#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Orquestador del pipeline. Separado en dos fases: generar guion y renderizar."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from config.settings import settings
from core.assemble import assemble_final_video, generate_thumbnail
from core.llm import generate_script
from core.render import generate_scene_html, generate_youtube_thumbnail, render_scene_video_playwright
from core.subtitles import build_dynamic_ass_subtitles
from core.tts import DEFAULT_PITCH, DEFAULT_RATE, synthesize_scene_audio

ProgressCB = Optional[Callable[[int, str, str], Any]]


async def _emit(cb: ProgressCB, pct: int, stage: str, message: str) -> None:
    print(f"[{pct:3d}%] ({stage}) {message}")
    if cb is None:
        return
    result = cb(pct, stage, message)
    if asyncio.iscoroutine(result):
        await result


# ---------------------------------------------------------------------------
# FASE 1: Guion
# ---------------------------------------------------------------------------
def generate_plan(
    topic: Optional[str] = None,
    lang: str = "es",
    provider: Optional[str] = None,
    model: Optional[str] = None,
    num_scenes: Optional[int] = None,
    target_seconds: Optional[int] = None,
    previous: Optional[Dict[str, Any]] = None,
    raise_on_error: bool = False,
    style: Optional[str] = None,
    style_index: Optional[int] = None,
) -> Dict[str, Any]:
    """Genera solo el guion (JSON) aplicando el estilo (tono + tema + mood sugeridos)."""
    from core.styles import resolve
    style_name, s = resolve(style, topic, style_index)
    plan = generate_script(
        topic=topic, lang=lang, provider=provider, model=model,
        num_scenes=num_scenes, target_seconds=target_seconds, previous=previous,
        raise_on_error=raise_on_error, tone=s["tone"],
    )
    plan["_style"] = style_name
    plan["_theme"] = s["theme"]
    plan["_mood"] = s["mood"]
    return plan


