from pathlib import Path
import shutil
import sys

from flask import render_template_string

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app


def main():
    pdfjs_version = app._pdfjs_asset_version()
    with app.app.app_context():
        html = render_template_string(
            app.HTML,
            meb_logo_src=app._asset_data_url("static/meb_logo.png", "static/meb_logo.png"),
            reylai_icon_src=app._asset_data_url("static/reylai_icon.png", "static/reylai_icon.png"),
            books_stack_src=app._asset_data_url("static/books_stack.png", "static/books_stack.png"),
            books_remote_base_url=app.BOOKS_REMOTE_BASE_URL,
            pdfjs_lib_url=f"/pdfjs/pdf.min.js?v={pdfjs_version}",
            pdfjs_worker_url=f"/pdfjs/pdf.worker.min.js?v={pdfjs_version}",
        )
    Path("index.html").write_text(html, encoding="utf-8")
    pdfjs_dest = ROOT / "pdfjs"
    pdfjs_dest.mkdir(exist_ok=True)
    for filename in ("pdf.min.js", "pdf.worker.min.js"):
        source = ROOT / "static" / "pdfjs" / filename
        if source.exists():
            shutil.copy2(source, pdfjs_dest / filename)


if __name__ == "__main__":
    main()
