#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Suite de pruebas unitarias para Cybercrime Studio."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core import llm, render, store, subtitles
from uploaders import tiktok


class TestLLMValidation(unittest.TestCase):
    def test_clean_json_with_fences_and_prose(self):
        raw = 'Aquí tienes:\n```json\n{"title": "Test", "scenes": [{"narration": "Hola"}]}\n```\nListo.'
        parsed = llm._clean_json(raw)
        self.assertEqual(parsed["title"], "Test")

    def test_validate_and_normalize_plan(self):
        raw = {
            "title": "Caso SolarWinds",
            "scenes": [
                {
                    "scene_type": "tipo_inventado",
                    "headline": "BRECHA INICIAL",
                    "narration": "",
                    "terminal_lines": "$ whoami\n[+] root",
                    "diagram_nodes": "A, B, C",
                }
            ],
        }
        plan = llm.validate_and_normalize_plan(raw, lang="es")
        self.assertEqual(len(plan["scenes"]), 1)
        sc = plan["scenes"][0]
        self.assertEqual(sc["scene_type"], "evidence")
        self.assertEqual(sc["narration"], "BRECHA INICIAL")
        self.assertEqual(sc["terminal_lines"], ["$ whoami", "[+] root"])
        self.assertEqual(sc["diagram_nodes"], ["A", "B", "C"])

    def test_validate_rejects_empty_scenes(self):
        with self.assertRaises(ValueError):
            llm.validate_and_normalize_plan({"title": "Vacío", "scenes": []})


class TestSubtitles(unittest.TestCase):
    def test_word_boundary_karaoke_and_theme_color(self):
        with tempfile.TemporaryDirectory() as tmp:
            ass_path = Path(tmp) / "sub.ass"
            scenes = [
                {
                    "duration": 2.5,
                    "narration": "Hola {mundo} real",
                    "_word_timings": [
                        {"text": "Hola", "start": 0.1, "end": 0.4},
                        {"text": "{mundo}", "start": 0.5, "end": 1.1},
                        {"text": "real", "start": 1.2, "end": 1.6},
                    ],
                }
            ]
            subtitles.build_dynamic_ass_subtitles(scenes, ass_path, theme="rojo")
            content = ass_path.read_text(encoding="utf-8")
            self.assertIn("&H005C3BFF", content)  # color rojo ASS
            self.assertIn(r"\{MUNDO\}", content)
            self.assertIn(r"\k", content)
            self.assertIn("0:00:00.10", content)

    def test_proportional_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            ass_path = Path(tmp) / "fallback.ass"
            scenes = [{"duration": 4.0, "narration": "Un ataque criptográfico masivo"}]
            subtitles.build_dynamic_ass_subtitles(scenes, ass_path, theme="azul")
            content = ass_path.read_text(encoding="utf-8")
            self.assertIn("&H00F8BD38", content)  # color azul ASS
            self.assertIn("CRIPTOGRÁFICO", content)


class TestRenderHTML(unittest.TestCase):
    def test_html_escaping_prevents_xss_and_broken_code_blocks(self):
        scene = {
            "id": 10,
            "scene_type": "evidence",
            "headline": "XSS <script>alert(1)</script>",
            "badge": "CVE <2026>",
            "code_snippet": "if (a < b) { document.write('<script>evil()</script>'); }",
        }
        doc = render.generate_scene_html(scene, total_scenes=12, theme="verde")
        self.assertIn("SEC_LOG // 10_12", doc)
        self.assertNotIn("<script>alert(1)</script>", doc)
        self.assertNotIn("<script>evil()</script>", doc)
        self.assertIn("&lt;script&gt;", doc)

    def test_terminal_escapes_closing_script_tag(self):
        scene = {
            "id": 1,
            "scene_type": "terminal",
            "headline": "PAYLOAD",
            "terminal_lines": ["$ echo '</script><img src=x>'"],
        }
        doc = render.generate_scene_html(scene, total_scenes=3)
        self.assertIn(r"<\/script>", doc)

    def test_all_scene_types_render(self):
        for stype in render.SCENE_TYPES:
            doc = render.generate_scene_html({"id": 1, "scene_type": stype, "headline": "Test"}, total_scenes=7)
            self.assertIn("<!DOCTYPE html>", doc)


