#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generación en LOTE de varios videos (desde noticias reales o desde el banco de temas)."""
from __future__ import annotations

import asyncio
from typing import Any, Callable, Dict, List, Optional

from core.news import fetch_latest_cyber_news
from core.pipeline import generate_plan, render_plan
from core.store import load_topics

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
    progress: ProgressCB = None,
) -> List[Dict[str, Any]]:
    """Genera `count` videos seguidos (rotando el estilo para que varíen). Devuelve la lista."""
    count = max(1, min(int(count), 20))

    # Elegir los temas de origen
    if source == "bank":
        topics = load_topics()[:count] or [None] * count
    else:
        news = fetch_latest_cyber_news(limit=count)
        topics = [f"{n['title']} - {n['summary']}" for n in news] or [None] * count
    topics = topics[:count]

    results: List[Dict[str, Any]] = []
    for idx, topic in enumerate(topics, start=1):
        lo = int((idx - 1) / count * 100)
        hi = int(idx / count * 100)

        async def sub_progress(pct, stage, msg, _lo=lo, _hi=hi, _i=idx):
            overall = _lo + int(pct / 100 * (_hi - _lo))
            await _emit(progress, overall, "lote", f"Video {_i}/{count}: {msg}")

        await _emit(progress, lo, "lote", f"Video {idx}/{count}: generando guion...")
        plan = await asyncio.to_thread(
            generate_plan, topic, lang, provider, model, None, None, None, False, style, idx - 1
        )
        v_theme = plan.get("_theme", theme)
        v_mood = plan.get("_mood", music_mood)
        res = await render_plan(
            plan, lang=lang, progress=sub_progress, voice=voice, rate=rate, pitch=pitch,
            theme=v_theme, music_mood=v_mood, branding=branding,
        )
        results.append(res)
        await _emit(progress, hi, "lote", f"Video {idx}/{count} listo: {res.get('title', '')[:40]}")

    await _emit(progress, 100, "done", f"Lote completado: {len(results)} videos")
    return results
