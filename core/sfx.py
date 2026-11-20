#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generador procedural de efectos de sonido (SFX) en Python puro (sin copyright).

Crea una pista WAV sincronizada con el inicio y el tipo de cada escena:
  - Transición (whoosh suave entre escenas)
  - terminal : pulsos sutiles de tecleo sincronizados con la animación
  - stat     : impacto grave (sub-bass drop) al aparecer la cifra
  - map/timeline/diagram : ping radar/sonar sutil
  - evidence/brand       : pulso forense de doble tono
"""
from __future__ import annotations

import math
import random
import struct
import wave
from pathlib import Path
from typing import Any, Dict, List

SAMPLE_RATE = 44100


def _mix_into(buf: List[float], start_sec: float, samples: List[float], gain: float = 1.0) -> None:
    start_idx = max(0, int(start_sec * SAMPLE_RATE))
    end_idx = min(len(buf), start_idx + len(samples))
    for i in range(start_idx, end_idx):
        buf[i] += samples[i - start_idx] * gain


def _whoosh(dur: float = 0.34) -> List[float]:
    """Barrido de aire filtrado (suave) para transiciones entre escenas."""
    rng = random.Random(42)
    n = int(dur * SAMPLE_RATE)
    out = [0.0] * n
    lp = 0.0
    for i in range(n):
        t = i / n
        env = math.sin(math.pi * t) ** 1.6
        # Frecuencia de corte sube y baja suavemente
        alpha = 0.04 + 0.22 * math.sin(math.pi * t)
        noise = rng.uniform(-1.0, 1.0)
        lp = lp + alpha * (noise - lp)
        out[i] = lp * env * 0.28
    return out


def _sub_impact(dur: float = 0.55) -> List[float]:
    """Impacto grave tipo cine (115 Hz -> 36 Hz) para escenas 'stat'."""
    n = int(dur * SAMPLE_RATE)
    out = [0.0] * n
    phase = 0.0
    for i in range(n):
        t = i / SAMPLE_RATE
        frac = i / n
        freq = 115.0 * ((36.0 / 115.0) ** (frac ** 0.7))
        phase += 2.0 * math.pi * freq / SAMPLE_RATE
        env = math.exp(-5.0 * frac) * min(1.0, i / 120.0)
        out[i] = math.sin(phase) * env * 0.48
    return out


def _sonar_ping(freq: float = 880.0, dur: float = 0.35) -> List[float]:
    """Ping tecnológico limpio para mapas, diagramas y timelines."""
    n = int(dur * SAMPLE_RATE)
    out = [0.0] * n
    for i in range(n):
        t = i / SAMPLE_RATE
        frac = i / n
        env = math.exp(-7.5 * frac) * min(1.0, i / 80.0)
        val = 0.7 * math.sin(2.0 * math.pi * freq * t) + 0.3 * math.sin(2.0 * math.pi * freq * 1.5 * t)
        out[i] = val * env * 0.22
    return out


def _forensic_blip(dur: float = 0.26) -> List[float]:
    """Doble pulso corto para evidencia técnica o marca."""
    n = int(dur * SAMPLE_RATE)
    out = [0.0] * n
    half = n // 2
    for i in range(n):
        t = i / SAMPLE_RATE
        if i < half:
            f = 540.0
            frac = i / half
        else:
            f = 720.0
            frac = (i - half) / max(1, n - half)
        env = math.exp(-8.0 * frac) * min(1.0, (i % max(1, half)) / 60.0)
        out[i] = math.sin(2.0 * math.pi * f * t) * env * 0.18
    return out


def _key_click(dur: float = 0.018, seed: int = 7) -> List[float]:
    """Click corto de tecla mecánica sutil para escena 'terminal'."""
    rng = random.Random(seed)
    n = int(dur * SAMPLE_RATE)
    out = [0.0] * n
    for i in range(n):
        frac = i / n
        env = math.exp(-16.0 * frac)
        click = rng.uniform(-1.0, 1.0) * 0.5 + math.sin(2.0 * math.pi * 2400.0 * i / SAMPLE_RATE) * 0.5
        out[i] = click * env * 0.14
    return out


def build_sfx_track(scenes: List[Dict[str, Any]], out_wav: Path) -> Path:
    """
    Construye una pista WAV de SFX sincronizada con la duración y tipo de cada escena.
    Devuelve la ruta del archivo WAV generado.
    """
    total_dur = sum(max(0.1, float(s.get("duration", 5.0))) for s in scenes)
    total_samples = max(SAMPLE_RATE, int(math.ceil(total_dur * SAMPLE_RATE)))
    buf = [0.0] * total_samples

    whoosh = _whoosh()
    impact = _sub_impact()
    ping = _sonar_ping()
    blip = _forensic_blip()

    cursor = 0.0
    for idx, scene in enumerate(scenes):
        dur = max(0.1, float(scene.get("duration", 5.0)))
        stype = (scene.get("scene_type") or "evidence").lower()

        # Transición whoosh al entrar a cada nueva escena (a partir de la 2)
        if idx > 0:
            _mix_into(buf, max(0.0, cursor - 0.12), whoosh, gain=0.85)

        if stype == "stat":
            _mix_into(buf, cursor + 0.05, impact, gain=1.0)
        elif stype == "terminal":
            # Secuencia sutil de tecleo durante los primeros ~2.4s de la escena
            t_offset = 0.22
            max_type = min(dur - 0.3, 2.5)
            k_idx = 0
            while t_offset < max_type:
                _mix_into(buf, cursor + t_offset, _key_click(seed=idx * 100 + k_idx), gain=0.75)
                t_offset += 0.065 + (0.04 if (k_idx % 5 == 0) else 0.0)
                k_idx += 1
        elif stype in ("map", "diagram", "timeline"):
            _mix_into(buf, cursor + 0.12, ping, gain=0.85)
        else:
            _mix_into(buf, cursor + 0.08, blip, gain=0.7)

        cursor += dur

    # Clamp y escribir WAV PCM 16-bit mono
    pcm = bytearray(len(buf) * 2)
    for i, s in enumerate(buf):
        clamped = max(-0.95, min(0.95, s))
        struct.pack_into("<h", pcm, i * 2, int(clamped * 32767))

    with wave.open(str(out_wav), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm)
    return out_wav
