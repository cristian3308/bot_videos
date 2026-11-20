#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Orquestador del pipeline. Separado en dos fases: generar guion y renderizar."""
from __future__ import annotations

import asyncio
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from config.settings import settings
from core.assemble import assemble_final_video, generate_thumbnail
from core.llm import generate_script
from core.render import generate_scene_html, generate_youtube_thumbnail, render_scene_video_playwright
from core.subtitles import build_dynamic_ass_subtitles
from core.tts import DEFAULT_PITCH, DEFAULT_RATE, synthesize_scene_audio_with_timings

ProgressCB = Optional[Callable[[int, str, str], Any]]


async def _emit(cb: ProgressCB, pct: int, stage: str, message: str) -> None:
    print(f"[{pct:3d}%] ({stage}) {message}")
    if cb is None:
        return
    result = cb(pct, stage, message)
    if asyncio.iscoroutine(result):
        await result


def _build_brand_scenes(title: str, lang: str, series_part: Optional[int]) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """Genera las escenas de intro/outro adaptadas a la marca configurada y al idioma."""
    brand = (settings.brand_name or "DÍA CERO").strip()
    is_en = (lang or "es").lower().startswith("en")
    if is_en:
        tagline = settings.brand_tagline_en or "Real cybersecurity case"
        outro_badge = f"PART {series_part + 1} SOON" if series_part else "FOLLOW"
        intro = {
            "scene_type": "brand",
            "headline": title[:60],
            "badge": brand,
            "subtitle": tagline,
            "narration": title,
        }
        outro = {
            "scene_type": "brand",
            "headline": "FOLLOW FOR MORE",
            "badge": outro_badge,
            "subtitle": "More real cybercrime stories",
            "narration": "If you found this useful, follow for the next real cybersecurity story.",
        }
    else:
        tagline = settings.brand_tagline_es or "Caso real de ciberseguridad"
        outro_badge = f"PARTE {series_part + 1} PRONTO" if series_part else "SÍGUEME"
        intro = {
            "scene_type": "brand",
            "headline": title[:60],
            "badge": brand,
            "subtitle": tagline,
            "narration": title,
        }
        outro = {
            "scene_type": "brand",
            "headline": "SÍGUEME PARA MÁS",
            "badge": outro_badge,
            "subtitle": "Más historias reales de hackers",
            "narration": "Si te sirvió, sígueme para la siguiente historia real de ciberseguridad.",
        }
    return intro, outro


# ---------------------------------------------------------------------------
# FASE 1: Guion
# ---------------------------------------------------------------------------
def generate_plan(
    topic: Optional[str] = None,
    lang: str = "es",
    provider: Optional[str] = None,
    model: Optional[str] = None,
    num_scenes: Optional[int] = None,
    target_seconds: Optional[int] = None,
    previous: Optional[Dict[str, Any]] = None,
    raise_on_error: bool = False,
    style: Optional[str] = None,
    style_index: Optional[int] = None,
    hook: Optional[str] = "auto",
) -> Dict[str, Any]:
    """Genera solo el guion (JSON) aplicando el estilo (tono + tema + mood) y el hook viral."""
    from core.styles import resolve, resolve_hook
    style_name, s = resolve(style, topic, style_index)
    hook_instr = resolve_hook(hook)
    plan = generate_script(
        topic=topic, lang=lang, provider=provider, model=model,
        num_scenes=num_scenes, target_seconds=target_seconds, previous=previous,
        raise_on_error=raise_on_error, tone=s["tone"], hook_instruction=hook_instr,
    )
    plan["_style"] = style_name
    plan["_theme"] = s["theme"]
    plan["_mood"] = s["mood"]
    if hook and hook != "auto":
        plan["_hook"] = hook
    return plan


