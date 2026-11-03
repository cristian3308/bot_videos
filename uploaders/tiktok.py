#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Subida automática a TikTok (Content Posting API).

IMPORTANTE:
  - Necesitas registrar una app en https://developers.tiktok.com/ y añadir el producto
    "Content Posting API". Hasta que TikTok apruebe tu app para publicación directa,
    los videos se suben como BORRADOR al buzón de la cuenta y tú los publicas desde la
    app de TikTok (modo "upload", no "direct post"). Esto es lo normal al empezar.
  - El token de acceso se obtiene con el login OAuth (connect_url + exchange_code).

Este módulo implementa el flujo de subida por carga directa del archivo (FILE_UPLOAD).
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, Optional

import requests

from config.settings import settings

AUTH_BASE = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
INIT_UPLOAD_URL = "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/"
SCOPES = "user.info.basic,video.upload"


def _token_path() -> Path:
    return settings.path(settings.tiktok_token_file)


def is_configured() -> bool:
    return bool(settings.tiktok_client_key and settings.tiktok_client_secret)


def is_connected() -> bool:
    return _token_path().exists()


def connect_url(redirect_uri: str, state: str = "creador") -> str:
    """Devuelve la URL de autorización de TikTok para que el usuario inicie sesión."""
    if not is_configured():
        raise RuntimeError("Faltan TIKTOK_CLIENT_KEY / TIKTOK_CLIENT_SECRET en el .env")
    from urllib.parse import urlencode

    params = {
        "client_key": settings.tiktok_client_key,
        "scope": SCOPES,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "state": state,
    }
    return AUTH_BASE + "?" + urlencode(params)


def exchange_code(code: str, redirect_uri: str) -> Dict:
    """Intercambia el 'code' del callback por un access_token y lo guarda."""
    resp = requests.post(
        TOKEN_URL,
        data={
            "client_key": settings.tiktok_client_key,
            "client_secret": settings.tiktok_client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    resp.raise_for_status()
    tok = resp.json()
    tok["obtained_at"] = int(time.time())
    path = _token_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tok, indent=2), encoding="utf-8")
    return {"status": "connected"}


def _access_token() -> str:
    path = _token_path()
    if not path.exists():
        raise RuntimeError("TikTok no está conectado. Conéctalo desde el panel.")
    tok = json.loads(path.read_text(encoding="utf-8"))
    return tok["access_token"]


def upload(video_path: str, title: Optional[str] = None) -> Dict[str, str]:
    """
    Sube el video al buzón de la cuenta (borrador). Devuelve el publish_id.
    El usuario finaliza la publicación desde la app de TikTok.
    """
    token = _access_token()
    size = Path(video_path).stat().st_size

    init = requests.post(
        INIT_UPLOAD_URL,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        data=json.dumps({
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": size,
                "chunk_size": size,
                "total_chunk_count": 1,
            }
        }),
        timeout=60,
    )
    init.raise_for_status()
    data = init.json()["data"]
    upload_url = data["upload_url"]
    publish_id = data["publish_id"]

    with open(video_path, "rb") as fh:
        put = requests.put(
            upload_url,
            headers={
                "Content-Type": "video/mp4",
                "Content-Length": str(size),
                "Content-Range": f"bytes 0-{size - 1}/{size}",
            },
            data=fh.read(),
            timeout=300,
        )
    put.raise_for_status()

    return {
        "publish_id": publish_id,
        "status": "subido_como_borrador",
        "note": "Abre la app de TikTok para revisar y publicar el video.",
    }
