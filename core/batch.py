#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generación en LOTE de varios videos (desde noticias reales o desde el banco de temas)."""
from __future__ import annotations

import asyncio
from typing import Any, Callable, Dict, List, Optional

from core.news import fetch_latest_cyber_news
from core.pipeline import generate_plan, render_plan
from core.store import consume_topic, is_topic_used, load_topics, record_used_topic

ProgressCB = Optional[Callable[[int, str, str], Any]]


async def _emit(cb: ProgressCB, pct: int, stage: str, message: str) -> None:
    print(f"[LOTE {pct:3d}%] ({stage}) {message}")
    if cb is None:
        return
    r = cb(pct, stage, message)
    if asyncio.iscoroutine(r):
        await r


async def run_batch(
    count: int = 3,
    source: str = "news",
    lang: str = "es",
    provider: Optional[str] = None,
    model: Optional[str] = None,
    theme: str = "verde",
    voice: Optional[str] = None,
    rate: str = "+8%",
    pitch: str = "-2Hz",
    music_mood: str = "dark",
    branding: bool = True,
    style: Optional[str] = "auto",
    auto_upload_youtube: bool = False,
    auto_upload_tiktok: bool = False,
    progress: ProgressCB = None,
) -> List[Dict[str, Any]]:
    """Genera `count` videos seguidos evitando duplicados y rotando estilos. Devuelve la lista."""
    count = max(1, min(int(count), 20))

    # Elegir los temas de origen filtrando los ya usados en history.json
    selected: List[Dict[str, str]] = []
    if source == "bank":
        for t in load_topics():
            if not is_topic_used(t):
                selected.append({"topic": t, "link": "", "from_bank": "1"})
            if len(selected) >= count:
                break
    else:
        news = fetch_latest_cyber_news(limit=max(20, count * 4))
        for n in news:
            topic_str = f"{n['title']} - {n['summary']}"
            if not is_topic_used(topic_str, link=n.get("link", "")):
                selected.append({"topic": topic_str, "link": n.get("link", ""), "from_bank": ""})
            if len(selected) >= count:
                break

    if not selected:
        selected = [{"topic": "", "link": "", "from_bank": ""}] * count

    total = len(selected)
    results: List[Dict[str, Any]] = []

    for idx, entry in enumerate(selected, start=1):
        lo = int((idx - 1) / total * 100)
        hi = int(idx / total * 100)
        topic = entry["topic"] or None

        async def sub_progress(pct, stage, msg, _lo=lo, _hi=hi, _i=idx):
            overall = _lo + int(pct / 100 * (_hi - _lo))
            await _emit(progress, overall, "lote", f"Video {_i}/{total}: {msg}")

        try:
            await _emit(progress, lo, "lote", f"Video {idx}/{total}: generando guion...")
            plan = await asyncio.to_thread(
                generate_plan, topic, lang, provider, model, None, None, None, False, style, idx - 1
            )
            v_theme = plan.get("_theme", theme)
            v_mood = plan.get("_mood", music_mood)
            res = await render_plan(
                plan, lang=lang, progress=sub_progress, voice=voice, rate=rate, pitch=pitch,
                theme=v_theme, music_mood=v_mood, branding=branding,
            )

            # Marcar tema como usado para no repetirlo en próximos lotes
            if entry["from_bank"] and entry["topic"]:
                consume_topic(entry["topic"], title=res.get("title", ""))
            elif entry["topic"] or entry["link"]:
                record_used_topic(entry["topic"], title=res.get("title", ""), link=entry["link"])

            # Auto-subida opcional
            if auto_upload_youtube:
                try:
                    from uploaders import youtube
                    if youtube.is_connected():
                        yt_res = await asyncio.to_thread(
                            youtube.upload, res["mp4"], res.get("title", ""), res.get("description", ""),
                            None, None, res.get("thumb_youtube"),
                        )
                        res["youtube"] = yt_res
                        await _emit(progress, hi, "lote", f"Video {idx}/{total} subido a YouTube: {yt_res.get('url')}")
                except Exception as exc:  # noqa: BLE001
                    await _emit(progress, hi, "lote", f"Aviso YouTube (video {idx}): {exc}")

            if auto_upload_tiktok:
                try:
                    from uploaders import tiktok
                    if tiktok.is_connected():
                        tt_res = await asyncio.to_thread(tiktok.upload, res["mp4"], res.get("title", ""))
                        res["tiktok"] = tt_res
                        await _emit(progress, hi, "lote", f"Video {idx}/{total} subido a TikTok (borrador)")
                except Exception as exc:  # noqa: BLE001
                    await _emit(progress, hi, "lote", f"Aviso TikTok (video {idx}): {exc}")

            results.append(res)
            await _emit(progress, hi, "lote", f"Video {idx}/{total} listo: {res.get('title', '')[:40]}")
        except Exception as exc:  # noqa: BLE001
            await _emit(progress, hi, "lote", f"Error en video {idx}/{total}: {exc} (continuando lote)")

    await _emit(progress, 100, "done", f"Lote completado: {len(results)}/{total} videos")
    return results
