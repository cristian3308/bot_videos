#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Motor visual 'Dark Tech': genera cada escena en HTML (tema de color + tipos de escena) y la graba con Playwright."""
from __future__ import annotations

import asyncio
import html
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from config.settings import settings

# Paletas de color (p = primario, a = acento, d = peligro/alerta)
THEMES: Dict[str, Dict[str, str]] = {
    "verde":   {"p": "#00ff88", "p_rgb": "0,255,136",   "a": "#38bdf8", "a_rgb": "56,189,248",  "d": "#ff2a55", "d_rgb": "255,42,85"},
    "azul":    {"p": "#38bdf8", "p_rgb": "56,189,248",  "a": "#00ff88", "a_rgb": "0,255,136",   "d": "#ff2a55", "d_rgb": "255,42,85"},
    "rojo":    {"p": "#ff3b5c", "p_rgb": "255,59,92",   "a": "#ffb020", "a_rgb": "255,176,32",  "d": "#ff2a55", "d_rgb": "255,42,85"},
    "purpura": {"p": "#b36bff", "p_rgb": "179,107,255", "a": "#38bdf8", "a_rgb": "56,189,248",  "d": "#ff2a55", "d_rgb": "255,42,85"},
    "naranja": {"p": "#ff9f1c", "p_rgb": "255,159,28",  "a": "#2ec4b6", "a_rgb": "46,196,182",  "d": "#ff2a55", "d_rgb": "255,42,85"},
}

# Tipos de escena válidos (los nuevos: map, stat, timeline, brand)
SCENE_TYPES = ["terminal", "diagram", "evidence", "map", "stat", "timeline", "brand"]


def get_theme(name: Optional[str]) -> Dict[str, str]:
    return THEMES.get((name or "verde").lower(), THEMES["verde"])


def _esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def _center_content(scene: Dict[str, Any]) -> str:
    """Devuelve el HTML central según el tipo de escena (con escape HTML seguro)."""
    scene_type = scene.get("scene_type", "terminal")
    terminal_lines = scene.get("terminal_lines") or [
        "$ analyzing packet capture...",
        "[+] Anomaly detected in outbound traffic",
        "[!] Unauthorized privilege escalation",
    ]
    diagram_nodes = scene.get("diagram_nodes") or ["Vector Inicial", "Servidor Interno", "Exfiltración"]
    code_snippet = scene.get("code_snippet") or "// Inspección de vulnerabilidad crítica\nSTATUS: COMPROMISED"

    if scene_type == "terminal":
        # Evita que una línea con `</script>` rompa el bloque JS inline.
        lines_json = json.dumps([str(x) for x in terminal_lines], ensure_ascii=False).replace("</", "<\\/")
        return f"""
        <div class="terminal-window">
            <div class="terminal-bar">
                <span class="dot red"></span><span class="dot yellow"></span><span class="dot green"></span>
                <span class="term-title">root@soc-forensics:~# live_capture</span>
            </div>
            <div class="terminal-body" id="term-output"></div>
        </div>
        <script>
            const lines = {lines_json};
            const container = document.getElementById('term-output');
            let li = 0;
            function nextLine() {{
                if (li >= lines.length) return;
                const p = document.createElement('div'); p.className = 'term-line';
                if (lines[li].includes('[!]')) p.classList.add('alert-line');
                if (lines[li].includes('[+]')) p.classList.add('success-line');
                container.appendChild(p);
                let ci = 0; const txt = lines[li];
                const iv = setInterval(() => {{
                    p.textContent = txt.slice(0, ci + 1) + '█'; ci++;
                    if (ci >= txt.length) {{ clearInterval(iv); p.textContent = txt; li++; setTimeout(nextLine, 280); }}
                }}, 22);
            }}
            setTimeout(nextLine, 200);
        </script>"""

    if scene_type == "diagram":
        nodes_html = ""
        nodes = diagram_nodes[:3]
        for i, node in enumerate(nodes):
            delay = i * 0.45
            nodes_html += f"""
            <div class="node-card" style="animation-delay: {delay}s">
                <div class="node-step">FASE 0{i + 1}</div>
                <div class="node-title">{_esc(node)}</div>
            </div>"""
            if i < len(nodes) - 1:
                nodes_html += f"""<div class="arrow-connector" style="animation-delay: {delay + 0.2}s"><span>▼ FLUJO DE ATAQUE ▼</span></div>"""
        return f'<div class="diagram-container">{nodes_html}</div>'

    if scene_type == "map":
        nodes = (list(diagram_nodes) + ["Origen", "Relay", "Objetivo"])[:3]
        return f"""
        <div class="map-stage">
            <div class="map-grid"></div>
            <div class="arc arc1"></div><div class="arc arc2"></div>
            <div class="map-node n1"><span class="ping"></span><label>{_esc(nodes[0])}</label></div>
            <div class="map-node n2"><span class="ping"></span><label>{_esc(nodes[1])}</label></div>
            <div class="map-node n3"><span class="ping danger"></span><label>{_esc(nodes[2])}</label></div>
            <div class="packet p1"></div><div class="packet p2"></div>
        </div>"""

    if scene_type == "stat":
        value = scene.get("stat_value") or scene.get("badge") or "100%"
        label = scene.get("stat_label") or scene.get("code_snippet") or "Impacto del ataque"
        return f"""
        <div class="stat-wrap">
            <div class="stat-value" id="statv">{_esc(value)}</div>
            <div class="stat-label">{_esc(label)}</div>
            <div class="stat-glow"></div>
        </div>"""

    if scene_type == "timeline":
        steps = diagram_nodes or ["Acceso inicial", "Escalada", "Exfiltración"]
        rows = ""
        for i, s in enumerate(steps[:5]):
            rows += f"""
            <div class="tl-row" style="animation-delay:{i*0.35}s">
                <div class="tl-dot"></div>
                <div class="tl-time">T+{i}</div>
                <div class="tl-text">{_esc(s)}</div>
            </div>"""
        return f'<div class="timeline"><div class="tl-line"></div>{rows}</div>'

    if scene_type == "brand":
        sub = scene.get("subtitle") or scene.get("code_snippet") or ""
        return f"""
        <div class="brand-stage">
            <div class="brand-ring"></div>
            <div class="brand-sub">{_esc(sub)}</div>
        </div>"""

    # evidence (por defecto)
    return f"""
    <div class="evidence-card">
        <div class="evidence-header"><span class="rec-dot">●</span> EVIDENCIA TÉCNICA VERIFICADA</div>
        <pre class="code-box">{_esc(code_snippet)}</pre>
        <div class="scan-bar"></div>
    </div>"""


