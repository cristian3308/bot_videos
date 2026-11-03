#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Aplicación FastAPI: panel profesional del generador de videos."""
from __future__ import annotations

import asyncio
import json
import re
import shutil
import unicodedata
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, Form, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from config.settings import settings
from core import llm, scheduler, store
from core.batch import run_batch
from core.pipeline import generate_plan, render_plan
from core.render import THEMES, generate_scene_html, render_scene_video_playwright
from core.tts import synthesize_sample, list_voices
from uploaders import tiktok, youtube

BASE = Path(__file__).resolve().parent
ASSETS_DIR = settings.project_root / "assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Cybercrime Studio")
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE / "templates"))

JOBS: Dict[str, Dict[str, Any]] = {}
ASSETS: Dict[str, str] = {}  # id -> ruta de archivo subido (música / logo)


# ---------------------------------------------------------------------------
# Modelos de petición
# ---------------------------------------------------------------------------
class ScriptRequest(BaseModel):
    topic: Optional[str] = None
    lang: str = "es"
    provider: Optional[str] = None
    model: Optional[str] = None
    num_scenes: Optional[int] = None
    target_seconds: Optional[int] = None
    previous_project: Optional[str] = None
    part: Optional[int] = 2
    style: Optional[str] = "auto"


class RenderRequest(BaseModel):
    plan: Dict[str, Any]
    lang: str = "es"
    voice: Optional[str] = None
    rate: str = "+8%"
    pitch: str = "-2Hz"
    theme: Optional[str] = "verde"
    music_id: Optional[str] = None
    logo_id: Optional[str] = None
    branding: bool = True
    part: Optional[int] = None
    music_mood: str = "dark"


class BatchRequest(BaseModel):
    count: int = 3
    source: str = "news"            # news | bank
    lang: str = "es"
    provider: Optional[str] = None
    model: Optional[str] = None
    theme: str = "verde"
    voice: Optional[str] = None
    rate: str = "+8%"
    pitch: str = "-2Hz"
    music_mood: str = "dark"
    branding: bool = True
    style: str = "auto"


class UploadRequest(BaseModel):
    job_id: Optional[str] = None
    project: Optional[str] = None


@app.on_event("startup")
async def _startup():
    scheduler.start()


# ---------------------------------------------------------------------------
# Páginas y estado
# ---------------------------------------------------------------------------
@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/api/status")
async def status():
    return {
        "ffmpeg_ready": settings.ffmpeg_ready(),
        "provider": settings.llm_provider,
        "default_voice": settings.default_voice("es"),
        "themes": list(THEMES.keys()),
        "providers": {
            "opencode": settings.provider_ready("opencode"),
            "gemini": settings.provider_ready("gemini"),
            "openai": settings.provider_ready("openai"),
            "ollama": True, "demo": True,
        },
        "youtube": {"configured": youtube.is_configured(), "connected": youtube.is_connected()},
        "tiktok": {"configured": tiktok.is_configured(), "connected": tiktok.is_connected()},
    }


@app.get("/api/opencode/models")
async def opencode_models():
    try:
        return {"models": await asyncio.to_thread(llm.list_opencode_models)}
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"error": str(exc)}, status_code=400)


@app.get("/api/voices")
async def voices(lang: str = "es"):
    prefix = "es" if lang == "es" else "en"
    return {"voices": await list_voices(prefix)}


@app.post("/api/voice/preview")
async def voice_preview(payload: Dict[str, Any]):
    voice = payload.get("voice") or settings.default_voice("es")
    rate = payload.get("rate", "+8%")
    pitch = payload.get("pitch", "-2Hz")
    text = payload.get("text") or "Esta es una muestra de la voz seleccionada para tu video."
    out = ASSETS_DIR / f"preview_{uuid.uuid4().hex[:8]}.mp3"
    try:
        await synthesize_sample(voice, out, text=text, rate=rate, pitch=pitch)
        return FileResponse(str(out), media_type="audio/mpeg")
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"error": str(exc)}, status_code=400)


# ---------------------------------------------------------------------------
# Subida de recursos (música / logo)
# ---------------------------------------------------------------------------
@app.post("/api/upload/music")
async def upload_music(file: UploadFile = File(...)):
    aid = uuid.uuid4().hex[:10]
    ext = Path(file.filename or "music.mp3").suffix or ".mp3"
    dest = ASSETS_DIR / f"music_{aid}{ext}"
    dest.write_bytes(await file.read())
    ASSETS[aid] = str(dest)
    return {"id": aid, "name": file.filename}


