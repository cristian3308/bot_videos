#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Subtítulos dinámicos .ASS estilo TikTok con efecto KARAOKE (resaltado palabra por palabra)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

# PrimaryColour = color de palabra YA dicha (resaltada), SecondaryColour = aún no dicha.
# Con karaoke \k, cada palabra empieza en SecondaryColour (blanco) y pasa a PrimaryColour (verde) al pronunciarse.
ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: CyberSub,Arial,66,&H0088FF00,&H00FFFFFF,&H00080808,&H80000000,-1,0,0,0,100,100,1,0,1,5,3,2,70,70,370,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def format_ass_time(seconds: float) -> str:
    """Convierte segundos a formato de tiempo ASS (H:MM:SS.cc)."""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centis = int(round((seconds - int(seconds)) * 100))
    if centis >= 100:
        centis = 99
    return f"{hrs}:{mins:02d}:{secs:02d}.{centis:02d}"


def build_dynamic_ass_subtitles(scenes: List[Dict[str, Any]], ass_path: Path) -> None:
    """
    Subtítulos .ASS con efecto karaoke: bloques de ~4 palabras donde cada palabra
    se ilumina (blanco -> verde neón) justo cuando el narrador la pronuncia.
    """
    events: List[str] = []
    current_time = 0.0

    for scene in scenes:
        duration = float(scene.get("duration", 5.0))
        words = scene.get("narration", "").split()
        if not words:
            current_time += duration
            continue

        chunk_size = 4
        chunks = [words[i:i + chunk_size] for i in range(0, len(words), chunk_size)]
        time_per_chunk = duration / len(chunks)

        for idx, chunk in enumerate(chunks):
            start_t = current_time + (idx * time_per_chunk)
            end_t = start_t + time_per_chunk
            per_word_cs = max(1, int(round((time_per_chunk / len(chunk)) * 100)))

            # Cada palabra con su tiempo de karaoke \k (en centisegundos)
            karaoke = "".join(f"{{\\k{per_word_cs}}}{w.upper()} " for w in chunk).strip()
            # Aparición suave + leve zoom
            pop = r"{\fad(60,40)\fscx108\fscy108\t(0,120,\fscx100\fscy100)}"
            events.append(
                f"Dialogue: 0,{format_ass_time(start_t)},{format_ass_time(end_t)},CyberSub,,0,0,0,,{pop}{karaoke}"
            )

        current_time += duration

    ass_path.write_text(ASS_HEADER + "\n".join(events) + "\n", encoding="utf-8")
