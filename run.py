#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lanzador del panel web del Creador de Videos.

Uso:
    python run.py

Luego abre http://127.0.0.1:8000 en tu navegador.
Funciona igual en Windows y Linux.
"""
from __future__ import annotations

import asyncio
import sys

import uvicorn

from config.settings import settings


def _fix_windows_event_loop() -> None:
    """Playwright necesita el ProactorEventLoop en Windows para lanzar Chromium."""
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    # Evitar que un título con emoji crashee la consola de Windows (cp1252).
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass


def main() -> None:
    _fix_windows_event_loop()
    print("=" * 60)
    print("  CYBERCRIME STUDIO — panel web")
    print(f"  Abre:  http://{settings.web_host}:{settings.web_port}")
    print(f"  FFmpeg: {'OK' if settings.ffmpeg_ready() else 'NO ENCONTRADO (instálalo)'}")
    print(f"  Proveedor IA por defecto: {settings.llm_provider}")
    print("=" * 60)
    uvicorn.run(
        "web.app:app",
        host=settings.web_host,
        port=settings.web_port,
        loop="asyncio",
        reload=False,
    )


if __name__ == "__main__":
    main()