# ---------------------------------------------------------------------------
# FASE 2: Render
# ---------------------------------------------------------------------------
async def render_plan(
    video_plan: Dict[str, Any],
    lang: str = "es",
    out_dir: Optional[Path] = None,
    progress: ProgressCB = None,
    voice: Optional[str] = None,
    rate: str = DEFAULT_RATE,
    pitch: str = DEFAULT_PITCH,
    theme: Optional[str] = None,
    music_path: Optional[Path] = None,
    logo_path: Optional[Path] = None,
    branding: bool = True,
    series_part: Optional[int] = None,
    music_mood: str = "dark",
) -> Dict[str, Any]:
    """Renderiza el video a partir de un plan (guion) ya generado o editado."""
    if not settings.ffmpeg_ready():
        raise RuntimeError("FFmpeg no está disponible. Instálalo o define FFMPEG_PATH en el .env.")

    out_dir = out_dir or settings.output_dir
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    project_dir = out_dir / f"cyber_video_{timestamp}"
    work_dir = project_dir / "temp_build"
    work_dir.mkdir(parents=True, exist_ok=True)

    plan_path = project_dir / "video_plan.json"
    plan_path.write_text(json.dumps(video_plan, indent=2, ensure_ascii=False), encoding="utf-8")

    voice = voice or video_plan.get("voice") or settings.default_voice(lang)
    scenes: List[Dict[str, Any]] = list(video_plan.get("scenes", []))
    if not scenes:
        raise RuntimeError("El guion no contiene escenas.")

    # Intro + outro de marca automáticos (opcional)
    if branding:
        title = (video_plan.get("title") or "CYBERCRIME STUDIO").strip()
        intro = {
            "scene_type": "brand", "headline": title[:60], "badge": "CYBERCRIME STUDIO",
            "subtitle": "Caso real de ciberseguridad", "narration": title,
        }
        outro_badge = f"PARTE {series_part + 1} PRONTO" if series_part else "SÍGUEME"
        outro = {
            "scene_type": "brand", "headline": "SÍGUEME PARA MÁS", "badge": outro_badge,
            "subtitle": "Más historias reales de hackers",
            "narration": "Si te sirvió, sígueme para la siguiente historia real de ciberseguridad.",
        }
        scenes = [intro] + scenes + [outro]

    for i, s in enumerate(scenes, start=1):
        s["id"] = i
    video_plan["scenes"] = scenes
    total = len(scenes)

    scene_videos: List[Path] = []
    scene_audios: List[Path] = []

    # --- Paso 1: sintetizar toda la voz para conocer las duraciones (y la barra de progreso) ---
    for i, scene in enumerate(scenes, start=1):
        await _emit(progress, 10 + int((i - 1) / total * 25), "voz", f"Narrando escena {i}/{total}...")
        audio_file = work_dir / f"scene_{i:02d}.mp3"
        scene["duration"] = await synthesize_scene_audio(scene.get("narration", ""), voice, audio_file, rate, pitch)
        scene_audios.append(audio_file)

    total_dur = sum(float(s.get("duration", 0)) for s in scenes) or 1.0

    # --- Paso 2: renderizar cada escena con su posición en la barra de progreso ---
    elapsed = 0.0
    for i, scene in enumerate(scenes, start=1):
        dur = float(scene.get("duration", 5.0))
        prog_start, prog_end = elapsed / total_dur, (elapsed + dur) / total_dur
        elapsed += dur
        await _emit(progress, 35 + int((i - 1) / total * 45), "escena",
                    f"Grabando escena {i}/{total} [{scene.get('scene_type')}] ({dur:.1f}s)...")
        html_file = work_dir / f"scene_{i:02d}.html"
        video_file = work_dir / f"scene_{i:02d}.mp4"
        html_file.write_text(
            generate_scene_html(scene, total_scenes=total, theme=theme, prog_start=prog_start, prog_end=prog_end),
            encoding="utf-8",
        )
        await render_scene_video_playwright(html_file, dur, video_file)
        scene_videos.append(video_file)

    await _emit(progress, 83, "subtitulos", "Generando subtítulos dinámicos .ASS...")
    ass_file = work_dir / "subtitles.ass"
    build_dynamic_ass_subtitles(scenes, ass_file)

    await _emit(progress, 88, "ensamblaje", "Ensamblando MP4 final con FFmpeg...")
    final_mp4 = project_dir / "video_final.mp4"
    await asyncio.to_thread(
        assemble_final_video, scene_videos, scene_audios, ass_file, final_mp4, work_dir,
        Path(music_path) if music_path else None,
        Path(logo_path) if logo_path else None,
        music_mood,
    )

    # Miniatura para la biblioteca (fotograma) + miniatura estilo YouTube (1280x720)
    thumb = project_dir / "thumb.jpg"
    await asyncio.to_thread(generate_thumbnail, final_mp4, thumb, 1.0)
    await _emit(progress, 95, "miniatura", "Generando miniatura de YouTube...")
    thumb_yt = project_dir / "thumb_youtube.jpg"
    await generate_youtube_thumbnail(video_plan.get("title", ""), thumb_yt, theme=theme)

    meta_txt = project_dir / "metadatos_publicacion.txt"
    meta_txt.write_text(
        f"TÍTULO:\n{video_plan.get('title')}\n\n"
        f"DESCRIPCIÓN:\n{video_plan.get('description')}\n\n"
        "CHECKLIST DE SUBIDA (YOUTUBE / TIKTOK):\n"
        "- Marcar 'Contenido alterado o sintético' solo si usas rostros realistas.\n"
        "- Duración > 60s para TikTok Creator Rewards y YouTube Shorts.\n",
        encoding="utf-8",
    )
    # Guardar el plan actualizado (con duraciones) para series "Parte 2"
    plan_path.write_text(json.dumps(video_plan, indent=2, ensure_ascii=False), encoding="utf-8")

    await _emit(progress, 100, "listo", "¡Video completado!")
    return {
        "mp4": str(final_mp4.resolve()),
        "plan_json": str(plan_path.resolve()),
        "metadata_txt": str(meta_txt.resolve()),
        "thumb": str(thumb.resolve()) if thumb.exists() else None,
        "thumb_youtube": str(thumb_yt.resolve()) if thumb_yt.exists() else None,
        "project_dir": str(project_dir.resolve()),
        "project": project_dir.name,
        "title": video_plan.get("title", ""),
        "description": video_plan.get("description", ""),
    }


# ---------------------------------------------------------------------------
# One-shot (CLI): guion + render juntos
# ---------------------------------------------------------------------------
async def run_pipeline(
    topic: Optional[str] = None,
    lang: str = "es",
    provider: Optional[str] = None,
    out_dir: Optional[Path] = None,
    progress: ProgressCB = None,
    model: Optional[str] = None,
    num_scenes: Optional[int] = None,
    target_seconds: Optional[int] = None,
    voice: Optional[str] = None,
    rate: str = DEFAULT_RATE,
    pitch: str = DEFAULT_PITCH,
    theme: Optional[str] = None,
    music_path: Optional[Path] = None,
    logo_path: Optional[Path] = None,
    previous: Optional[Dict[str, Any]] = None,
    branding: bool = True,
) -> Dict[str, Any]:
    await _emit(progress, 5, "guion", f"Generando guion con proveedor '{provider or settings.llm_provider}'...")
    plan = await asyncio.to_thread(
        generate_plan, topic, lang, provider, model, num_scenes, target_seconds, previous
    )
    await _emit(progress, 10, "guion", f"Título: {plan.get('title')}")
    return await render_plan(
        plan, lang=lang, out_dir=out_dir, progress=progress,
        voice=voice, rate=rate, pitch=pitch, theme=theme,
        music_path=music_path, logo_path=logo_path, branding=branding,
        series_part=(previous or {}).get("part") if previous else None,
    )
