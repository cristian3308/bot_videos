#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ensamblador final con FFmpeg: une escenas, audio (música propia o Dark Synth), subtítulos y logo."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import List, Optional

from config.settings import settings
from core.tts import get_audio_duration


def format_ffmpeg_filter_path(path: Path) -> str:
    """Escapa rutas para el filtro `subtitles`/`ass` de FFmpeg en Windows y Linux."""
    resolved = str(path.resolve())
    if os.name == "nt":
        resolved = resolved.replace("\\", "/")
        resolved = resolved.replace(":", "\\:")
    return resolved


def _ffmpeg() -> str:
    return settings.ffmpeg or "ffmpeg"


# Ambientes musicales procedurales (sin copyright), sintetizados por FFmpeg.
MUSIC_MOODS = {
    "dark": "0.06*sin(2*PI*55*t)+0.03*sin(2*PI*110*t)*(0.5+0.5*sin(2*PI*0.5*t))",
    "tense": "0.05*sin(2*PI*73*t)+0.04*sin(2*PI*146*t)*(0.5+0.5*sin(2*PI*2*t))",
    "action": "0.05*sin(2*PI*65*t)*(0.6+0.4*sin(2*PI*4*t))+0.03*sin(2*PI*196*t)",
    "suspense": "0.07*sin(2*PI*48*t)*(0.5+0.5*sin(2*PI*0.25*t))",
}


def assemble_final_video(
    scene_videos: List[Path],
    scene_audios: List[Path],
    ass_subtitles: Path,
    output_mp4: Path,
    work_dir: Path,
    music_path: Optional[Path] = None,
    logo_path: Optional[Path] = None,
    music_mood: str = "dark",
) -> None:
    """
    Une clips de video/voz, añade música de fondo (archivo propio con DUCKING, o ambiente
    procedural según el mood), quema los subtítulos .ASS y superpone un logo opcional.
    """
    v_list_file = work_dir / "videos_concat.txt"
    a_list_file = work_dir / "audios_concat.txt"
    v_list_file.write_text("\n".join(f"file '{p.resolve().as_posix()}'" for p in scene_videos), encoding="utf-8")
    a_list_file.write_text("\n".join(f"file '{p.resolve().as_posix()}'" for p in scene_audios), encoding="utf-8")

    merged_video = work_dir / "merged_visuals.mp4"
    merged_voice = work_dir / "merged_voice.mp3"
    subprocess.run([_ffmpeg(), "-y", "-f", "concat", "-safe", "0", "-i", str(v_list_file), "-c", "copy", str(merged_video)],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run([_ffmpeg(), "-y", "-f", "concat", "-safe", "0", "-i", str(a_list_file), "-c", "copy", str(merged_voice)],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    total_duration = get_audio_duration(merged_voice)
    escaped_ass = format_ffmpeg_filter_path(ass_subtitles)

    # --- Construir inputs y filtros dinámicamente ---
    inputs: List[str] = ["-i", str(merged_video), "-i", str(merged_voice)]
    idx = 2  # 0=video, 1=voz

    use_file_music = bool(music_path and Path(music_path).exists())
    if use_file_music:
        inputs += ["-stream_loop", "-1", "-i", str(music_path)]
    else:
        synth = MUSIC_MOODS.get(music_mood, MUSIC_MOODS["dark"])
        inputs += ["-f", "lavfi", "-i", f"aevalsrc='{synth}':s=44100:d={total_duration:.2f}"]
    music_idx = idx
    idx += 1

    logo_idx = None
    if logo_path and Path(logo_path).exists():
        inputs += ["-i", str(logo_path)]
        logo_idx = idx
        idx += 1

    if use_file_music:
        # DUCKING: la música baja automáticamente cuando hay narración (sidechaincompress).
        audio_filter = (
            f"[1:a]volume=1.0,asplit=2[v1][v2];"
            f"[{music_idx}:a]volume=0.5[mraw];"
            f"[mraw][v2]sidechaincompress=threshold=0.02:ratio=10:attack=15:release=400[mduck];"
            f"[v1][mduck]amix=inputs=2:duration=first:dropout_transition=0[aout]"
        )
    else:
        audio_filter = (
            f"[1:a]volume=1.0[voice];[{music_idx}:a]lowpass=f=280[bg];"
            f"[voice][bg]amix=inputs=2:duration=first:dropout_transition=0[aout]"
        )
    if logo_idx is not None:
        video_filter = (
            f"[0:v]ass='{escaped_ass}'[subbed];"
            f"[{logo_idx}:v]scale=200:-1[lg];"
            f"[subbed][lg]overlay=W-w-40:40[vout]"
        )
        vmap = "[vout]"
    else:
        video_filter = f"[0:v]ass='{escaped_ass}'[vout]"
        vmap = "[vout]"

    cmd_final = [_ffmpeg(), "-y", *inputs,
                 "-filter_complex", f"{audio_filter};{video_filter}",
                 "-map", vmap, "-map", "[aout]",
                 "-c:v", "libx264", "-preset", "medium", "-crf", "19",
                 "-c:a", "aac", "-b:a", "192k", "-shortest", str(output_mp4)]
    subprocess.run(cmd_final, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def generate_thumbnail(mp4_path: Path, out_jpg: Path, at_sec: float = 1.0) -> Optional[Path]:
    """Extrae un fotograma como miniatura para la biblioteca."""
    try:
        subprocess.run(
            [settings.ffmpeg or "ffmpeg", "-y", "-ss", f"{at_sec:.2f}", "-i", str(mp4_path),
             "-frames:v", "1", "-vf", "scale=360:-1", str(out_jpg)],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return out_jpg if out_jpg.exists() else None
    except Exception:  # noqa: BLE001
        return None