@app.post("/api/upload/logo")
async def upload_logo(file: UploadFile = File(...)):
    aid = uuid.uuid4().hex[:10]
    ext = Path(file.filename or "logo.png").suffix or ".png"
    dest = ASSETS_DIR / f"logo_{aid}{ext}"
    dest.write_bytes(await file.read())
    ASSETS[aid] = str(dest)
    return {"id": aid, "name": file.filename}


# ---------------------------------------------------------------------------
# FASE 1: generar guion (editable)
# ---------------------------------------------------------------------------
@app.post("/api/script/generate")
async def script_generate(req: ScriptRequest):
    previous = None
    if req.previous_project:
        plan = _load_project_plan(req.previous_project)
        if plan:
            previous = {
                "title": plan.get("title", ""),
                "description": plan.get("description", ""),
                "part": req.part or 2,
            }
    try:
        plan = await asyncio.to_thread(
            generate_plan, req.topic, req.lang, req.provider, req.model,
            req.num_scenes, req.target_seconds, previous, True, req.style,
        )
        return {"plan": plan}
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"error": str(exc)}, status_code=400)


# ---------------------------------------------------------------------------
# FASE 2: renderizar (fondo + progreso por websocket)
# ---------------------------------------------------------------------------
@app.post("/api/render")
async def render(req: RenderRequest):
    job_id = uuid.uuid4().hex[:12]
    job = {"id": job_id, "status": "running", "pct": 0, "stage": "inicio",
           "log": [], "result": None, "error": None, "queue": asyncio.Queue()}
    JOBS[job_id] = job

    async def progress(pct: int, stage: str, message: str):
        job["pct"], job["stage"] = pct, stage
        entry = {"pct": pct, "stage": stage, "message": message}
        job["log"].append(entry)
        await job["queue"].put(entry)

    music_path = ASSETS.get(req.music_id) if req.music_id else None
    logo_path = ASSETS.get(req.logo_id) if req.logo_id else None

    async def worker():
        try:
            result = await render_plan(
                req.plan, lang=req.lang, progress=progress,
                voice=req.voice, rate=req.rate, pitch=req.pitch, theme=req.theme,
                music_path=music_path, logo_path=logo_path,
                branding=req.branding, series_part=req.part, music_mood=req.music_mood,
            )
            job["result"], job["status"] = result, "done"
            await job["queue"].put({"pct": 100, "stage": "done", "message": "FIN", "result": result})
        except Exception as exc:  # noqa: BLE001
            job["status"], job["error"] = "error", str(exc)
            await job["queue"].put({"pct": job["pct"], "stage": "error", "message": str(exc), "error": True})

    asyncio.create_task(worker())
    return {"job_id": job_id}


@app.websocket("/ws/{job_id}")
async def ws_progress(websocket: WebSocket, job_id: str):
    await websocket.accept()
    job = JOBS.get(job_id)
    if not job:
        await websocket.send_json({"error": "job no encontrado"})
        await websocket.close()
        return
    for entry in list(job["log"]):
        await websocket.send_json(entry)
    if job["status"] in ("done", "error"):
        await websocket.send_json({"pct": job["pct"], "stage": job["status"],
                                   "message": "FIN", "result": job.get("result"),
                                   "error": job["status"] == "error"})
    try:
        while True:
            entry = await job["queue"].get()
            await websocket.send_json(entry)
            if entry.get("stage") in ("done", "error"):
                break
    except WebSocketDisconnect:
        pass
    finally:
        await websocket.close()


@app.get("/video/{job_id}")
async def video(job_id: str):
    job = JOBS.get(job_id)
    if not job or not job.get("result"):
        return JSONResponse({"error": "no disponible"}, status_code=404)
    return FileResponse(job["result"]["mp4"], media_type="video/mp4")


@app.get("/download/{job_id}")
async def download(job_id: str):
    job = JOBS.get(job_id)
    if not job or not job.get("result"):
        return JSONResponse({"error": "no disponible"}, status_code=404)
    path = Path(job["result"]["mp4"])
    return FileResponse(path, media_type="video/mp4", filename=path.name)


