#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generación de un video por línea de comandos (sin panel web).

Ejemplos:
    python cli.py --provider demo
    python cli.py --topic "El ataque a SolarWinds" --provider opencode --lang es
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from config.settings import settings
from core.pipeline import run_pipeline


def _fix_windows_event_loop() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Creador de Videos de Cibercrímenes (CLI)")
    parser.add_argument("--topic", default=None, help="Tema o caso específico (opcional)")
    parser.add_argument("--lang", default=settings.lang, choices=["es", "en"], help="Idioma")
    parser.add_argument("--provider", default=settings.llm_provider,
                        choices=["opencode", "gemini", "openai", "ollama", "demo"],
                        help="Motor de guion")
    parser.add_argument("--format", dest="aspect_ratio", default="9:16", choices=["9:16", "16:9"],
                        help="Formato de video: 9:16 (Shorts/TikTok) o 16:9 (YouTube horizontal)")
    parser.add_argument("--hook", default="auto",
                        choices=["auto", "cifra", "paradoja", "error_fatal", "cuenta_regresiva", "pregunta"],
                        help="Plantilla de gancho viral para los primeros 3 segundos")
    parser.add_argument("--no-sfx", action="store_true", help="Desactivar efectos de sonido (SFX)")
    args = parser.parse_args()

    _fix_windows_event_loop()
    result = asyncio.run(run_pipeline(
        topic=args.topic, lang=args.lang, provider=args.provider,
        aspect_ratio=args.aspect_ratio, sfx=not args.no_sfx, hook=args.hook,
    ))

    print("\n[OK] ¡Video completado!")
    print(f"     MP4       : {result['mp4']}")
    print(f"     Guion JSON: {result['plan_json']}")
    print(f"     Metadatos : {result['metadata_txt']}")


if __name__ == "__main__":
    main()
