#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Motor de voz neuronal (Edge TTS): síntesis, duración, muestras y listado de voces."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List

from config.settings import settings

DEFAULT_RATE = "+8%"
DEFAULT_PITCH = "-2Hz"


def get_audio_duration(audio_path: Path) -> float:
    """Obtiene la duración exacta en segundos de un archivo de audio con ffprobe."""
    cmd = [
        settings.ffprobe or "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(audio_path),
    ]
    out = subprocess.check_output(cmd, text=True).strip()
    return float(out)


def _normalize_rate(rate: str) -> str:
    rate = (rate or DEFAULT_RATE).strip()
    if not rate.endswith("%"):
        rate = rate + "%"
    if not rate.startswith(("+", "-")):
        rate = "+" + rate
    return rate


def _normalize_pitch(pitch: str) -> str:
    pitch = (pitch or DEFAULT_PITCH).strip()
    if not pitch.lower().endswith("hz"):
        pitch = pitch + "Hz"
    if not pitch.startswith(("+", "-")):
        pitch = "+" + pitch
    return pitch


async def synthesize_scene_audio(
    text: str,
    voice: str,
    out_mp3: Path,
    rate: str = DEFAULT_RATE,
    pitch: str = DEFAULT_PITCH,
) -> float:
    """Genera el MP3 de una escena con edge-tts y devuelve su duración en segundos."""
    import edge_tts

    communicate = edge_tts.Communicate(
        text=text, voice=voice, rate=_normalize_rate(rate), pitch=_normalize_pitch(pitch)
    )
    await communicate.save(str(out_mp3))
    return get_audio_duration(out_mp3)


async def synthesize_sample(
    voice: str,
    out_mp3: Path,
    text: str = "Esta es una muestra de la voz seleccionada para tu video.",
    rate: str = DEFAULT_RATE,
    pitch: str = DEFAULT_PITCH,
) -> Path:
    """Genera una muestra corta para que el usuario escuche la voz antes de generar."""
    import edge_tts

    communicate = edge_tts.Communicate(
        text=text, voice=voice, rate=_normalize_rate(rate), pitch=_normalize_pitch(pitch)
    )
    await communicate.save(str(out_mp3))
    return out_mp3


async def list_voices(lang_prefix: str = "") -> List[dict]:
    """Devuelve las voces disponibles de Edge TTS (opcionalmente filtradas por idioma)."""
    import edge_tts

    voices = await edge_tts.list_voices()
    result = []
    for v in voices:
        short = v.get("ShortName", "")
        if lang_prefix and not short.lower().startswith(lang_prefix.lower()):
            continue
        result.append({
            "name": short,
            "gender": v.get("Gender", ""),
            "locale": v.get("Locale", ""),
        })
    return sorted(result, key=lambda x: x["name"])
