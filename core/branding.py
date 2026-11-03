#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generador de la identidad del canal: logo, foto de perfil y banner (PNG) + documento de marca."""
from __future__ import annotations

from pathlib import Path
from typing import Optional


async def _render_png(html: str, out_png: Path, width: int, height: int) -> Optional[Path]:
    from playwright.async_api import async_playwright

    tmp = out_png.parent / f"_tmp_{out_png.stem}.html"
    tmp.write_text(html, encoding="utf-8")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": width, "height": height})
            await page.goto(tmp.resolve().as_uri())
            await page.wait_for_timeout(400)
            await page.screenshot(path=str(out_png), type="png")
            await browser.close()
        tmp.unlink(missing_ok=True)
        return out_png if out_png.exists() else None
    except Exception:  # noqa: BLE001
        return None


def _logo_html(name: str, tagline: str, size: int = 1024) -> str:
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>
    *{{margin:0;box-sizing:border-box}}
    body{{width:{size}px;height:{size}px;overflow:hidden;position:relative;
        background:radial-gradient(circle at 50% 42%,#0c192c,#050811 68%,#020307);
        font-family:Arial,Helvetica,sans-serif;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:40px}}
    .grid{{position:absolute;inset:0;background-image:linear-gradient(rgba(0,255,136,.06) 2px,transparent 2px),linear-gradient(90deg,rgba(0,255,136,.06) 2px,transparent 2px);background-size:72px 72px}}
    .mark{{position:relative;width:520px;height:520px;border:14px solid #00ff88;border-radius:50%;
        display:flex;align-items:center;justify-content:center;box-shadow:0 0 90px rgba(0,255,136,.45),inset 0 0 60px rgba(0,255,136,.15)}}
    .mark::before{{content:'';position:absolute;inset:-14px;border-radius:50%;border:4px solid rgba(255,42,85,.5);clip-path:polygon(0 42%,100% 38%,100% 55%,0 60%)}}
    .zero{{font-size:360px;font-weight:900;color:#fff;text-shadow:0 0 50px rgba(0,255,136,.7);letter-spacing:-10px}}
    .zero b{{color:#00ff88}}
    .slash{{position:absolute;width:150%;height:26px;background:linear-gradient(90deg,transparent,#ff2a55,transparent);transform:rotate(-24deg);box-shadow:0 0 30px #ff2a55}}
    .name{{position:relative;font-size:148px;font-weight:900;letter-spacing:12px;color:#fff;text-shadow:0 0 30px rgba(0,255,136,.5)}}
    .name span{{color:#00ff88}}
    .tag{{position:relative;font-size:38px;letter-spacing:10px;color:#7a93b3;margin-top:-18px}}
    </style></head><body>
    <div class="grid"></div>
    <div class="mark"><span class="zero">0<b>D</b></span><div class="slash"></div></div>
    <div class="name">{name.split()[0]}<span>{(' ' + name.split()[1]) if len(name.split())>1 else ''}</span></div>
    <div class="tag">{tagline}</div>
    </body></html>"""


def _banner_html(name: str, tagline: str) -> str:
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>
    *{{margin:0;box-sizing:border-box}}
    body{{width:2560px;height:1440px;overflow:hidden;position:relative;
        background:radial-gradient(circle at 50% 50%,#0c192c,#050811 60%,#020307);
        font-family:Arial,Helvetica,sans-serif;display:flex;align-items:center;justify-content:center}}
    .grid{{position:absolute;inset:0;background-image:linear-gradient(rgba(0,255,136,.05) 2px,transparent 2px),linear-gradient(90deg,rgba(0,255,136,.05) 2px,transparent 2px);background-size:90px 90px}}
    /* zona segura centrada (~1546x423) */
    .safe{{position:relative;width:1546px;height:423px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:26px}}
    .row{{display:flex;align-items:center;gap:40px}}
    .mark{{width:170px;height:170px;border:9px solid #00ff88;border-radius:50%;display:flex;align-items:center;justify-content:center;box-shadow:0 0 50px rgba(0,255,136,.5)}}
    .mark span{{font-size:120px;font-weight:900;color:#fff}}.mark b{{color:#00ff88}}
    .name{{font-size:150px;font-weight:900;letter-spacing:14px;color:#fff;text-shadow:0 0 30px rgba(0,255,136,.5)}}
    .name i{{color:#00ff88;font-style:normal}}
    .tag{{font-size:46px;letter-spacing:14px;color:#9fb3cc;font-weight:700}}
    .pill{{font-size:34px;letter-spacing:6px;color:#ff4d73;border:2px solid #ff2a55;padding:8px 26px;border-radius:30px;margin-top:6px}}
    </style></head><body>
    <div class="grid"></div>
    <div class="safe">
        <div class="row">
            <div class="mark"><span>0<b>D</b></span></div>
            <div class="name">{name.split()[0]} <i>{name.split()[1] if len(name.split())>1 else ''}</i></div>
        </div>
        <div class="tag">{tagline}</div>
        <div class="pill">NUEVO CASO CADA SEMANA</div>
    </div>
    </body></html>"""


async def generate_brand_pack(name: str, tagline: str, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    logo = out_dir / "logo_perfil_1024.png"
    banner = out_dir / "banner_youtube_2560x1440.png"
    await _render_png(_logo_html(name, tagline), logo, 1024, 1024)
    await _render_png(_banner_html(name, tagline), banner, 2560, 1440)
    return {"logo": str(logo), "banner": str(banner)}
