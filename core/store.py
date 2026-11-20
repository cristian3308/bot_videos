#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Almacenamiento persistente simple en JSON (banco de temas y config del programador)."""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from typing import Any, Dict, List

from config.settings import settings

DATA_DIR = settings.project_root / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
TOPICS_FILE = DATA_DIR / "topics.json"
SCHED_FILE = DATA_DIR / "scheduler.json"
HISTORY_FILE = DATA_DIR / "history.json"

DEFAULT_SCHED: Dict[str, Any] = {
    "enabled": False,
    "hour": 9,
    "minute": 0,
    "count": 1,
    "source": "news",      # news | bank
    "lang": "es",
    "provider": "opencode",
    "model": "",
    "theme": "verde",
    "voice": "",
    "music_mood": "dark",
    "branding": True,
    "style": "auto",
    "auto_upload_youtube": False,
    "auto_upload_tiktok": False,
    "last_run": "",        # fecha YYYY-MM-DD del último lanzamiento
}


def _read(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return default
    return default


def _norm_key(text: str) -> str:
    s = unicodedata.normalize("NFKD", (text or "").strip()).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\s+", " ", s)
    return s[:160]


def load_topics() -> List[str]:
    return _read(TOPICS_FILE, [])


def save_topics(topics: List[str]) -> None:
    TOPICS_FILE.write_text(json.dumps(topics, ensure_ascii=False, indent=2), encoding="utf-8")


def add_topic(topic: str) -> List[str]:
    topics = load_topics()
    topic = topic.strip()
    if topic and topic not in topics:
        topics.append(topic)
        save_topics(topics)
    return topics


def remove_topic(topic: str) -> List[str]:
    topics = [t for t in load_topics() if t != topic]
    save_topics(topics)
    return topics


def load_history() -> List[Dict[str, str]]:
    data = _read(HISTORY_FILE, [])
    return data if isinstance(data, list) else []


def is_topic_used(topic: str, link: str = "") -> bool:
    """Devuelve True si el tema o su enlace ya fue producido anteriormente."""
    key = _norm_key(topic)
    link_clean = (link or "").strip()
    for item in load_history():
        if link_clean and item.get("link") == link_clean:
            return True
        if key and item.get("key") == key:
            return True
    return False


def record_used_topic(topic: str, title: str = "", link: str = "") -> None:
    """Registra un tema/noticia ya producido para evitar duplicados en lotes y programador."""
    if not topic and not link:
        return
    history = load_history()
    key = _norm_key(topic)
    history.append({
        "key": key,
        "topic": (topic or "")[:240],
        "title": (title or "")[:120],
        "link": (link or "").strip(),
        "used_at": datetime.now().isoformat(timespec="seconds"),
    })
    # Mantener los últimos 500 registros para evitar crecimiento infinito
    HISTORY_FILE.write_text(json.dumps(history[-500:], ensure_ascii=False, indent=2), encoding="utf-8")


def consume_topic(topic: str, title: str = "") -> None:
    """Elimina un tema del banco tras usarlo y lo registra en el historial."""
    remove_topic(topic)
    record_used_topic(topic, title=title)


def load_sched() -> Dict[str, Any]:
    cfg = dict(DEFAULT_SCHED)
    cfg.update(_read(SCHED_FILE, {}))
    return cfg


def save_sched(cfg: Dict[str, Any]) -> Dict[str, Any]:
    merged = load_sched()
    merged.update(cfg or {})
    SCHED_FILE.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    return merged