# ---------------------------------------------------------------------------
# Biblioteca
# ---------------------------------------------------------------------------
def _load_project_plan(project: str) -> Optional[Dict[str, Any]]:
    plan_file = settings.output_dir / project / "video_plan.json"
    if plan_file.exists():
        try:
            return json.loads(plan_file.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return None
    return None


def _series_key(title: str) -> tuple[str, str]:
    """Devuelve (clave_normalizada, título_base) quitando 'Parte N' para agrupar series."""
    t = title or ""
    base = re.sub(r"[\s\-:–|(]*\bparte\s*\d+\b[\s):]*", " ", t, flags=re.IGNORECASE)
    base = re.sub(r"[\s\-:–|(]*\bpt\.?\s*\d+\b[\s):]*", " ", base, flags=re.IGNORECASE)
    base = re.sub(r"\s+", " ", base).strip(" -:–|")
    key = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode().lower().strip()
    return (key or t.lower(), base or t)


def _part_num(title: str) -> int:
    m = (re.search(r"\bparte\s*(\d+)\b", title or "", re.IGNORECASE)
         or re.search(r"\bpt\.?\s*(\d+)\b", title or "", re.IGNORECASE))
    return int(m.group(1)) if m else 1


@app.get("/api/library")
async def library():
    items: List[Dict[str, Any]] = []
    for d in sorted(settings.output_dir.glob("cyber_video_*"), reverse=True):
        mp4 = d / "video_final.mp4"
        if not mp4.exists():
            continue
        plan = _load_project_plan(d.name) or {}
        ts = d.name.replace("cyber_video_", "")
        try:
            fecha = datetime.strptime(ts, "%Y%m%d_%H%M%S").strftime("%d/%m/%Y %H:%M")
        except ValueError:
            fecha = ts
        title = plan.get("title", d.name)
        items.append({
            "project": d.name,
            "title": title,
            "date": fecha,
            "part": _part_num(title),
            "has_thumb": (d / "thumb.jpg").exists(),
            "has_thumb_yt": (d / "thumb_youtube.jpg").exists(),
            "video_url": f"/library/video/{d.name}",
            "thumb_url": f"/thumb/{d.name}",
            "thumb_yt_url": f"/thumb_yt/{d.name}",
        })

    # Agrupar en series por título base
    groups: Dict[str, Dict[str, Any]] = {}
    for it in items:
        key, base = _series_key(it["title"])
        g = groups.setdefault(key, {"title": base, "parts": []})
        g["parts"].append(it)
    series: List[Dict[str, Any]] = []
    for g in groups.values():
        g["parts"].sort(key=lambda x: (x["part"], x["project"]))
        g["count"] = len(g["parts"])
        series.append(g)
    series.sort(key=lambda g: max(p["project"] for p in g["parts"]), reverse=True)

    return {"series": series, "items": items}


@app.get("/thumb_yt/{project}")
async def thumb_yt(project: str):
    p = settings.output_dir / project / "thumb_youtube.jpg"
    if not p.exists():
        return JSONResponse({"error": "sin miniatura"}, status_code=404)
    return FileResponse(str(p), media_type="image/jpeg")


# ---------------------------------------------------------------------------
# Automatización: lote, banco de temas y programador
# ---------------------------------------------------------------------------
@app.post("/api/batch")
async def batch(req: BatchRequest):
    job_id = uuid.uuid4().hex[:12]
    job = {"id": job_id, "status": "running", "pct": 0, "stage": "lote",
           "log": [], "result": None, "error": None, "queue": asyncio.Queue()}
    JOBS[job_id] = job

    async def progress(pct: int, stage: str, message: str):
        job["pct"], job["stage"] = pct, stage
        entry = {"pct": pct, "stage": stage, "message": message}
        job["log"].append(entry)
        await job["queue"].put(entry)

    async def worker():
        try:
            results = await run_batch(
                count=req.count, source=req.source, lang=req.lang, provider=req.provider,
                model=req.model, theme=req.theme, voice=req.voice, rate=req.rate, pitch=req.pitch,
                music_mood=req.music_mood, branding=req.branding, style=req.style, progress=progress,
            )
            job["result"], job["status"] = {"videos": results}, "done"
            await job["queue"].put({"pct": 100, "stage": "done", "message": "FIN", "result": {"videos": results}})
        except Exception as exc:  # noqa: BLE001
            job["status"], job["error"] = "error", str(exc)
            await job["queue"].put({"pct": job["pct"], "stage": "error", "message": str(exc), "error": True})

    asyncio.create_task(worker())
    return {"job_id": job_id}


@app.get("/api/topics")
async def topics_list():
    return {"topics": store.load_topics()}


@app.post("/api/topics")
async def topics_add(payload: Dict[str, Any]):
    return {"topics": store.add_topic(payload.get("topic", ""))}


@app.delete("/api/topics")
async def topics_remove(payload: Dict[str, Any]):
    return {"topics": store.remove_topic(payload.get("topic", ""))}


@app.get("/api/scheduler")
async def scheduler_get():
    return store.load_sched()


@app.post("/api/scheduler")
async def scheduler_set(payload: Dict[str, Any]):
    return store.save_sched(payload or {})


@app.post("/api/scene/preview")
async def scene_preview(payload: Dict[str, Any]):
    """Renderiza SOLO una escena (sin audio, ~4.5s) para previsualizar su aspecto."""
    scene = payload.get("scene") or {}
    theme = payload.get("theme") or "verde"
    try:
        html = generate_scene_html(scene, total_scenes=1, theme=theme)
        html_file = ASSETS_DIR / f"scene_prev_{uuid.uuid4().hex[:8]}.html"
        mp4_file = ASSETS_DIR / f"scene_prev_{uuid.uuid4().hex[:8]}.mp4"
        html_file.write_text(html, encoding="utf-8")
        await render_scene_video_playwright(html_file, 4.5, mp4_file)
        return FileResponse(str(mp4_file), media_type="video/mp4")
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"error": str(exc)}, status_code=400)


