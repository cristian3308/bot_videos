#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Motor de voz neuronal (Edge TTS): síntesis, duración, muestras y listado de voces."""
from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Tuple

from config.settings import settings

DEFAULT_RATE = "+8%"
DEFAULT_PITCH = "-2Hz"
TICKS_PER_SECOND = 10_000_000.0  # Edge TTS usa unidades de 100ns


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


def _make_communicate(edge_tts: Any, text: str, voice: str, rate: str, pitch: str) -> Any:
    """Instancia edge_tts.Communicate pidiendo WordBoundary si la versión lo soporta."""
    kwargs = {"text": text, "voice": voice, "rate": _normalize_rate(rate), "pitch": _normalize_pitch(pitch)}
    try:
        return edge_tts.Communicate(**kwargs, boundary="WordBoundary")
    except TypeError:
        return edge_tts.Communicate(**kwargs)


async def synthesize_scene_audio_with_timings(
    text: str,
    voice: str,
    out_mp3: Path,
    rate: str = DEFAULT_RATE,
    pitch: str = DEFAULT_PITCH,
) -> Tuple[float, List[Dict[str, Any]]]:
    """
    Genera el MP3 de una escena con edge-tts y devuelve (duración_seg, word_timings).
    Cada elemento de word_timings tiene: {'text': str, 'start': float, 'end': float}.
    """
    import edge_tts

    clean_text = (text or "").strip()
    if not clean_text:
        clean_text = "..."

    communicate = _make_communicate(edge_tts, clean_text, voice, rate, pitch)
    word_timings: List[Dict[str, Any]] = []
    audio_chunks: List[bytes] = []

    async for chunk in communicate.stream():
        ctype = chunk.get("type")
        if ctype == "audio":
            audio_chunks.append(chunk["data"])
        elif ctype == "WordBoundary":
            w_text = (chunk.get("text") or "").strip()
            offset = chunk.get("offset")
            duration = chunk.get("duration")
            if w_text and offset is not None and duration is not None:
                start_s = float(offset) / TICKS_PER_SECOND
                dur_s = max(0.02, float(duration) / TICKS_PER_SECOND)
                word_timings.append({"text": w_text, "start": start_s, "end": start_s + dur_s})

    if not audio_chunks:
        raise RuntimeError(f"Edge TTS no devolvió audio para el texto: {clean_text[:60]!r}")

    out_mp3.write_bytes(b"".join(audio_chunks))
    duration_sec = await asyncio.to_thread(get_audio_duration, out_mp3)
    return duration_sec, word_timings


async def synthesize_scene_audio(
    text: str,
    voice: str,
    out_mp3: Path,
    rate: str = DEFAULT_RATE,
    pitch: str = DEFAULT_PITCH,
) -> float:
    """Genera el MP3 de una escena con edge-tts y devuelve su duración en segundos."""
    duration_sec, _ = await synthesize_scene_audio_with_timings(text, voice, out_mp3, rate, pitch)
    return duration_sec


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
