#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Almacenamiento persistente simple en JSON (banco de temas y config del programador)."""
from __future__ import annotations

import json
from typing import Any, Dict, List

from config.settings import settings

DATA_DIR = settings.project_root / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
TOPICS_FILE = DATA_DIR / "topics.json"
SCHED_FILE = DATA_DIR / "scheduler.json"

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
    "last_run": "",        # fecha YYYY-MM-DD del último lanzamiento
}


def _read(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return default
    return default


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


def load_sched() -> Dict[str, Any]:
    cfg = dict(DEFAULT_SCHED)
    cfg.update(_read(SCHED_FILE, {}))
    return cfg


def save_sched(cfg: Dict[str, Any]) -> Dict[str, Any]:
    merged = load_sched()
    merged.update(cfg or {})
    SCHED_FILE.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    return merged