class TestStoreDeduplication(unittest.TestCase):
    def test_topic_history_and_consume(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            with mock.patch.object(store, "TOPICS_FILE", tmp_path / "topics.json"), \
                 mock.patch.object(store, "HISTORY_FILE", tmp_path / "history.json"), \
                 mock.patch.object(store, "SCHED_FILE", tmp_path / "scheduler.json"):
                store.add_topic("El ataque a SolarWinds")
                self.assertEqual(store.load_topics(), ["El ataque a SolarWinds"])
                self.assertFalse(store.is_topic_used("el ataque a solarwinds"))

                store.consume_topic("El ataque a SolarWinds", title="SolarWinds")
                self.assertEqual(store.load_topics(), [])
                self.assertTrue(store.is_topic_used("EL ATAQUE A SOLARWINDS"))

                store.record_used_topic("Noticia X", link="https://example.com/news/1")
                self.assertTrue(store.is_topic_used("Otro texto", link="https://example.com/news/1"))

                cfg = store.save_sched({"auto_upload_youtube": True, "hour": 14})
                self.assertTrue(cfg["auto_upload_youtube"])
                self.assertEqual(cfg["hour"], 14)


class TestTikTokSecurity(unittest.TestCase):
    def test_csrf_state_verification(self):
        with mock.patch.object(tiktok.settings, "tiktok_client_key", "k"), \
             mock.patch.object(tiktok.settings, "tiktok_client_secret", "s"):
            url = tiktok.connect_url("http://127.0.0.1:8000/auth/tiktok/callback")
            state = url.split("state=")[1].split("&")[0]
            self.assertTrue(tiktok.verify_state(state))
            # Un state ya consumido no debe volver a pasar
            self.assertFalse(tiktok.verify_state(state))
            self.assertFalse(tiktok.verify_state("forged_state"))

    def test_tiktok_error_detection(self):
        tiktok._check_tiktok_error({"error": {"code": "ok", "message": ""}})
        with self.assertRaises(RuntimeError):
            tiktok._check_tiktok_error({"error": {"code": "access_token_invalid", "message": "expired"}})


class TestWebSecurity(unittest.TestCase):
    def test_safe_project_dir_blocks_traversal(self):
        try:
            from web import app as web_app
        except ImportError:
            self.skipTest("FastAPI no está instalado en este entorno")

        self.assertIsNone(web_app._safe_project_dir("../etc/passwd"))
        self.assertIsNone(web_app._safe_project_dir("cyber_video_1/../../etc"))
        self.assertIsNone(web_app._safe_project_dir("not_a_project"))
        ok = web_app._safe_project_dir("cyber_video_20260101_120000")
        self.assertIsNotNone(ok)
        self.assertEqual(ok.name, "cyber_video_20260101_120000")

    def test_series_key_and_part_num(self):
        try:
            from web import app as web_app
        except ImportError:
            self.skipTest("FastAPI no está instalado en este entorno")

        k1, _ = web_app._series_key("El hackeo de Ronin - Parte 1")
        k2, _ = web_app._series_key("El hackeo de Ronin (Parte 2)")
        self.assertEqual(k1, k2)
        self.assertEqual(web_app._part_num("El hackeo de Ronin Pt. 3"), 3)
        self.assertEqual(web_app._part_num("Video único"), 1)


class TestSFXAndWidescreenHooks(unittest.TestCase):
    def test_sfx_track_generates_valid_wav(self):
        import wave
        from core import sfx

        with tempfile.TemporaryDirectory() as tmp:
            wav_path = Path(tmp) / "sfx.wav"
            scenes = [
                {"scene_type": "terminal", "duration": 2.0},
                {"scene_type": "stat", "duration": 1.5},
                {"scene_type": "map", "duration": 1.5},
                {"scene_type": "evidence", "duration": 1.0},
            ]
            sfx.build_sfx_track(scenes, wav_path)
            self.assertTrue(wav_path.exists())
            with wave.open(str(wav_path), "rb") as wf:
                self.assertEqual(wf.getnchannels(), 1)
                self.assertEqual(wf.getframerate(), sfx.SAMPLE_RATE)
                self.assertGreaterEqual(wf.getnframes(), int(6.0 * sfx.SAMPLE_RATE))

    def test_widescreen_16_9_html_and_subtitles(self):
        doc = render.generate_scene_html(
            {"id": 1, "scene_type": "diagram", "headline": "16:9 TEST", "diagram_nodes": ["A", "B", "C"]},
            total_scenes=3, aspect_ratio="16:9",
        )
        self.assertIn("width:1920px; height:1080px;", doc)
        self.assertIn("flex-direction: row", doc)

        with tempfile.TemporaryDirectory() as tmp:
            ass_path = Path(tmp) / "wide.ass"
            subtitles.build_dynamic_ass_subtitles(
                [{"duration": 3.0, "narration": "Prueba horizontal"}], ass_path, theme="verde", aspect_ratio="16:9"
            )
            content = ass_path.read_text(encoding="utf-8")
            self.assertIn("PlayResX: 1920", content)
            self.assertIn("PlayResY: 1080", content)

    def test_viral_hooks(self):
        from core import styles

        self.assertEqual(styles.resolve_hook("auto"), "")
        for hk in ("cifra", "paradoja", "error_fatal", "cuenta_regresiva", "pregunta"):
            instr = styles.resolve_hook(hk)
            self.assertIn("HOOK OBLIGATORIO", instr)


if __name__ == "__main__":
    unittest.main()