# ---------------------------------------------------------------------------
# FASE 2: Render
# ---------------------------------------------------------------------------
async def render_plan(
    video_plan: Dict[str, Any],
    lang: str = "es",
    out_dir: Optional[Path] = None,
    progress: ProgressCB = None,
    voice: Optional[str] = None,
    rate: str = DEFAULT_RATE,
    pitch: str = DEFAULT_PITCH,
    theme: Optional[str] = None,
    music_path: Optional[Path] = None,
    logo_path: Optional[Path] = None,
    branding: bool = True,
    series_part: Optional[int] = None,
    music_mood: str = "dark",
    aspect_ratio: str = "9:16",
    sfx: bool = True,
) -> Dict[str, Any]:
    """Renderiza el video a partir de un plan (guion) ya generado o editado."""
    if not settings.ffmpeg_ready():
        raise RuntimeError("FFmpeg no está disponible. Instálalo o define FFMPEG_PATH en el .env.")

    out_dir = out_dir or settings.output_dir
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    project_dir = out_dir / f"cyber_video_{timestamp}"
    work_dir = project_dir / "temp_build"
    work_dir.mkdir(parents=True, exist_ok=True)

    # Trabajar sobre una copia para no mutar el dict original del llamador
    plan_copy: Dict[str, Any] = json.loads(json.dumps(video_plan))
    plan_copy["_aspect_ratio"] = aspect_ratio
    plan_path = project_dir / "video_plan.json"
    plan_path.write_text(json.dumps(plan_copy, indent=2, ensure_ascii=False), encoding="utf-8")

    voice = voice or plan_copy.get("voice") or settings.default_voice(lang)
    scenes: List[Dict[str, Any]] = list(plan_copy.get("scenes", []))
    if not scenes:
        raise RuntimeError("El guion no contiene escenas.")

    # Intro + outro de marca automáticos (opcional)
    if branding:
        title = (plan_copy.get("title") or settings.brand_name or "DÍA CERO").strip()
        intro, outro = _build_brand_scenes(title, lang, series_part)
        scenes = [intro] + scenes + [outro]

    for i, s in enumerate(scenes, start=1):
        s["id"] = i
    plan_copy["scenes"] = scenes
    total = len(scenes)

    # --- Paso 1: sintetizar toda la voz en paralelo (hasta 3 a la vez) + WordBoundary timings ---
    tts_sem = asyncio.Semaphore(3)
    tts_done = 0

    async def _synth_one(idx: int, scene: Dict[str, Any]) -> Path:
        nonlocal tts_done
        audio_file = work_dir / f"scene_{idx:02d}.mp3"
        async with tts_sem:
            dur, timings = await synthesize_scene_audio_with_timings(
                scene.get("narration", ""), voice, audio_file, rate, pitch
            )
            scene["duration"] = dur
            scene["_word_timings"] = timings
            tts_done += 1
            await _emit(progress, 10 + int(tts_done / total * 25), "voz", f"Voz lista {tts_done}/{total}...")
        return audio_file

    await _emit(progress, 10, "voz", f"Sintetizando narración de {total} escenas...")
    scene_audios: List[Path] = list(
        await asyncio.gather(*[_synth_one(i, sc) for i, sc in enumerate(scenes, start=1)])
    )

    total_dur = sum(float(s.get("duration", 0)) for s in scenes) or 1.0

    # Calcular tramos de barra de progreso y escribir HTMLs antes de grabar
    scene_jobs: List[tuple[int, Dict[str, Any], Path, Path, float]] = []
    elapsed = 0.0
    for i, scene in enumerate(scenes, start=1):
        dur = float(scene.get("duration", 5.0))
        prog_start, prog_end = elapsed / total_dur, (elapsed + dur) / total_dur
        elapsed += dur
        html_file = work_dir / f"scene_{i:02d}.html"
        video_file = work_dir / f"scene_{i:02d}.mp4"
        html_file.write_text(
            generate_scene_html(
                scene, total_scenes=total, theme=theme,
                prog_start=prog_start, prog_end=prog_end, aspect_ratio=aspect_ratio,
            ),
            encoding="utf-8",
        )
        scene_jobs.append((i, scene, html_file, video_file, dur))

    # --- Paso 2: reutilizar un solo Chromium y renderizar escenas en paralelo ---
    from playwright.async_api import async_playwright

    render_sem = asyncio.Semaphore(settings.render_concurrency)
    rendered_done = 0
    thumb_yt = project_dir / "thumb_youtube.jpg"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            async def _render_one(idx: int, sc: Dict[str, Any], hfile: Path, vfile: Path, dur: float) -> Path:
                nonlocal rendered_done
                async with render_sem:
                    await render_scene_video_playwright(
                        hfile, dur, vfile, browser=browser, aspect_ratio=aspect_ratio
                    )
                    rendered_done += 1
                    await _emit(
                        progress,
                        35 + int(rendered_done / total * 45),
                        "escena",
                        f"Escena {rendered_done}/{total} lista [{sc.get('scene_type')}] ({dur:.1f}s)",
                    )
                return vfile

            await _emit(
                progress, 35, "escena",
                f"Grabando {total} escenas en {aspect_ratio} (concurrencia: {settings.render_concurrency})...",
            )
            scene_videos: List[Path] = list(
                await asyncio.gather(*[_render_one(*job) for job in scene_jobs])
            )

            await _emit(progress, 82, "miniatura", "Generando miniatura de YouTube...")
            yt_sub = "REAL CASE" if (lang or "es").lower().startswith("en") else "CASO REAL"
            await generate_youtube_thumbnail(
                plan_copy.get("title", ""), thumb_yt, theme=theme, subtitle=yt_sub, browser=browser
            )
        finally:
            await browser.close()

    await _emit(progress, 85, "subtitulos", "Generando subtítulos karaoke .ASS sincronizados...")
    ass_file = work_dir / "subtitles.ass"
    build_dynamic_ass_subtitles(scenes, ass_file, theme=theme, aspect_ratio=aspect_ratio)

    sfx_file: Optional[Path] = None
    if sfx:
        await _emit(progress, 87, "sfx", "Sintetizando efectos de sonido (SFX) por escena...")
        from core.sfx import build_sfx_track
        sfx_file = await asyncio.to_thread(build_sfx_track, scenes, work_dir / "sfx_track.wav")

    await _emit(progress, 90, "ensamblaje", "Ensamblando MP4 final con FFmpeg (loudnorm -14 LUFS)...")
    final_mp4 = project_dir / "video_final.mp4"
    await asyncio.to_thread(
        assemble_final_video, scene_videos, scene_audios, ass_file, final_mp4, work_dir,
        Path(music_path) if music_path else None,
        Path(logo_path) if logo_path else None,
        music_mood,
        None,
        sfx_file,
    )

    # Miniatura para la biblioteca (fotograma)
    thumb = project_dir / "thumb.jpg"
    await asyncio.to_thread(generate_thumbnail, final_mp4, thumb, 1.0)

    meta_txt = project_dir / "metadatos_publicacion.txt"
    meta_txt.write_text(
        f"TÍTULO:\n{plan_copy.get('title')}\n\n"
        f"DESCRIPCIÓN:\n{plan_copy.get('description')}\n\n"
        f"FORMATO: {aspect_ratio}\n\n"
        "CHECKLIST DE SUBIDA (YOUTUBE / TIKTOK):\n"
        "- Marcar 'Contenido alterado o sintético' solo si usas rostros realistas.\n"
        "- Duración > 60s para TikTok Creator Rewards y YouTube Shorts.\n",
        encoding="utf-8",
    )

    # Guardar el plan actualizado (con duraciones, sin los timings internos pesados) para series "Parte 2"
    for sc in plan_copy["scenes"]:
        sc.pop("_word_timings", None)
    plan_path.write_text(json.dumps(plan_copy, indent=2, ensure_ascii=False), encoding="utf-8")

    # Limpiar temporales pesados (temp_build/) salvo que se pida conservarlos
    if not settings.keep_temp_files:
        shutil.rmtree(work_dir, ignore_errors=True)

    await _emit(progress, 100, "listo", "¡Video completado!")
    return {
        "mp4": str(final_mp4.resolve()),
        "plan_json": str(plan_path.resolve()),
        "metadata_txt": str(meta_txt.resolve()),
        "thumb": str(thumb.resolve()) if thumb.exists() else None,
        "thumb_youtube": str(thumb_yt.resolve()) if thumb_yt.exists() else None,
        "project_dir": str(project_dir.resolve()),
        "project": project_dir.name,
        "title": plan_copy.get("title", ""),
        "description": plan_copy.get("description", ""),
        "aspect_ratio": aspect_ratio,
    }


