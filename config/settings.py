#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuración central del proyecto.

Carga las variables del archivo .env (si existe), expone rutas absolutas
multiplataforma y localiza los binarios de FFmpeg tanto en Windows como en Linux.
Importa `settings` desde cualquier módulo:  from config.settings import settings
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
except ImportError:  # dotenv es opcional; si no está, se usan solo variables de entorno
    def load_dotenv(*_args, **_kwargs):  # type: ignore
        return False

# Raíz del proyecto = carpeta que contiene a config/
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Cargar .env desde la raíz del proyecto
load_dotenv(PROJECT_ROOT / ".env")


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


def _env_bool(key: str, default: bool) -> bool:
    raw = _env(key)
    if not raw:
        return default
    return raw.lower() in ("1", "true", "yes", "on", "si", "sí")


def _env_int(key: str, default: int, lo: int = 1, hi: int = 64) -> int:
    try:
        val = int(_env(key) or default)
    except ValueError:
        val = default
    return max(lo, min(hi, val))


def _resolve_ffmpeg(name: str, override_dir: str) -> Optional[str]:
    """Busca ffmpeg/ffprobe en una ruta configurada o en el PATH del sistema."""
    exe = name + (".exe" if os.name == "nt" else "")
    if override_dir:
        candidate = Path(override_dir) / exe
        if candidate.exists():
            return str(candidate)
        # Quizá apuntaron directamente al binario de ffmpeg
        candidate_bin = Path(override_dir)
        if candidate_bin.is_file():
            return str(candidate_bin.parent / exe)
    return shutil.which(name)


@dataclass
class Settings:
    # --- Rutas ---
    project_root: Path = PROJECT_ROOT
    output_dir: Path = field(default_factory=lambda: PROJECT_ROOT / _env("OUTPUT_DIR", "output_videos"))
    credentials_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "credentials")

    # --- Motor de guion (LLM) ---
    llm_provider: str = field(default_factory=lambda: _env("VIDEO_LLM_PROVIDER", "demo").lower())

    opencode_api_key: str = field(default_factory=lambda: _env("OPENCODE_API_KEY"))
    opencode_model: str = field(default_factory=lambda: _env("OPENCODE_MODEL", "glm-5.3"))
    # Plan OpenCode Go: el chat y la lista de modelos usan rutas distintas.
    opencode_base_url: str = field(default_factory=lambda: _env("OPENCODE_BASE_URL", "https://opencode.ai/inference/go/openai/v1"))
    opencode_models_url: str = field(default_factory=lambda: _env("OPENCODE_MODELS_URL", "https://opencode.ai/inference/go/v1/models"))

    gemini_api_key: str = field(default_factory=lambda: _env("GEMINI_API_KEY"))
    gemini_model: str = field(default_factory=lambda: _env("GEMINI_MODEL", "gemini-2.5-flash"))

    openai_api_key: str = field(default_factory=lambda: _env("OPENAI_API_KEY"))
    openai_model: str = field(default_factory=lambda: _env("OPENAI_MODEL", "gpt-4o-mini"))
    openai_base_url: str = field(default_factory=lambda: _env("OPENAI_BASE_URL", "https://api.openai.com/v1"))

    ollama_base_url: str = field(default_factory=lambda: _env("OLLAMA_BASE_URL", "http://localhost:11434"))
    ollama_model: str = field(default_factory=lambda: _env("OLLAMA_MODEL", "llama3.1"))

    # --- Identidad del canal ---
    brand_name: str = field(default_factory=lambda: _env("BRAND_NAME", "DÍA CERO"))
    brand_tagline_es: str = field(default_factory=lambda: _env("BRAND_TAGLINE_ES", "Caso real de ciberseguridad"))
    brand_tagline_en: str = field(default_factory=lambda: _env("BRAND_TAGLINE_EN", "Real cybersecurity case"))

    # --- YouTube ---
    youtube_client_secret_file: str = field(default_factory=lambda: _env("YOUTUBE_CLIENT_SECRET_FILE", "credentials/youtube_client_secret.json"))
    youtube_token_file: str = field(default_factory=lambda: _env("YOUTUBE_TOKEN_FILE", "credentials/youtube_token.json"))
    youtube_privacy: str = field(default_factory=lambda: _env("YOUTUBE_PRIVACY", "private"))

    # --- TikTok ---
    tiktok_client_key: str = field(default_factory=lambda: _env("TIKTOK_CLIENT_KEY"))
    tiktok_client_secret: str = field(default_factory=lambda: _env("TIKTOK_CLIENT_SECRET"))
    tiktok_token_file: str = field(default_factory=lambda: _env("TIKTOK_TOKEN_FILE", "credentials/tiktok_token.json"))

    # --- General ---
    lang: str = field(default_factory=lambda: _env("VIDEO_LANG", "es"))
    voice_es: str = field(default_factory=lambda: _env("VIDEO_VOICE_ES", "es-CO-GonzaloNeural"))
    voice_en: str = field(default_factory=lambda: _env("VIDEO_VOICE_EN", "en-US-ChristopherNeural"))

    # --- Rendimiento y audio ---
    render_concurrency: int = field(default_factory=lambda: _env_int("RENDER_CONCURRENCY", 2, lo=1, hi=4))
    audio_loudnorm: bool = field(default_factory=lambda: _env_bool("AUDIO_LOUDNORM", True))
    keep_temp_files: bool = field(default_factory=lambda: _env_bool("KEEP_TEMP_FILES", False))

    web_host: str = field(default_factory=lambda: _env("WEB_HOST", "127.0.0.1"))
    web_port: int = field(default_factory=lambda: int(_env("WEB_PORT", "8000") or 8000))

    ffmpeg_path_override: str = field(default_factory=lambda: _env("FFMPEG_PATH"))

    def __post_init__(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.credentials_dir.mkdir(parents=True, exist_ok=True)
        self.ffmpeg = _resolve_ffmpeg("ffmpeg", self.ffmpeg_path_override)
        self.ffprobe = _resolve_ffmpeg("ffprobe", self.ffmpeg_path_override)

    # --- Helpers de ruta (siempre absolutas) ---
    def path(self, value: str) -> Path:
        p = Path(value)
        return p if p.is_absolute() else (self.project_root / p)

    def default_voice(self, lang: Optional[str] = None) -> str:
        return self.voice_en if (lang or self.lang) == "en" else self.voice_es

    def ffmpeg_ready(self) -> bool:
        return bool(self.ffmpeg and self.ffprobe)

    def provider_ready(self, provider: Optional[str] = None) -> bool:
        p = (provider or self.llm_provider).lower()
        if p == "opencode":
            return bool(self.opencode_api_key)
        if p == "gemini":
            return bool(self.gemini_api_key)
        if p == "openai":
            return bool(self.openai_api_key)
        if p == "ollama":
            return True  # servidor local, se valida en tiempo de ejecución
        return True  # demo siempre listo


settings = Settings()