@app.delete("/api/library/{project}")
async def library_delete(project: str):
    """Borra un video de la biblioteca (solo carpetas cyber_video_* dentro de output)."""
    if not project.startswith("cyber_video_") or "/" in project or "\\" in project or ".." in project:
        return JSONResponse({"error": "proyecto inválido"}, status_code=400)
    target = (settings.output_dir / project).resolve()
    if settings.output_dir.resolve() not in target.parents:
        return JSONResponse({"error": "ruta fuera de la biblioteca"}, status_code=400)
    shutil.rmtree(target, ignore_errors=True)
    return {"status": "deleted", "project": project}


@app.get("/thumb/{project}")
async def thumb(project: str):
    p = settings.output_dir / project / "thumb.jpg"
    if not p.exists():
        return JSONResponse({"error": "sin miniatura"}, status_code=404)
    return FileResponse(str(p), media_type="image/jpeg")


@app.get("/library/video/{project}")
async def library_video(project: str):
    p = settings.output_dir / project / "video_final.mp4"
    if not p.exists():
        return JSONResponse({"error": "no existe"}, status_code=404)
    return FileResponse(str(p), media_type="video/mp4")


# ---------------------------------------------------------------------------
# Cuentas y subida
# ---------------------------------------------------------------------------
def _resolve_upload(req: UploadRequest) -> Optional[Dict[str, str]]:
    if req.job_id:
        job = JOBS.get(req.job_id)
        if job and job.get("result"):
            return job["result"]
    if req.project:
        plan = _load_project_plan(req.project) or {}
        mp4 = settings.output_dir / req.project / "video_final.mp4"
        if mp4.exists():
            return {"mp4": str(mp4), "title": plan.get("title", req.project),
                    "description": plan.get("description", "")}
    return None


@app.post("/auth/youtube/connect")
async def youtube_connect():
    try:
        await asyncio.to_thread(youtube.connect)
        return {"status": "connected"}
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"error": str(exc)}, status_code=400)


@app.post("/api/upload/youtube")
async def upload_youtube(req: UploadRequest):
    r = _resolve_upload(req)
    if not r:
        return JSONResponse({"error": "video no disponible"}, status_code=404)
    try:
        return await asyncio.to_thread(youtube.upload, r["mp4"], r["title"], r["description"])
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"error": str(exc)}, status_code=400)


@app.get("/auth/tiktok/connect")
async def tiktok_connect(request: Request):
    redirect_uri = str(request.base_url).rstrip("/") + "/auth/tiktok/callback"
    try:
        return RedirectResponse(tiktok.connect_url(redirect_uri))
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"error": str(exc)}, status_code=400)


@app.get("/auth/tiktok/callback")
async def tiktok_callback(request: Request, code: str = "", state: str = ""):
    redirect_uri = str(request.base_url).rstrip("/") + "/auth/tiktok/callback"
    try:
        tiktok.exchange_code(code, redirect_uri)
        return RedirectResponse("/?tiktok=connected")
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"error": str(exc)}, status_code=400)


@app.post("/api/upload/tiktok")
async def upload_tiktok(req: UploadRequest):
    r = _resolve_upload(req)
    if not r:
        return JSONResponse({"error": "video no disponible"}, status_code=404)
    try:
        return await asyncio.to_thread(tiktok.upload, r["mp4"], r["title"])
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"error": str(exc)}, status_code=400)
