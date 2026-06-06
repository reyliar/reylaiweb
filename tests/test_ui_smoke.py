import hashlib
import json
import tempfile
import threading
import time
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import app as reylai_app
from werkzeug.serving import make_server

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - optional dependency
    sync_playwright = None


SAMPLE_PDF = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Count 1 /Kids [3 0 R] >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Contents 4 0 R >>
endobj
4 0 obj
<< /Length 38 >>
stream
BT 20 100 Td (UI Smoke) Tj ET
endstream
endobj
trailer
<< /Root 1 0 R >>
%%EOF
"""


@unittest.skipIf(sync_playwright is None, "playwright not installed")
class UiSmokeTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.base = Path(self.tmpdir.name)
        self.books_dir = self.base / "books"
        self.scans_dir = self.base / "scans"
        self.covers_dir = self.base / "covers"
        self.db_file = self.base / "library.json"
        self.config_file = self.base / "config.json"
        self.chat_history_file = self.base / "chat_history.json"
        for directory in (self.books_dir, self.scans_dir, self.covers_dir):
            directory.mkdir(parents=True, exist_ok=True)

        local_pdf = self.books_dir / "9" / "ui-book.pdf"
        local_pdf.parent.mkdir(parents=True, exist_ok=True)
        local_pdf.write_bytes(SAMPLE_PDF)
        self.local_pdf = local_pdf

        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(reylai_app, "BOOKS_DIR", str(self.books_dir)))
        self.stack.enter_context(patch.object(reylai_app, "SCANS_DIR", str(self.scans_dir)))
        self.stack.enter_context(patch.object(reylai_app, "COVERS_DIR", str(self.covers_dir)))
        self.stack.enter_context(patch.object(reylai_app, "DB_FILE", str(self.db_file)))
        self.stack.enter_context(patch.object(reylai_app, "CONFIG_FILE", str(self.config_file)))
        self.stack.enter_context(
            patch.object(reylai_app, "CHAT_HISTORY_FILE", str(self.chat_history_file))
        )
        self.stack.enter_context(
            patch.object(reylai_app, "ADMIN_HASH", hashlib.sha256(b"test-pass").hexdigest())
        )
        self.stack.enter_context(patch.object(reylai_app, "start_scan", lambda *_a, **_k: None))

        reylai_app.save_library(
            [
                {
                    "book_id": "ui-book",
                    "name": "UI Deneme.pdf",
                    "title": "UI Deneme",
                    "drive_id": "",
                    "local_path": str(local_pdf),
                    "grade": "9",
                    "scan_status": "done",
                    "scan_pages": 3,
                    "added_at": "2026-04-30T00:00:00",
                }
            ]
        )

        self.server = make_server("127.0.0.1", 0, reylai_app.app)
        self.port = self.server.socket.getsockname()[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.thread.join, 2)

    def _mobile_analyze_button_is_visible_and_markdown_renders_legacy(self):
        base_url = f"http://127.0.0.1:{self.port}/"
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 390, "height": 844}, is_mobile=True)

            status_calls = {"count": 0}

            def handle_analyze_start(route):
                route.fulfill(
                    status=200,
                    headers={"Content-Type": "application/json"},
                    body=json.dumps({"success": True, "analysis_id": "ui-test-analysis"}),
                )

            def handle_analyze_status(route):
                status_calls["count"] += 1
                done = status_calls["count"] >= 2
                body = (
                    {"done": True, "message": "Yanıt hazır.", "stage": "done", "result": "Bu **kalin** ve *italik* cevap."}
                    if done
                    else {"done": False, "message": "Hazır tarama metni okunuyor...", "stage": "cache"}
                )
                route.fulfill(status=200, headers={"Content-Type": "application/json"}, body=json.dumps(body))

            page.route("**/api/analyze_start", handle_analyze_start)
            page.route("**/api/analyze_status/**", handle_analyze_status)
            page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_selector(".book-card", timeout=15000)
            page.locator(".book-card").first.click()
            page.wait_for_selector("#analysisScreen.active", timeout=10000)
            page.wait_for_timeout(800)

            button_box = page.locator("#analyzeBtn").bounding_box()
            self.assertIsNotNone(button_box)
            self.assertGreaterEqual(button_box["x"], 0)
            self.assertLessEqual(button_box["x"] + button_box["width"], 390)
            self.assertIn("Analiz", page.locator("#analyzeBtn").inner_text())

            page.locator("#promptInput").fill("Bu **kalin** ve *italik* soruyu açıkla.")
            page.locator("#analyzeBtn").click()
            self.assertIn(
                page.locator("#typingIndicator .typing-label").text_content().strip(),
                ["Yazıyor...", "Analiz başlatılıyor..."],
            )
            page.wait_for_selector(".chat-msg.ai .chat-text .chat-inline-strong", timeout=10000)
            page.wait_for_selector("#responseBanner.active", timeout=10000)

            user_html = page.locator(".chat-msg.user .chat-bubble").inner_html()
            ai_html = page.locator(".chat-msg.ai .chat-text").inner_html()

            self.assertIn('class="chat-inline-strong"', user_html)
            self.assertIn('class="chat-inline-em"', user_html)
            self.assertIn('class="chat-inline-strong"', ai_html)
            self.assertIn('class="chat-inline-em"', ai_html)
            self.assertNotIn("*", page.locator(".chat-msg.ai .chat-text").inner_text())

            browser.close()

    def test_desktop_card_opens_analysis_after_grade_switch(self):
        base_url = f"http://127.0.0.1:{self.port}/"
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 900})

            page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_selector(".book-card", timeout=15000)
            self.assertEqual(page.locator(".card-analyze-btn").count(), 0)

            page.locator('.grade-btn[data-grade="10"]').click()
            page.wait_for_timeout(800)
            self.assertEqual(page.locator(".empty-state").count(), 1)

            page.locator('.grade-btn[data-grade="9"]').click()
            page.wait_for_selector(".book-card", timeout=15000)
            self.assertEqual(page.locator(".card-analyze-btn").count(), 0)

            first_card = page.locator(".book-card").first
            card_box = first_card.bounding_box()
            self.assertIsNotNone(card_box)
            self.assertGreater(card_box["width"], 120)

            first_card.click()
            page.wait_for_selector("#analysisScreen.active", timeout=10000)
            self.assertTrue(page.locator("#analyzeBtn").is_visible())
            self.assertIn("Analiz Et", page.locator("#analyzeBtn").inner_text())

            browser.close()

    def test_auth_callback_runs_original_action_after_password(self):
        base_url = f"http://127.0.0.1:{self.port}/"
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 900})

            page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_selector(".upload-nav-btn", timeout=15000)

            page.evaluate("() => { window.__authCallbackRan = false; requireAuth(function(){ window.__authCallbackRan = true; }); }")
            page.wait_for_selector("#authOverlay.active", timeout=10000)
            page.locator("#authInput").fill("test-pass")

            page.locator("#authInput").press("Enter")
            page.wait_for_function("() => window.__authCallbackRan === true", timeout=10000)

            self.assertTrue(page.evaluate("() => !!sessionStorage.getItem('auth_token')"))
            self.assertFalse(page.locator("#authOverlay").evaluate("el => el.classList.contains('active')"))

            browser.close()

    def test_upload_requires_password_after_file_selection(self):
        base_url = f"http://127.0.0.1:{self.port}/"
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 900})

            page.route(
                "**/api/upload",
                lambda route: route.fulfill(
                    status=200,
                    headers={"Content-Type": "application/json"},
                    body=json.dumps({"success": True}),
                ),
            )
            page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_selector(".upload-nav-btn", timeout=15000)

            with page.expect_file_chooser(timeout=10000) as chooser_info:
                page.locator(".upload-nav-btn").click()
            chooser_info.value.set_files(str(self.local_pdf))

            page.wait_for_selector("#authOverlay.active", timeout=10000)
            page.locator("#authInput").fill("test-pass")

            with page.expect_response("**/api/upload", timeout=10000):
                page.locator("#authInput").press("Enter")

            self.assertTrue(page.evaluate("() => !!sessionStorage.getItem('auth_token')"))
            self.assertFalse(page.locator("#authOverlay").evaluate("el => el.classList.contains('active')"))

            browser.close()

    def test_library_chat_history_drawer_continues_correct_book(self):
        second_pdf = self.books_dir / "9" / "lit-book.pdf"
        second_pdf.write_bytes(SAMPLE_PDF)
        reylai_app.save_library(
            [
                {
                    "book_id": "ui-book",
                    "name": "Ingilizce 9.pdf",
                    "title": "Ingilizce 9",
                    "drive_id": "",
                    "local_path": str(self.local_pdf),
                    "grade": "9",
                    "scan_status": "done",
                    "scan_pages": 3,
                    "added_at": "2026-04-30T00:00:00",
                },
                {
                    "book_id": "lit-book",
                    "name": "Edebiyat.pdf",
                    "title": "Edebiyat",
                    "drive_id": "",
                    "local_path": str(second_pdf),
                    "grade": "9",
                    "scan_status": "done",
                    "scan_pages": 3,
                    "added_at": "2026-04-30T00:01:00",
                },
            ]
        )
        chat_store = {
            "chats": [
                {
                    "id": "chat-english",
                    "book_id": "ui-book",
                    "book_title": "Ingilizce 9",
                    "drive_id": "",
                    "title": "Ingilizce sorusu",
                    "messages": [{"role": "user", "text": "Ingilizce sorusu"}],
                    "created_at": "2026-05-20T16:16:00",
                    "updated_at": "2026-05-20T16:18:00",
                },
                {
                    "id": "chat-literature",
                    "book_id": "lit-book",
                    "book_title": "Edebiyat",
                    "drive_id": "",
                    "title": "Edebiyat sorusu",
                    "messages": [{"role": "user", "text": "Edebiyat sorusu"}],
                    "created_at": "2026-05-20T16:15:00",
                    "updated_at": "2026-05-20T16:17:00",
                },
            ]
        }

        base_url = f"http://127.0.0.1:{self.port}/"
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.add_init_script(
                "localStorage.setItem('reylai.chatHistory.v1', " + json.dumps(json.dumps(chat_store)) + ");"
            )

            page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_selector(".book-card", timeout=15000)
            page.locator(".history-nav-btn").click()
            page.wait_for_selector("#chatSidebar:not(.collapsed)", timeout=10000)

            self.assertEqual(page.locator("#chatHistoryList .chat-history-item").count(), 2)
            history_font = page.locator("#chatHistoryList").evaluate("el => getComputedStyle(el).fontFamily")
            self.assertIn("Manrope", history_font)

            page.locator("#chatHistoryList .chat-history-item", has_text="Edebiyat").click()
            page.wait_for_selector("#analysisScreen.active", timeout=10000)

            self.assertEqual(page.locator("#selectedTitle").inner_text(), "Edebiyat")
            self.assertIn("Edebiyat sorusu", page.locator(".chat-msg.user .chat-bubble").inner_text())

            browser.close()

    def test_chat_history_delete_button_removes_chat(self):
        reylai_app.save_chat_history(
            {
                "chats": [
                    {
                        "id": "chat-keep",
                        "book_id": "ui-book",
                        "book_title": "UI Deneme",
                        "title": "Kalacak sohbet",
                        "messages": [{"role": "user", "text": "Kalacak"}],
                        "created_at": "2026-05-20T16:16:00",
                        "updated_at": "2026-05-20T16:18:00",
                    },
                    {
                        "id": "chat-delete",
                        "book_id": "ui-book",
                        "book_title": "UI Deneme",
                        "title": "Silinecek sohbet",
                        "messages": [{"role": "user", "text": "Silinecek"}],
                        "created_at": "2026-05-20T16:15:00",
                        "updated_at": "2026-05-20T16:17:00",
                    },
                ]
            }
        )

        base_url = f"http://127.0.0.1:{self.port}/"
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 900})

            page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_selector(".book-card", timeout=15000)
            page.locator(".history-nav-btn").click()
            page.wait_for_selector("#chatSidebar:not(.collapsed)", timeout=10000)
            self.assertEqual(page.locator("#chatHistoryList .chat-history-item").count(), 2)

            page.locator("#chatHistoryList .chat-history-item", has_text="Silinecek").locator(".chat-history-delete").click()
            page.wait_for_function(
                "() => document.querySelectorAll('#chatHistoryList .chat-history-item').length === 1",
                timeout=10000,
            )
            self.assertIn("Kalacak", page.locator("#chatHistoryList").inner_text())
            self.assertNotIn("Silinecek", page.locator("#chatHistoryList").inner_text())

            browser.close()

        saved = reylai_app.load_chat_history()
        self.assertEqual([chat["id"] for chat in saved["chats"]], ["chat-keep"])

    def _navbar_scan_button_opens_status_overlay_and_finishes_legacy(self):
        base_url = f"http://127.0.0.1:{self.port}/"
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 900})

            page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_selector(".upload-nav-btn", timeout=15000)
            self.assertEqual(page.locator("#scanAllBtn").count(), 0)

            self.assertEqual(page.locator("#syncBtn").count(), 0)
            self.assertNotIn("Cloud'a Aktar", page.locator(".nav-right").inner_text())

            browser.close()


    def test_mobile_analyze_button_is_visible_and_markdown_renders(self):
        base_url = f"http://127.0.0.1:{self.port}/"
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 390, "height": 844}, is_mobile=True)
            page_errors = []
            page.on("pageerror", lambda exc: page_errors.append(str(exc)))
            page.on(
                "console",
                lambda msg: page_errors.append(msg.text) if msg.type == "error" else None,
            )

            status_calls = {"count": 0}
            tiny_png = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEElEQVR4nGP8zwACTGCSAQANHQEDgslx/wAAAABJRU5ErkJggg=="
            rich_markdown = (
                "## Markdown Baslik\n\n"
                "Bu **kalin**, *italik*, ~~silinen~~, `kod`, [baglanti](https://example.com) "
                "ve www.example.com destekler.[^1]\n\n"
                "Matematiksel ifade:\n"
                "\\[\n"
                "P + \\frac{1}{2} \\rho v^2 + \\rho gh = \\text{Sabit}\n"
                "\\]\n\n"
                "Inline \\(a^2 + b^2 = c^2\\) de desteklenir.\n\n"
                "- [x] Tamam\n"
                "- [ ] Bekliyor\n\n"
                "| Ozellik | Durum |\n"
                "| --- | :---: |\n"
                "| Tablo | Hazir |\n\n"
                "> Alinti metni\n\n"
                "---\n\n"
                f"![Logo]({tiny_png} \"Logo\")\n\n"
                "[^1]: Dipnot metni."
            )

            def handle_analyze_start(route):
                route.fulfill(
                    status=200,
                    headers={"Content-Type": "application/json"},
                    body=json.dumps({"success": True, "analysis_id": "ui-test-analysis"}),
                )

            def handle_analyze_status(route):
                status_calls["count"] += 1
                done = status_calls["count"] >= 2
                body = (
                    {"done": True, "message": "Yanıt hazır.", "stage": "done", "result": rich_markdown}
                    if done
                    else {"done": False, "message": "Hazır tarama metni okunuyor...", "stage": "cache"}
                )
                route.fulfill(status=200, headers={"Content-Type": "application/json"}, body=json.dumps(body))

            page.route("**/api/analyze_start", handle_analyze_start)
            page.route("**/api/analyze_status/**", handle_analyze_status)
            page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
            try:
                page.wait_for_selector(".book-card", timeout=15000)
            except Exception as exc:
                browser.close()
                details = "\n".join(page_errors[-6:]) or str(exc)
                self.fail("Book cards did not render. Page errors:\n" + details)
            page.locator(".book-card").first.click()
            page.wait_for_selector("#analysisScreen.active", timeout=10000)
            page.wait_for_timeout(800)

            button_box = page.locator("#analyzeBtn").bounding_box()
            self.assertIsNotNone(button_box)
            self.assertGreaterEqual(button_box["x"], 0)
            self.assertLessEqual(button_box["x"] + button_box["width"], 390)
            self.assertIn("Analiz", page.locator("#analyzeBtn").inner_text())

            page.locator("#promptInput").fill("Bu **kalin** ve *italik* soruyu açıkla.")
            page.locator("#analyzeBtn").click()
            self.assertIn(
                page.locator("#typingIndicator .typing-label").text_content().strip(),
                ["Yazıyor...", "Analiz başlatılıyor..."],
            )
            try:
                page.wait_for_selector(".chat-msg.ai .chat-text .chat-inline-strong", timeout=10000)
                page.wait_for_selector(".chat-msg.ai .chat-text .chat-md-table", timeout=10000)
                page.wait_for_selector(".chat-msg.ai .chat-text .chat-md-math.display .chat-math-frac", timeout=10000)
            except Exception as exc:
                chat_text = page.locator("#chatFlow").inner_text(timeout=1000)
                browser.close()
                details = "\n".join(page_errors[-6:]) or str(exc)
                self.fail("Markdown response did not render. Page errors:\n" + details + "\nChat:\n" + chat_text)
            page.wait_for_selector("#responseBanner.active", timeout=10000)

            user_html = page.locator(".chat-msg.user .chat-bubble").inner_html()
            ai_html = page.locator(".chat-msg.ai .chat-text").inner_html()

            self.assertIn('class="chat-inline-strong"', user_html)
            self.assertIn('class="chat-inline-em"', user_html)
            self.assertIn('class="chat-inline-strong"', ai_html)
            self.assertIn('class="chat-inline-em"', ai_html)
            self.assertNotIn("*", page.locator(".chat-msg.ai .chat-text").inner_text())
            self.assertEqual(page.locator(".chat-msg.ai .chat-text .chat-md-heading.level-2").count(), 1)
            self.assertEqual(page.locator(".chat-msg.ai .chat-text .chat-inline-del").count(), 1)
            self.assertEqual(page.locator(".chat-msg.ai .chat-text code.chat-md-code").inner_text(), "kod")
            self.assertEqual(page.locator(".chat-msg.ai .chat-text .chat-md-math.display").count(), 1)
            self.assertIn("ρ", page.locator(".chat-msg.ai .chat-text .chat-md-math.display").inner_text())
            self.assertGreaterEqual(page.locator(".chat-msg.ai .chat-text .chat-md-math.inline").count(), 1)
            self.assertEqual(page.locator(".chat-msg.ai .chat-text .chat-md-task-checkbox").count(), 2)
            self.assertTrue(page.locator(".chat-msg.ai .chat-text .chat-md-task-checkbox").first.is_checked())
            self.assertIn("Tablo", page.locator(".chat-msg.ai .chat-text .chat-md-table").inner_text())
            self.assertIn("Alinti metni", page.locator(".chat-msg.ai .chat-text blockquote").inner_text())
            self.assertEqual(page.locator(".chat-msg.ai .chat-text hr.chat-md-hr").count(), 1)
            self.assertEqual(page.locator(".chat-msg.ai .chat-text img.chat-md-image[alt='Logo']").count(), 1)
            self.assertGreaterEqual(page.locator(".chat-msg.ai .chat-text a.chat-md-link").count(), 3)
            self.assertIn("Dipnot metni", page.locator(".chat-msg.ai .chat-text .chat-md-footnotes").inner_text())

            browser.close()

    def test_small_talk_answers_locally_without_analysis_request(self):
        base_url = f"http://127.0.0.1:{self.port}/"
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 390, "height": 844}, is_mobile=True)
            calls = {"analyze_start": 0}

            def handle_analyze_start(route):
                calls["analyze_start"] += 1
                route.fulfill(
                    status=500,
                    headers={"Content-Type": "application/json"},
                    body=json.dumps({"success": False, "error": "should not be called"}),
                )

            page.route("**/api/analyze_start", handle_analyze_start)
            page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_selector(".book-card", timeout=15000)
            page.locator(".book-card").first.click()
            page.wait_for_selector("#analysisScreen.active", timeout=10000)

            page.locator("#promptInput").fill("selam bugün nasılsın")
            page.locator("#analyzeBtn").click()
            page.wait_for_selector(".chat-msg.ai .chat-text", timeout=3000)
            page.wait_for_function(
                "() => document.querySelector('.chat-msg.ai .chat-text')?.innerText.includes('buradayım')",
                timeout=3000,
            )

            self.assertEqual(calls["analyze_start"], 0)
            self.assertIn("buradayım", page.locator(".chat-msg.ai .chat-text").inner_text())
            self.assertFalse(page.locator("#typingIndicator").evaluate("el => el.classList.contains('active')"))
            browser.close()

    def test_navbar_bulk_scan_and_cloud_buttons_are_hidden(self):
        base_url = f"http://127.0.0.1:{self.port}/"
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 900})

            page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_selector(".upload-nav-btn", timeout=15000)
            self.assertEqual(page.locator("#scanAllBtn").count(), 0)
            self.assertEqual(page.locator("#syncBtn").count(), 0)
            self.assertNotIn("Kitapları Analiz Et", page.locator(".nav-right").inner_text())
            self.assertNotIn("Cloud'a Aktar", page.locator(".nav-right").inner_text())

            browser.close()

            browser.close()


if __name__ == "__main__":
    unittest.main()