ASPECT_RATIOS: Dict[str, tuple[int, int]] = {
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
}


def get_resolution(aspect_ratio: Optional[str] = None) -> tuple[int, int]:
    return ASPECT_RATIOS.get((aspect_ratio or "9:16").strip(), (1080, 1920))


def generate_scene_html(
    scene: Dict[str, Any],
    total_scenes: int,
    theme: Optional[str] = None,
    prog_start: float = 0.0,
    prog_end: float = 1.0,
    aspect_ratio: str = "9:16",
) -> str:
    """Genera una página HTML5/CSS3/JS animada a 1080x1920 (9:16) o 1920x1080 (16:9)."""
    t = get_theme(theme)
    width, height = get_resolution(aspect_ratio)
    is_wide = width > height
    scene_id = int(scene.get("id", 1) or 1)
    headline = _esc(scene.get("headline", "ANÁLISIS FORENSE"))
    badge = _esc(scene.get("badge", "CYBERSECURITY INTEL"))
    center = _center_content(scene)

    dur = float(scene.get("duration", 5.0)) or 5.0
    ps = max(0.0, min(1.0, prog_start)) * 100
    pe = max(0.0, min(1.0, prog_end)) * 100
    wide_css = ""
    if is_wide:
        wide_css = """
        .hud-wrapper { padding: 52px 96px 130px; gap: 28px; }
        .top-bar { padding-bottom: 16px; }
        .badge { font-size: 24px; padding: 8px 20px; }
        .scene-counter { font-size: 24px; }
        .headline { font-size: 56px; padding-left: 24px; }
        .terminal-window { min-height: 430px; }
        .terminal-body { padding: 28px 34px; font-size: 32px; line-height: 1.5; }
        .diagram-container { flex-direction: row; align-items: stretch; gap: 18px; margin-top: 24px; }
        .node-card { flex: 1; padding: 30px 26px; display: flex; flex-direction: column; justify-content: center; }
        .node-title { font-size: 34px; }
        .arrow-connector { display: flex; align-items: center; font-size: 22px; }
        .arrow-connector span { writing-mode: horizontal-tb; }
        .map-stage { min-height: 460px; }
        .stat-value { font-size: 168px; }
        .stat-label { font-size: 40px; margin-top: 18px; max-width: 1300px; }
        .code-box { font-size: 32px; padding: 26px; }
        .tl-row { margin-bottom: 22px; }
        .tl-text { font-size: 34px; }
        .brand-ring { width: 220px; height: 220px; }
        .brand-sub { font-size: 44px; margin-top: 28px; }
        """

    extra_css = (
        ".bgzoom{position:absolute;inset:0;z-index:0;"
        "background:radial-gradient(circle at 50% 35%,#0c192c,#050811 70%,#020307);"
        "animation:kb 16s ease-in-out infinite alternate}"
        "@keyframes kb{to{transform:scale(1.08)}}"
        ".vprog{position:absolute;left:0;right:0;bottom:0;height:10px;background:rgba(255,255,255,.08);z-index:6}"
        ".vprog-fill{height:100%;background:linear-gradient(90deg,var(--a),var(--p));box-shadow:0 0 12px var(--p)}"
        "@keyframes vfill{to{width:" + f"{pe:.1f}" + "%}}"
    )
    extra_body = (
        '<div class="bgzoom"></div>'
        '<div class="vprog"><div class="vprog-fill" style="width:' + f"{ps:.1f}"
        + '%;animation:vfill ' + f"{dur:.2f}" + 's linear forwards"></div></div>'
    )

    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8"><style>
    :root {{ --p:{t['p']}; --p-rgb:{t['p_rgb']}; --a:{t['a']}; --a-rgb:{t['a_rgb']}; --d:{t['d']}; --d-rgb:{t['d_rgb']}; }}
    {extra_css}
    * {{ box-sizing:border-box; margin:0; padding:0; }}
    body {{ width:{width}px; height:{height}px; overflow:hidden; color:#e2f1ff; position:relative;
        background:radial-gradient(circle at 50% 35%, #0c192c 0%, #050811 70%, #020307 100%);
        font-family:'Courier New',Consolas,monospace; }}
    .cyber-grid {{ position:absolute; inset:0; z-index:1;
        background-image:linear-gradient(rgba(var(--p-rgb),.07) 1px,transparent 1px),linear-gradient(90deg,rgba(var(--p-rgb),.07) 1px,transparent 1px);
        background-size:60px 60px; animation:moveGrid 8s linear infinite; }}
    @keyframes moveGrid {{ 100% {{ transform:translateY(60px); }} }}
    .hud-wrapper {{ position:relative; z-index:2; padding:110px 70px; height:100%; display:flex; flex-direction:column; gap:48px; }}
    .top-bar {{ display:flex; justify-content:space-between; align-items:center; border-bottom:2px solid rgba(var(--p-rgb),.35); padding-bottom:24px; }}
    .badge {{ background:rgba(var(--d-rgb),.18); border:2px solid var(--d); color:var(--d); padding:10px 24px; font-size:28px; font-weight:bold; letter-spacing:2px; border-radius:8px; box-shadow:0 0 20px rgba(var(--d-rgb),.4); }}
    .scene-counter {{ font-size:28px; color:var(--p); letter-spacing:3px; }}
    .headline {{ font-family:Arial,sans-serif; font-size:62px; font-weight:900; line-height:1.12; text-transform:uppercase; color:#fff;
        text-shadow:0 0 25px rgba(var(--p-rgb),.45); border-left:10px solid var(--p); padding-left:28px; animation:slideIn .4s ease-out forwards; }}
    @keyframes slideIn {{ from {{ opacity:0; transform:translateX(-30px); }} to {{ opacity:1; transform:translateX(0); }} }}
    /* Terminal */
    .terminal-window {{ background:rgba(6,11,20,.92); border:2px solid var(--p); border-radius:16px; box-shadow:0 20px 60px rgba(var(--p-rgb),.18); overflow:hidden; min-height:580px; }}
    .terminal-bar {{ background:#101c2e; padding:18px 24px; display:flex; align-items:center; gap:14px; border-bottom:1px solid rgba(var(--p-rgb),.25); }}
    .dot {{ width:20px; height:20px; border-radius:50%; }} .red {{ background:#ff5f56; }} .yellow {{ background:#ffbd2e; }} .green {{ background:#27c93f; }}
    .term-title {{ margin-left:16px; font-size:26px; color:#8ab4f8; }}
    .terminal-body {{ padding:36px; font-size:35px; line-height:1.65; color:var(--p); }}
    .term-line {{ margin-bottom:22px; word-break:break-word; }} .alert-line {{ color:var(--d); font-weight:bold; }} .success-line {{ color:var(--a); }}
    /* Diagram */
    .diagram-container {{ display:flex; flex-direction:column; align-items:center; gap:22px; margin-top:10px; }}
    .node-card {{ width:100%; background:linear-gradient(135deg,rgba(16,30,52,.95),rgba(8,16,30,.95)); border:2px solid var(--a); border-radius:18px; padding:32px 40px; opacity:0; animation:popNode .5s ease-out forwards; box-shadow:0 0 30px rgba(var(--a-rgb),.22); }}
    @keyframes popNode {{ from {{ opacity:0; transform:scale(.9) translateY(20px); }} to {{ opacity:1; transform:scale(1) translateY(0); }} }}
    .node-step {{ font-size:24px; color:var(--p); letter-spacing:3px; margin-bottom:8px; }}
    .node-title {{ font-family:Arial,sans-serif; font-size:44px; font-weight:800; color:#fff; }}
    .arrow-connector {{ color:var(--d); font-size:26px; font-weight:bold; letter-spacing:3px; opacity:0; animation:popNode .4s ease-out forwards; text-align:center; }}
    /* Evidence */
    .evidence-card {{ background:rgba(10,17,30,.94); border:2px solid var(--d); border-radius:18px; padding:40px; position:relative; overflow:hidden; box-shadow:0 0 45px rgba(var(--d-rgb),.22); }}
    .evidence-header {{ font-size:28px; color:var(--d); font-weight:bold; margin-bottom:28px; letter-spacing:2px; }}
    .rec-dot {{ animation:blink 1s infinite; }} @keyframes blink {{ 50% {{ opacity:.2; }} }}
    .code-box {{ font-size:36px; line-height:1.6; color:#f8fafc; white-space:pre-wrap; background:rgba(0,0,0,.45); padding:30px; border-radius:12px; border-left:6px solid var(--a); }}
    .scan-bar {{ position:absolute; left:0; right:0; height:6px; background:linear-gradient(90deg,transparent,var(--p),transparent); animation:scan 3s ease-in-out infinite; }}
    @keyframes scan {{ 0% {{ top:0; }} 50% {{ top:96%; }} 100% {{ top:0; }} }}
    /* MAP */
    .map-stage {{ position:relative; flex:1; min-height:760px; border:2px solid rgba(var(--a-rgb),.4); border-radius:18px; overflow:hidden; background:rgba(6,14,26,.6); }}
    .map-grid {{ position:absolute; inset:0; background-image:radial-gradient(rgba(var(--a-rgb),.18) 2px,transparent 2px); background-size:46px 46px; }}
    .map-node {{ position:absolute; display:flex; flex-direction:column; align-items:center; gap:10px; }}
    .map-node label {{ font-family:Arial,sans-serif; font-size:30px; font-weight:800; color:#fff; background:rgba(0,0,0,.5); padding:6px 14px; border-radius:8px; }}
    .map-node .ping {{ width:34px; height:34px; border-radius:50%; background:var(--p); box-shadow:0 0 0 0 rgba(var(--p-rgb),.7); animation:ping 1.6s infinite; }}
    .map-node .ping.danger {{ background:var(--d); box-shadow:0 0 0 0 rgba(var(--d-rgb),.7); }}
    @keyframes ping {{ 70% {{ box-shadow:0 0 0 38px rgba(var(--p-rgb),0); }} 100% {{ box-shadow:0 0 0 0 rgba(var(--p-rgb),0); }} }}
    .n1 {{ left:9%; top:22%; }} .n2 {{ left:42%; top:58%; }} .n3 {{ right:9%; top:30%; }}
    .arc {{ position:absolute; height:4px; background:linear-gradient(90deg,transparent,var(--a),transparent); transform-origin:left center; opacity:.8; }}
    .arc1 {{ left:13%; top:28%; width:34%; transform:rotate(26deg); }}
    .arc2 {{ left:47%; top:60%; width:40%; transform:rotate(-24deg); }}
    .packet {{ position:absolute; width:18px; height:18px; border-radius:50%; background:var(--p); box-shadow:0 0 18px var(--p); }}
    .p1 {{ animation:pk1 2.2s linear infinite; }} .p2 {{ animation:pk2 2.2s linear infinite 1.1s; }}
    @keyframes pk1 {{ 0% {{ left:11%; top:26%; }} 100% {{ left:44%; top:60%; }} }}
    @keyframes pk2 {{ 0% {{ left:45%; top:60%; }} 100% {{ left:88%; top:32%; }} }}
    /* STAT */
    .stat-wrap {{ flex:1; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; position:relative; }}
    .stat-value {{ font-family:Arial,sans-serif; font-size:200px; font-weight:900; color:var(--p); text-shadow:0 0 50px rgba(var(--p-rgb),.6); animation:statPop .7s cubic-bezier(.2,.9,.3,1.4) forwards; line-height:1; }}
    @keyframes statPop {{ from {{ opacity:0; transform:scale(.4); }} to {{ opacity:1; transform:scale(1); }} }}
    .stat-label {{ font-family:Arial,sans-serif; font-size:48px; font-weight:700; color:#fff; margin-top:30px; max-width:860px; }}
    .stat-glow {{ position:absolute; width:620px; height:620px; border-radius:50%; background:radial-gradient(circle,rgba(var(--p-rgb),.22),transparent 70%); z-index:-1; animation:blink 2s infinite; }}
    /* TIMELINE */
    .timeline {{ position:relative; padding-left:40px; margin-top:10px; }}
    .tl-line {{ position:absolute; left:16px; top:10px; bottom:10px; width:4px; background:linear-gradient(var(--p),var(--d)); }}
    .tl-row {{ display:flex; align-items:center; gap:22px; margin-bottom:34px; opacity:0; animation:popNode .5s ease-out forwards; position:relative; }}
    .tl-dot {{ position:absolute; left:-32px; width:24px; height:24px; border-radius:50%; background:var(--p); box-shadow:0 0 16px var(--p); }}
    .tl-time {{ font-size:30px; color:var(--p); font-weight:800; min-width:110px; }}
    .tl-text {{ font-family:Arial,sans-serif; font-size:42px; font-weight:800; color:#fff; }}
    /* BRAND (intro/outro) */
    .brand-stage {{ flex:1; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; position:relative; }}
    .brand-ring {{ width:360px; height:360px; border:8px solid var(--p); border-top-color:transparent; border-radius:50%; animation:spin 3s linear infinite; box-shadow:0 0 50px rgba(var(--p-rgb),.4); }}
    @keyframes spin {{ 100% {{ transform:rotate(360deg); }} }}
    .brand-sub {{ font-family:Arial,sans-serif; font-size:52px; font-weight:800; color:#fff; margin-top:46px; max-width:880px; text-shadow:0 0 25px rgba(var(--p-rgb),.4); }}
    {wide_css}
</style></head>
<body>
    {extra_body}
    <div class="cyber-grid"></div>
    <div class="hud-wrapper">
        <div class="top-bar"><span class="badge">{badge}</span><span class="scene-counter">SEC_LOG // {scene_id:02d}_{total_scenes:02d}</span></div>
        <div class="headline">{headline}</div>
        {center}
    </div>
</body></html>"""


async def _record_with_browser(
    browser: Any,
    html_path: Path,
    duration_sec: float,
    temp_video_dir: Path,
    width: int = 1080,
    height: int = 1920,
) -> None:
    context = await browser.new_context(
        viewport={"width": width, "height": height},
        record_video_dir=str(temp_video_dir),
        record_video_size={"width": width, "height": height},
    )
    try:
        page = await context.new_page()
        await page.goto(html_path.resolve().as_uri())
        await page.wait_for_timeout(int(duration_sec * 1000) + 250)
    finally:
        await context.close()


async def render_scene_video_playwright(
    html_path: Path,
    duration_sec: float,
    out_mp4: Path,
    browser: Any = None,
    aspect_ratio: str = "9:16",
) -> None:
    """
    Graba la animación HTML en Chromium headless y la normaliza a MP4 30fps con FFmpeg.
    Si se pasa `browser`, lo reutiliza en lugar de lanzar una nueva instancia por escena.
    """
    width, height = get_resolution(aspect_ratio)
    temp_video_dir = out_mp4.parent / f"pw_tmp_{out_mp4.stem}"
    temp_video_dir.mkdir(parents=True, exist_ok=True)

    try:
        if browser is not None:
            await _record_with_browser(browser, html_path, duration_sec, temp_video_dir, width, height)
        else:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                owned_browser = await p.chromium.launch(headless=True)
                try:
                    await _record_with_browser(owned_browser, html_path, duration_sec, temp_video_dir, width, height)
                finally:
                    await owned_browser.close()

        recorded_files = list(temp_video_dir.glob("*.webm"))
        if not recorded_files:
            raise RuntimeError(f"Playwright no generó el video para {html_path.name}")

        fade_out = max(0.0, duration_sec - 0.35)
        vf = (f"fps=30,scale={width}:{height},format=yuv420p,"
              f"fade=t=in:st=0:d=0.3,fade=t=out:st={fade_out:.2f}:d=0.35")
        cmd = [
            settings.ffmpeg or "ffmpeg", "-y", "-i", str(recorded_files[0]),
            "-t", f"{duration_sec:.3f}", "-vf", vf,
            "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-an", str(out_mp4),
        ]
        proc = await asyncio.to_thread(
            subprocess.run, cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True
        )
        if proc.returncode != 0:
            tail = "\n".join((proc.stderr or "").splitlines()[-10:])
            raise RuntimeError(f"FFmpeg falló normalizando {html_path.name}:\n{tail}")
    finally:
        shutil.rmtree(temp_video_dir, ignore_errors=True)


async def generate_youtube_thumbnail(
    title: str,
    out_jpg: Path,
    theme: Optional[str] = None,
    subtitle: str = "CASO REAL",
    browser: Any = None,
) -> Optional[Path]:
    """Genera una miniatura 1280x720 estilo YouTube con el gancho del video."""
    t = get_theme(theme)
    safe_sub = _esc(subtitle)
    safe_title = _esc((title or "")[:70])
    thumb_html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>
    *{{margin:0;box-sizing:border-box}}
    body{{width:1280px;height:720px;overflow:hidden;position:relative;
        background:radial-gradient(circle at 30% 30%,#0c192c,#050811 70%,#020307);
        font-family:Arial,Helvetica,sans-serif;color:#fff;display:flex;flex-direction:column;justify-content:center;padding:70px}}
    .grid{{position:absolute;inset:0;background-image:linear-gradient(rgba({t['p_rgb']},.08) 2px,transparent 2px),linear-gradient(90deg,rgba({t['p_rgb']},.08) 2px,transparent 2px);background-size:70px 70px}}
    .tag{{position:relative;align-self:flex-start;background:{t['d']};color:#fff;font-weight:900;font-size:34px;letter-spacing:3px;padding:10px 26px;border-radius:10px;margin-bottom:34px;box-shadow:0 0 30px {t['d']}}}
    .title{{position:relative;font-size:96px;font-weight:900;line-height:1.05;text-transform:uppercase;text-shadow:0 6px 30px rgba({t['p_rgb']},.6)}}
    .title b{{color:{t['p']}}}
    .bar{{position:absolute;left:0;bottom:0;height:16px;width:100%;background:linear-gradient(90deg,{t['a']},{t['p']})}}
    </style></head><body>
    <div class="grid"></div>
    <div class="tag">{safe_sub}</div>
    <div class="title">{safe_title}</div>
    <div class="bar"></div>
    </body></html>"""
    html_file = out_jpg.parent / f"thumb_yt_{out_jpg.stem}.html"
    html_file.write_text(thumb_html, encoding="utf-8")
    try:
        async def _capture(br: Any) -> None:
            page = await br.new_page(viewport={"width": 1280, "height": 720})
            try:
                await page.goto(html_file.resolve().as_uri())
                await page.wait_for_timeout(400)
                await page.screenshot(path=str(out_jpg), type="jpeg", quality=90)
            finally:
                await page.close()

        if browser is not None:
            await _capture(browser)
        else:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                owned_browser = await p.chromium.launch(headless=True)
                try:
                    await _capture(owned_browser)
                finally:
                    await owned_browser.close()
        return out_jpg if out_jpg.exists() else None
    except Exception:  # noqa: BLE001
        return None
    finally:
        html_file.unlink(missing_ok=True)