# ---------------------------------------------------------------------------
# One-shot (CLI): guion + render juntos
# ---------------------------------------------------------------------------
async def run_pipeline(
    topic: Optional[str] = None,
    lang: str = "es",
    provider: Optional[str] = None,
    out_dir: Optional[Path] = None,
    progress: ProgressCB = None,
    model: Optional[str] = None,
    num_scenes: Optional[int] = None,
    target_seconds: Optional[int] = None,
    voice: Optional[str] = None,
    rate: str = DEFAULT_RATE,
    pitch: str = DEFAULT_PITCH,
    theme: Optional[str] = None,
    music_path: Optional[Path] = None,
    logo_path: Optional[Path] = None,
    previous: Optional[Dict[str, Any]] = None,
    branding: bool = True,
    style: Optional[str] = "auto",
    music_mood: Optional[str] = None,
    aspect_ratio: str = "9:16",
    sfx: bool = True,
    hook: Optional[str] = "auto",
) -> Dict[str, Any]:
    await _emit(progress, 5, "guion", f"Generando guion con proveedor '{provider or settings.llm_provider}'...")
    plan = await asyncio.to_thread(
        generate_plan, topic, lang, provider, model, num_scenes, target_seconds, previous, False, style, None, hook
    )
    await _emit(progress, 10, "guion", f"Título: {plan.get('title')}")
    return await render_plan(
        plan, lang=lang, out_dir=out_dir, progress=progress,
        voice=voice, rate=rate, pitch=pitch,
        theme=theme or plan.get("_theme"),
        music_path=music_path, logo_path=logo_path, branding=branding,
        series_part=(previous or {}).get("part") if previous else None,
        music_mood=music_mood or plan.get("_mood", "dark"),
        aspect_ratio=aspect_ratio, sfx=sfx,
    )
