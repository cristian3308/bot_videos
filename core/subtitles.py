#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Subtítulos dinámicos .ASS estilo TikTok con efecto KARAOKE (resaltado palabra por palabra)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

# Colores ASS en formato &H00BBGGRR (inverso a RGB) para que el karaoke combine con el tema.
THEME_ASS_COLORS: Dict[str, str] = {
    "verde":   "&H0088FF00",  # #00ff88
    "azul":    "&H00F8BD38",  # #38bdf8
    "rojo":    "&H005C3BFF",  # #ff3b5c
    "purpura": "&H00FF6BB3",  # #b36bff
    "naranja": "&H001C9FFF",  # #ff9f1c
}


def _ass_header(theme: Optional[str] = None) -> str:
    primary = THEME_ASS_COLORS.get((theme or "verde").lower(), THEME_ASS_COLORS["verde"])
    # PrimaryColour = color de palabra YA dicha (resaltada), SecondaryColour = aún no dicha (blanco).
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: CyberSub,Arial,66,{primary},&H00FFFFFF,&H00080808,&H80000000,-1,0,0,0,100,100,1,0,1,5,3,2,70,70,370,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _escape_ass_text(text: str) -> str:
    """Escapa caracteres que tienen significado especial en subtítulos ASS."""
    return (
        text.replace("\\", r"\\")
        .replace("{", r"\{")
        .replace("}", r"\}")
        .replace("\r", " ")
        .replace("\n", " ")
    )


def format_ass_time(seconds: float) -> str:
    """Convierte segundos a formato de tiempo ASS (H:MM:SS.cc)."""
    seconds = max(0.0, float(seconds))
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centis = int(round((seconds - int(seconds)) * 100))
    if centis >= 100:
        centis = 99
    return f"{hrs}:{mins:02d}:{secs:02d}.{centis:02d}"


def _build_scene_events_from_timings(
    word_timings: List[Dict[str, Any]],
    scene_offset: float,
    scene_duration: float,
    chunk_size: int = 4,
) -> List[str]:
    """Construye eventos ASS karaoke usando timestamps reales (WordBoundary) de Edge TTS."""
    events: List[str] = []
    pop = r"{\fad(50,35)\fscx108\fscy108\t(0,110,\fscx100\fscy100)}"
    chunks = [word_timings[i:i + chunk_size] for i in range(0, len(word_timings), chunk_size)]

    for c_idx, chunk in enumerate(chunks):
        chunk_start = float(chunk[0]["start"])
        if c_idx + 1 < len(chunks):
            next_start = float(chunks[c_idx + 1][0]["start"])
            chunk_end = max(float(chunk[-1]["end"]), min(next_start, float(chunk[-1]["end"]) + 0.25))
        else:
            chunk_end = min(scene_duration, max(float(chunk[-1]["end"]) + 0.15, chunk_start + 0.2))

        karaoke_parts: List[str] = []
        cursor = chunk_start
        for w_idx, w in enumerate(chunk):
            w_start = float(w["start"])
            w_end = float(w["end"])
            # Si hay una pausa antes de la palabra, absorberla en el tiempo de la palabra anterior o de esta
            if w_idx + 1 < len(chunk):
                next_w_start = float(chunk[w_idx + 1]["start"])
                span = max(w_end - cursor, next_w_start - cursor)
            else:
                span = max(w_end - cursor, chunk_end - cursor)
            cs = max(1, int(round(span * 100)))
            word_txt = _escape_ass_text(str(w["text"]).upper())
            karaoke_parts.append(f"{{\\k{cs}}}{word_txt}")
            cursor = max(w_end, w_start + span)

        abs_start = scene_offset + chunk_start
        abs_end = scene_offset + max(chunk_end, chunk_start + 0.1)
        events.append(
            f"Dialogue: 0,{format_ass_time(abs_start)},{format_ass_time(abs_end)},CyberSub,,0,0,0,,{pop}{' '.join(karaoke_parts)}"
        )
    return events


def _build_scene_events_proportional(
    words: List[str],
    scene_offset: float,
    scene_duration: float,
    chunk_size: int = 4,
) -> List[str]:
    """Respaldo proporcional a la longitud de cada palabra si no hay WordBoundary."""
    events: List[str] = []
    pop = r"{\fad(60,40)\fscx108\fscy108\t(0,120,\fscx100\fscy100)}"
    chunks = [words[i:i + chunk_size] for i in range(0, len(words), chunk_size)]
    weights = [sum(max(2, len(w)) for w in ch) for ch in chunks]
    total_weight = sum(weights) or 1

    cursor = scene_offset
    for chunk, ch_weight in zip(chunks, weights):
        ch_dur = scene_duration * (ch_weight / total_weight)
        start_t = cursor
        end_t = cursor + ch_dur
        cursor = end_t

        w_weights = [max(2, len(w)) for w in chunk]
        w_total = sum(w_weights) or 1
        karaoke = " ".join(
            f"{{\\k{max(1, int(round(ch_dur * (ww / w_total) * 100)))}}}{_escape_ass_text(w.upper())}"
            for w, ww in zip(chunk, w_weights)
        )
        events.append(
            f"Dialogue: 0,{format_ass_time(start_t)},{format_ass_time(end_t)},CyberSub,,0,0,0,,{pop}{karaoke}"
        )
    return events


def build_dynamic_ass_subtitles(
    scenes: List[Dict[str, Any]],
    ass_path: Path,
    theme: Optional[str] = None,
) -> None:
    """
    Subtítulos .ASS con efecto karaoke: bloques de ~4 palabras donde cada palabra
    se ilumina (blanco -> color del tema) sincronizada con la narración.
    """
    events: List[str] = []
    current_time = 0.0

    for scene in scenes:
        duration = float(scene.get("duration", 5.0))
        timings = scene.get("_word_timings") or []
        if timings:
            events.extend(_build_scene_events_from_timings(timings, current_time, duration))
        else:
            words = (scene.get("narration") or "").split()
            if words:
                events.extend(_build_scene_events_proportional(words, current_time, duration))
        current_time += duration

    ass_path.write_text(_ass_header(theme) + "\n".join(events) + "\n", encoding="utf-8")
