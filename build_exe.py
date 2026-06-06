import subprocess
import sys
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parent
ICON_PNG = ROOT / "resources" / "reylai_icon.png"
ICON_ICO = ROOT / "resources" / "reylai_icon.ico"
STATIC_DIR = ROOT / "static"


def ensure_icon():
    if not ICON_PNG.exists():
        raise FileNotFoundError(f"Ikon bulunamadı: {ICON_PNG}")
    ICON_ICO.parent.mkdir(parents=True, exist_ok=True)
    image = Image.open(ICON_PNG).convert("RGBA")
    image.save(
        ICON_ICO,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )


def main():
    ensure_icon()
    separator = ";" if sys.platform.startswith("win") else ":"
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onefile",
        "--name",
        "ReylAI",
        "--icon",
        str(ICON_ICO),
        "--add-data",
        f"{ICON_PNG}{separator}resources",
        "--add-data",
        f"{STATIC_DIR}{separator}static",
        "--collect-all",
        "webview",
        "--hidden-import",
        "flask",
        "--hidden-import",
        "werkzeug.serving",
        "--hidden-import",
        "jinja2",
        "--hidden-import",
        "requests",
        "--hidden-import",
        "dotenv",
        "--hidden-import",
        "pypdf",
        "--hidden-import",
        "pdf2image",
        "--hidden-import",
        "PIL.Image",
        str(ROOT / "reylai_launcher.py"),
    ]
    subprocess.run(command, cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
