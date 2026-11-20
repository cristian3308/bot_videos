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
import secrets
import time
from pathlib import Path
from typing import Dict, Optional, Set

import requests

from config.settings import settings

AUTH_BASE = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
INIT_UPLOAD_URL = "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/"
SCOPES = "user.info.basic,video.upload"

_PENDING_STATES: Set[str] = set()


def _token_path() -> Path:
    return settings.path(settings.tiktok_token_file)


def _check_tiktok_error(payload: Dict) -> None:
    """TikTok puede devolver HTTP 200 con error en el JSON (`error.code != 'ok'`)."""
    err = payload.get("error")
    if isinstance(err, dict):
        code = str(err.get("code") or "").strip().lower()
        if code and code != "ok":
            msg = err.get("message") or code
            raise RuntimeError(f"Error de TikTok API [{code}]: {msg}")
    elif isinstance(err, str) and err.strip():
        desc = payload.get("error_description") or err
        raise RuntimeError(f"Error OAuth de TikTok: {desc}")


def is_configured() -> bool:
    return bool(settings.tiktok_client_key and settings.tiktok_client_secret)


def is_connected() -> bool:
    return _token_path().exists()


def connect_url(redirect_uri: str, state: Optional[str] = None) -> str:
    """Devuelve la URL de autorización de TikTok con un parámetro state anti-CSRF."""
    if not is_configured():
        raise RuntimeError("Faltan TIKTOK_CLIENT_KEY / TIKTOK_CLIENT_SECRET en el .env")
    from urllib.parse import urlencode

    st = state or secrets.token_urlsafe(24)
    _PENDING_STATES.add(st)
    if len(_PENDING_STATES) > 50:
        _PENDING_STATES.clear()
        _PENDING_STATES.add(st)

    params = {
        "client_key": settings.tiktok_client_key,
        "scope": SCOPES,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "state": st,
    }
    return AUTH_BASE + "?" + urlencode(params)


def verify_state(state: str) -> bool:
    """Verifica y consume el parámetro state de OAuth (anti-CSRF)."""
    if not state or state not in _PENDING_STATES:
        return False
    _PENDING_STATES.discard(state)
    return True


def _save_token(tok: Dict) -> None:
    tok["obtained_at"] = int(time.time())
    path = _token_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tok, indent=2), encoding="utf-8")


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
    _check_tiktok_error(tok)
    if "access_token" not in tok:
        raise RuntimeError("TikTok no devolvió access_token en el intercambio OAuth.")
    _save_token(tok)
    return {"status": "connected"}


def _refresh_access_token(refresh_token: str) -> str:
    """Renueva el access_token de TikTok usando el refresh_token almacenado."""
    resp = requests.post(
        TOKEN_URL,
        data={
            "client_key": settings.tiktok_client_key,
            "client_secret": settings.tiktok_client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    resp.raise_for_status()
    tok = resp.json()
    _check_tiktok_error(tok)
    if "access_token" not in tok:
        raise RuntimeError("No se pudo renovar el token de TikTok. Reconecta tu cuenta en el panel.")
    _save_token(tok)
    return tok["access_token"]


def _access_token() -> str:
    path = _token_path()
    if not path.exists():
        raise RuntimeError("TikTok no está conectado. Conéctalo desde el panel.")
    tok = json.loads(path.read_text(encoding="utf-8"))
    obtained_at = int(tok.get("obtained_at", 0))
    expires_in = int(tok.get("expires_in", 86400))
    # Si falta menos de 60s para expirar y hay refresh_token, renovar automáticamente
    if obtained_at and time.time() >= (obtained_at + expires_in - 60):
        refresh = tok.get("refresh_token")
        if refresh and is_configured():
            return _refresh_access_token(refresh)
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
    payload = init.json()
    _check_tiktok_error(payload)
    data = payload["data"]
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
