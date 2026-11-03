#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extractor de noticias reales de ciberseguridad vía RSS."""
from __future__ import annotations

import re
import urllib.request
import xml.etree.ElementTree as ET
from typing import Dict, List

RSS_FEEDS = [
    "https://feeds.feedburner.com/TheHackersNews",
    "https://www.bleepingcomputer.com/feed/",
]


def fetch_latest_cyber_news(limit: int = 5) -> List[Dict[str, str]]:
    """Descarga los últimos titulares reales de ciberseguridad para inspirar el guion."""
    items: List[Dict[str, str]] = []
    for rss_url in RSS_FEEDS:
        try:
            req = urllib.request.Request(rss_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                xml_data = resp.read()
            root = ET.fromstring(xml_data)
            for item in root.findall(".//item"):
                title = item.findtext("title", default="").strip()
                desc = re.sub(r"<[^>]+>", "", item.findtext("description", default="")).strip()
                link = item.findtext("link", default="").strip()
                if title:
                    items.append({"title": title, "summary": desc[:400], "link": link})
                if len(items) >= limit:
                    return items
        except Exception as exc:  # noqa: BLE001
            print(f"[!] Aviso: no se pudo leer el RSS {rss_url} ({exc}).")
    return items
