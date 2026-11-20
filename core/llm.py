#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Capa de generación de guion multi-proveedor.

Proveedores (config.settings.llm_provider):
  - opencode : OpenCode Go, endpoint compatible con OpenAI (principal).
  - gemini   : Google Gemini.
  - openai   : OpenAI (o endpoint compatible).
  - ollama   : modelo local gratuito.
  - demo     : caso forense pre-cargado, sin red.

Soporta personalización: modelo, nº de escenas, duración y continuaciones ("Parte 2").
"""
from __future__ import annotations

import json
import re
import uuid
from typing import Any, Dict, List, Optional

import requests

from config.settings import settings
from core.news import fetch_latest_cyber_news
from core.prompts import DEMO_VIDEO_PLAN, SYSTEM_PROMPT_CYBERCRIME

TIMEOUT = 180  # los modelos con razonamiento (p.ej. glm-5.3) tardan en el guion completo

# El plan OpenCode Go pide identificar al cliente y enviar un x-opencode-session estable.
USER_AGENT = "cybercrime-studio/1.0"

# Modelos de respaldo de OpenCode Go (si el elegido falla, se prueban en orden).
OPENCODE_FALLBACK = ["glm-5.3", "glm-5.3-flash", "claude-haiku-5-5", "kimi-k3", "qwen3.8-flash", "grok-4.7"]


def _opencode_headers(api_key: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
        "x-opencode-session": uuid.uuid4().hex,
    }


def _api_error(resp: "requests.Response") -> str:
    """Extrae un mensaje de error legible del cuerpo de la respuesta de la API."""
    try:
        j = resp.json()
        msg = (j.get("error", {}) or {}).get("message") or j.get("message") or resp.text
    except Exception:  # noqa: BLE001
        msg = resp.text
    return f"[{resp.status_code}] {msg}".strip()


def _clean_json(raw_text: str) -> Dict[str, Any]:
    """Extrae un objeto JSON aunque venga con ```json ... ``` o texto alrededor."""
    cleaned = re.sub(r"^```json\s*|\s*```$", "", raw_text.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


_VALID_SCENE_TYPES = {"terminal", "diagram", "evidence", "map", "stat", "timeline", "brand"}


def validate_and_normalize_plan(plan: Any, lang: str = "es") -> Dict[str, Any]:
    """Valida y normaliza el JSON devuelto por el LLM para evitar fallos en TTS/render."""
    if not isinstance(plan, dict):
        raise ValueError("El LLM no devolvió un objeto JSON válido.")

    raw_scenes = plan.get("scenes")
    if not isinstance(raw_scenes, list) or not raw_scenes:
        raise ValueError("El guion devuelto por el LLM no contiene escenas.")

    title = str(plan.get("title") or "Caso de Ciberseguridad").strip()[:100]
    description = str(plan.get("description") or title).strip()

    normalized_scenes: List[Dict[str, Any]] = []
    for idx, raw in enumerate(raw_scenes, start=1):
        if not isinstance(raw, dict):
            continue
        stype = str(raw.get("scene_type") or "evidence").strip().lower()
        if stype not in _VALID_SCENE_TYPES:
            stype = "evidence"

        headline = str(raw.get("headline") or f"ESCENA {idx}").strip()
        narration = str(raw.get("narration") or "").strip() or headline
        badge = str(raw.get("badge") or "CYBERSECURITY INTEL").strip()

        t_lines = raw.get("terminal_lines")
        if isinstance(t_lines, str):
            t_lines = [line.strip() for line in t_lines.splitlines() if line.strip()]
        elif not isinstance(t_lines, list):
            t_lines = []
        else:
            t_lines = [str(x).strip() for x in t_lines if str(x).strip()]

        d_nodes = raw.get("diagram_nodes")
        if isinstance(d_nodes, str):
            d_nodes = [n.strip() for n in d_nodes.split(",") if n.strip()]
        elif not isinstance(d_nodes, list):
            d_nodes = []
        else:
            d_nodes = [str(x).strip() for x in d_nodes if str(x).strip()]

        scene_clean: Dict[str, Any] = {
            "id": idx,
            "scene_type": stype,
            "narration": narration,
            "headline": headline,
            "badge": badge,
            "terminal_lines": t_lines,
            "diagram_nodes": d_nodes,
            "code_snippet": str(raw.get("code_snippet") or ""),
        }
        if raw.get("stat_value") is not None:
            scene_clean["stat_value"] = str(raw.get("stat_value"))
        if raw.get("stat_label") is not None:
            scene_clean["stat_label"] = str(raw.get("stat_label"))
        if raw.get("subtitle") is not None:
            scene_clean["subtitle"] = str(raw.get("subtitle"))
        normalized_scenes.append(scene_clean)

    if not normalized_scenes:
        raise ValueError("Ninguna escena del guion tiene formato válido.")

    out = dict(plan)
    out["title"] = title
    out["description"] = description
    out["language"] = str(plan.get("language") or lang)
    out["voice"] = str(plan.get("voice") or settings.default_voice(lang))
    out["scenes"] = normalized_scenes
    return out


def _build_user_prompt(
    topic: Optional[str],
    lang: str,
    num_scenes: Optional[int] = None,
    target_seconds: Optional[int] = None,
    previous: Optional[Dict[str, Any]] = None,
    tone: Optional[str] = None,
    hook_instruction: Optional[str] = None,
) -> str:
    voice_default = settings.default_voice(lang)
    if not topic and not previous:
        news = fetch_latest_cyber_news(limit=1)
        if news:
            topic = f"{news[0]['title']} - {news[0]['summary']}"
            try:
                print(f"[*] Noticia detectada automáticamente: {news[0]['title']}")
            except UnicodeEncodeError:
                pass
        else:
            topic = "El ataque de cadena de suministro a SolarWinds explicado paso a paso"

    extra = []
    if num_scenes:
        extra.append(f"- Genera EXACTAMENTE {num_scenes} escenas.")
    if target_seconds:
        words = int(target_seconds * 2.6)  # ~2.6 palabras/seg
        extra.append(f"- Duración objetivo: ~{target_seconds} segundos (~{words} palabras en total).")

    continuation = ""
    if previous:
        part = previous.get("part", 2)
        continuation = (
            f"\nESTE ES UN VIDEO DE CONTINUACIÓN (PARTE {part}) de una serie.\n"
            f"Video anterior — Título: {previous.get('title','')}\n"
            f"Resumen anterior: {previous.get('description','')}\n"
            "La PRIMERA escena debe abrir con un recordatorio tipo 'En la parte anterior...' "
            "(2-3 segundos) y luego AVANZAR la historia con información nueva, sin repetir lo ya contado. "
            "Mantén el mismo estilo, tono y nivel técnico. El título debe incluir 'Parte "
            f"{part}'.\n"
        )
        if not topic:
            topic = f"Continúa la historia del video anterior: {previous.get('title','')}"

    prompt = (
        f"Idioma del guion: {lang} (usa la voz '{voice_default}').\n"
        f"Tema / Caso de ciberseguridad a desarrollar:\n{topic}\n"
        f"{continuation}\n"
    )
    if extra:
        prompt += "Requisitos adicionales:\n" + "\n".join(extra) + "\n"
    if tone:
        prompt += f"ESTILO DE NARRACIÓN: {tone}\n"
    if hook_instruction:
        prompt += f"{hook_instruction}\n"
    prompt += "\nGenera el JSON siguiendo exactamente la estructura indicada."
    return prompt


# ---------------------------------------------------------------------------
# Proveedores
# ---------------------------------------------------------------------------
def _demo_plan(lang: str) -> Dict[str, Any]:
    plan = json.loads(json.dumps(DEMO_VIDEO_PLAN))
    if lang == "en":
        plan["voice"] = settings.voice_en
    return plan


def _generate_openai_compatible(
    base_url: str,
    api_key: str,
    model: str,
    user_prompt: str,
    extra_headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Sirve para OpenCode Go y OpenAI (misma API /chat/completions)."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT_CYBERCRIME},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.7,
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    url = base_url.rstrip("/") + "/chat/completions"

    resp = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT)
    if resp.status_code == 400 and "response_format" in resp.text:
        # Algunos modelos no aceptan response_format: reintentar sin él.
        payload.pop("response_format", None)
        resp = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT)
    if not resp.ok:
        raise RuntimeError(_api_error(resp))
    data = resp.json()
    return _clean_json(data["choices"][0]["message"]["content"])


def _generate_gemini(user_prompt: str, model: str) -> Dict[str, Any]:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={settings.gemini_api_key}"
    )
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT_CYBERCRIME}]},
        "contents": [{"parts": [{"text": user_prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.7},
    }
    resp = requests.post(url, json=payload, timeout=TIMEOUT)
    resp.raise_for_status()
    result = resp.json()
    return _clean_json(result["candidates"][0]["content"]["parts"][0]["text"])


def _generate_ollama(user_prompt: str, model: str) -> Dict[str, Any]:
    url = settings.ollama_base_url.rstrip("/") + "/api/chat"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT_CYBERCRIME},
            {"role": "user", "content": user_prompt},
        ],
        "format": "json",
        "stream": False,
        "options": {"temperature": 0.7},
    }
    resp = requests.post(url, json=payload, timeout=TIMEOUT * 2)
    resp.raise_for_status()
    return _clean_json(resp.json()["message"]["content"])


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------
def generate_script(
    topic: Optional[str] = None,
    lang: str = "es",
    provider: Optional[str] = None,
    model: Optional[str] = None,
    num_scenes: Optional[int] = None,
    target_seconds: Optional[int] = None,
    previous: Optional[Dict[str, Any]] = None,
    raise_on_error: bool = False,
    tone: Optional[str] = None,
    hook_instruction: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Genera el plan del video en JSON.
    Si falla: con raise_on_error=True relanza el error (para que el panel lo muestre);
    si no, usa el caso demo de respaldo (útil para el CLI).
    """
    provider = (provider or settings.llm_provider).lower()
    if provider == "demo":
        return _demo_plan(lang)

    try:
        user_prompt = _build_user_prompt(topic, lang, num_scenes, target_seconds, previous, tone, hook_instruction)
        if provider == "opencode":
            if not settings.opencode_api_key:
                raise RuntimeError("Falta OPENCODE_API_KEY en el .env")
            # Fallback inteligente: prueba el modelo elegido y, si falla, los de respaldo.
            candidates = [model or settings.opencode_model]
            for m in OPENCODE_FALLBACK:
                if m not in candidates:
                    candidates.append(m)
            last_exc: Optional[Exception] = None
            for m in candidates:
                try:
                    plan = _generate_openai_compatible(
                        settings.opencode_base_url, settings.opencode_api_key, m, user_prompt,
                        extra_headers=_opencode_headers(settings.opencode_api_key),
                    )
                    plan = validate_and_normalize_plan(plan, lang)
                    plan["_model_used"] = m
                    return plan
                except Exception as e:  # noqa: BLE001
                    print(f"[*] Modelo '{m}' no disponible ({str(e)[:80]}). Probando otro...")
                    last_exc = e
            raise last_exc or RuntimeError("Ningún modelo de OpenCode respondió")
        if provider == "openai":
            if not settings.openai_api_key:
                raise RuntimeError("Falta OPENAI_API_KEY en el .env")
            plan = _generate_openai_compatible(
                settings.openai_base_url, settings.openai_api_key,
                model or settings.openai_model, user_prompt,
            )
            return validate_and_normalize_plan(plan, lang)
        if provider == "gemini":
            if not settings.gemini_api_key:
                raise RuntimeError("Falta GEMINI_API_KEY en el .env")
            return validate_and_normalize_plan(_generate_gemini(user_prompt, model or settings.gemini_model), lang)
        if provider == "ollama":
            return validate_and_normalize_plan(_generate_ollama(user_prompt, model or settings.ollama_model), lang)
        return _demo_plan(lang)
    except Exception as exc:  # noqa: BLE001
        if raise_on_error:
            raise
        print(f"[!] Error generando guion con '{provider}' ({exc}). Usando caso demo de respaldo...")
        return _demo_plan(lang)


def list_opencode_models() -> List[Dict[str, str]]:
    """Lista los modelos disponibles en OpenCode Go."""
    if not settings.opencode_api_key:
        raise RuntimeError("Falta OPENCODE_API_KEY en el .env")
    resp = requests.get(settings.opencode_models_url, headers=_opencode_headers(settings.opencode_api_key), timeout=30)
    resp.raise_for_status()
    data = resp.json()
    rows = data.get("data", data if isinstance(data, list) else [])
    out = []
    for m in rows:
        if isinstance(m, dict):
            out.append({"id": m.get("id", ""), "name": m.get("name", m.get("id", ""))})
        else:
            out.append({"id": str(m), "name": str(m)})
    return out
