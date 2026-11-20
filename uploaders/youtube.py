#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Subida automática a YouTube (YouTube Data API v3) con OAuth de escritorio.

Flujo:
  1. El usuario crea un "ID de cliente OAuth -> App de escritorio" en Google Cloud
     y descarga el JSON a credentials/youtube_client_secret.json (ver .env.example).
  2. La primera vez, connect() abre el navegador para autorizar y guarda el token.
  3. upload() sube el MP4 como Short y devuelve la URL del video.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from config.settings import settings

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _paths() -> tuple[Path, Path]:
    return settings.path(settings.youtube_client_secret_file), settings.path(settings.youtube_token_file)


def is_configured() -> bool:
    client_secret, _ = _paths()
    return client_secret.exists()


def is_connected() -> bool:
    _, token = _paths()
    return token.exists()


def _load_credentials(allow_interactive: bool):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    client_secret, token_file = _paths()
    creds = None
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)

    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_file.write_text(creds.to_json(), encoding="utf-8")
        return creds

    if not allow_interactive:
        raise RuntimeError("YouTube no está conectado. Pulsa 'Conectar YouTube' en el panel.")
    if not client_secret.exists():
        raise RuntimeError(
            f"No existe {client_secret}. Descarga el JSON de OAuth de Google Cloud "
            "(ver instrucciones en .env.example)."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(creds.to_json(), encoding="utf-8")
    return creds


def connect() -> Dict[str, str]:
    """Lanza el flujo OAuth interactivo (abre el navegador) y guarda el token."""
    _load_credentials(allow_interactive=True)
    return {"status": "connected"}


def upload(
    video_path: str,
    title: str,
    description: str,
    tags: Optional[List[str]] = None,
    privacy: Optional[str] = None,
    thumbnail_path: Optional[str] = None,
) -> Dict[str, str]:
    """Sube el video a YouTube (y opcionalmente su miniatura) y devuelve {'video_id', 'url'}."""
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    creds = _load_credentials(allow_interactive=False)
    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": tags or ["ciberseguridad", "hacking", "tech", "shorts"],
            "categoryId": "28",  # Ciencia y tecnología
        },
        "status": {
            "privacyStatus": privacy or settings.youtube_privacy,
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        _status, response = request.next_chunk()

    video_id = response["id"]
    thumb_note = ""
    if thumbnail_path and Path(thumbnail_path).exists():
        try:
            thumb_media = MediaFileUpload(thumbnail_path, mimetype="image/jpeg")
            youtube.thumbnails().set(videoId=video_id, media_body=thumb_media).execute()
            thumb_note = "ok"
        except Exception as exc:  # noqa: BLE001
            # Canales sin verificación telefónica o Shorts pueden rechazar miniaturas custom
            thumb_note = f"omitida ({exc})"

    out = {"video_id": video_id, "url": f"https://youtu.be/{video_id}"}
    if thumb_note:
        out["thumbnail"] = thumb_note
    return out
