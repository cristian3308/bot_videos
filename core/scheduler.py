#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Programador: lanza un lote de videos automáticamente a una hora del día (mientras el panel corra)."""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

from core.batch import run_batch
from core.store import load_sched, save_sched

_task: Optional[asyncio.Task] = None


async def _loop() -> None:
    while True:
        try:
            cfg = load_sched()
            if cfg.get("enabled"):
                now = datetime.now()
                today = now.strftime("%Y-%m-%d")
                if (now.hour == int(cfg.get("hour", 9))
                        and now.minute == int(cfg.get("minute", 0))
                        and cfg.get("last_run") != today):
                    save_sched({"last_run": today})
                    print(f"[SCHED] Lanzando lote programado de {cfg.get('count')} video(s)...")
                    try:
                        await run_batch(
                            count=int(cfg.get("count", 1)),
                            source=cfg.get("source", "news"),
                            lang=cfg.get("lang", "es"),
                            provider=(cfg.get("provider") or None),
                            model=(cfg.get("model") or None),
                            theme=cfg.get("theme", "verde"),
                            voice=(cfg.get("voice") or None),
                            music_mood=cfg.get("music_mood", "dark"),
                            branding=bool(cfg.get("branding", True)),
                            style=cfg.get("style", "auto"),
                        )
                        print("[SCHED] Lote programado completado.")
                    except Exception as exc:  # noqa: BLE001
                        print(f"[SCHED] Error en lote programado: {exc}")
        except Exception as exc:  # noqa: BLE001
            print(f"[SCHED] Error en el bucle: {exc}")
        await asyncio.sleep(30)


def start() -> None:
    """Arranca el bucle del programador (una sola vez)."""
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(_loop())
