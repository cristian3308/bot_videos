#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Estilos narrativos/visuales del video.

Cada estilo cambia el TONO del guion (cómo lo explica la IA), el TEMA de color y el
MOOD de la música, para que los videos no se vean/expliquen todos iguales y se adapten
al tipo de caso. Con 'auto' se elige según el tema; en lote se rotan para dar variedad.
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple

STYLES: Dict[str, Dict[str, str]] = {
    "investigacion": {
        "label": "Investigación", "theme": "verde", "mood": "dark",
        "tone": "Narra con tono de investigación forense: serio, metódico y revelador, como un analista reconstruyendo el ataque.",
    },
    "alerta": {
        "label": "Alerta / Breaking", "theme": "rojo", "mood": "action",
        "tone": "Narra con tono de ALERTA urgente, estilo breaking news: enérgico, directo y con sensación de peligro inminente.",
    },
    "didactico": {
        "label": "Didáctico", "theme": "azul", "mood": "suspense",
        "tone": "Narra con tono didáctico y claro, explicando cada paso con sencillez como a un principiante, sin perder el rigor técnico.",
    },
    "documental": {
        "label": "Documental", "theme": "purpura", "mood": "dark",
        "tone": "Narra con tono documental y cinematográfico: cuenta una historia con ritmo, contexto y suspenso, como un true-crime tecnológico.",
    },
    "misterio": {
        "label": "Misterio", "theme": "naranja", "mood": "tense",
        "tone": "Narra con tono de misterio e intriga: plantea preguntas, crea tensión y revela la verdad poco a poco.",
    },
}

# Orden de rotación para lotes (da variedad entre videos consecutivos)
ROTATION = ["investigacion", "alerta", "documental", "didactico", "misterio"]


def pick_style(topic: Optional[str], index: Optional[int] = None) -> str:
    """Elige un estilo automáticamente: por índice (rotación en lote) o por el tema."""
    if index is not None:
        return ROTATION[index % len(ROTATION)]
    t = (topic or "").lower()
    if any(k in t for k in ["alerta", "breaking", "reciente", "hoy", "esta semana", "cve-202", "nuevo ataque", "en vivo"]):
        return "alerta"
    if any(k in t for k in ["cómo ", "como ", "qué es", "que es", "explica", "tutorial", "paso a paso", "guía", "guia"]):
        return "didactico"
    if any(k in t for k in ["historia", "caso ", "el robo", "legendar", "clásico", "clasico", "201", "199", "200"]):
        return "documental"
    if any(k in t for k in ["misterio", "enigma", "nadie sabe", "desapareci"]):
        return "misterio"
    return "investigacion"


def resolve(style: Optional[str], topic: Optional[str] = None, index: Optional[int] = None) -> Tuple[str, Dict[str, str]]:
    """Devuelve (nombre_estilo, datos) resolviendo 'auto'/None según tema o índice."""
    if not style or style in ("auto", "variado"):
        style = pick_style(topic, index)
    data = STYLES.get(style, STYLES["investigacion"])
    return style, data
