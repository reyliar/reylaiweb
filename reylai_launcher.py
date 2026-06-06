import argparse
import base64
import importlib.util
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path


APP_NAME = "ReylAI"
HOST = "127.0.0.1"
LOADING_WIDTH = 560
LOADING_HEIGHT = 650
LOADING_MIN_SIZE = (520, 620)
SPLASH_MIN_SECONDS = 5.0
HANDOFF_FADE_SECONDS = 0.34


def _runtime_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _bundle_dir():
    return Path(getattr(sys, "_MEIPASS", _runtime_dir())).resolve()


def _candidate_app_dirs():
    runtime_dir = _runtime_dir()
    candidates = [
        Path(os.environ.get("REYLAI_APP_DIR", "")) if os.environ.get("REYLAI_APP_DIR") else None,
        runtime_dir,
        runtime_dir.parent,
        Path.cwd(),
        Path(__file__).resolve().parent if not getattr(sys, "frozen", False) else None,
    ]
    seen = set()
    for candidate in candidates:
        if not candidate:
            continue
        candidate = candidate.resolve()
        if candidate in seen:
            continue
        seen.add(candidate)
        yield candidate


def find_app_dir():
    for candidate in _candidate_app_dirs():
        if (candidate / "app.py").exists():
            return candidate
    raise FileNotFoundError("app.py bulunamadı. ReylAI.exe dosyasını proje klasörüne veya dist'in bir üstüne koyun.")


def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((HOST, 0))
        return sock.getsockname()[1]


def wait_for_server(url, timeout=45):
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.5) as response:
                if 200 <= response.status < 500:
                    return True
        except Exception as exc:
            last_error = exc
            time.sleep(0.25)
    raise TimeoutError(f"ReylAI sunucusu zamanında başlamadı: {last_error}")


def import_app_module(app_dir):
    app_path = Path(app_dir) / "app.py"
    sys.path.insert(0, str(app_dir))
    spec = importlib.util.spec_from_file_location("reylai_app_runtime", app_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def run_server(app_dir, port):
    os.environ["REYLAI_SERVER_ONLY"] = "1"
    os.environ["REYLAI_FLASK_HOST"] = HOST
    os.environ["REYLAI_FLASK_PORT"] = str(port)
    os.environ["REYLAI_APP_DIR"] = str(app_dir)
    module = import_app_module(app_dir)
    module.app.run(host=HOST, port=port, debug=False, threaded=True, use_reloader=False)


def icon_data_url():
    icon_path = _runtime_dir() / "resources" / "reylai_icon.png"
    if not icon_path.exists():
        icon_path = _bundle_dir() / "resources" / "reylai_icon.png"
    if not icon_path.exists():
        return ""
    data = base64.b64encode(icon_path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{data}"


def _legacy_loading_html_unused():
    icon = icon_data_url()
    return f"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ReylAI Yükleniyor</title>
<style>
  :root {{
    color-scheme: dark;
    --bg: #05050a;
    --bg2: #080812;
    --tile: #17102f;
    --accent: #8557ff;
    --accent-soft: #5f35d8;
    --text: #efeaff;
    --muted: #a8a0d7;
    --dim: #7c7896;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{
    height: 100%;
    margin: 0;
    overflow: hidden;
    background:
      radial-gradient(circle at 50% 30%, rgba(100, 58, 215, .24), transparent 26%),
      radial-gradient(circle at 50% 43%, rgba(83, 44, 180, .12), transparent 38%),
      linear-gradient(180deg, var(--bg2) 0%, var(--bg) 100%);
    font-family: Inter, Segoe UI, Arial, sans-serif;
    color: var(--text);
  }}
  .wrap {{
    position: relative;
    z-index: 1;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 42px 28px;
  }}
  .splash {{
    width: min(420px, 92vw);
    min-height: 480px;
    display: grid;
    justify-items: center;
    align-content: center;
    text-align: center;
  }}
  .tile {{
    width: 92px;
    height: 92px;
    border-radius: 22px;
    display: grid;
    place-items: center;
    background:
      radial-gradient(circle at 50% 42%, rgba(133,87,255,.34), transparent 58%),
      linear-gradient(145deg, rgba(62,34,139,.95), rgba(21,13,47,.98));
    box-shadow:
      0 0 76px rgba(106, 64, 229, .42),
      0 18px 42px rgba(0, 0, 0, .55),
      inset 0 1px 0 rgba(255,255,255,.08);
    animation: tileFloat 2.8s ease-in-out infinite;
  }}
  .tile img {{
    width: 78px;
    height: 78px;
    object-fit: contain;
    filter: drop-shadow(0 10px 18px rgba(0,0,0,.44));
  }}
  h1 {{
    margin: 34px 0 0;
    font-size: 38px;
    line-height: 1;
    letter-spacing: 0;
    font-weight: 800;
    color: var(--accent);
    text-shadow: 0 0 26px rgba(133,87,255,.22);
  }}
  .tm {{
    position: relative;
    top: -13px;
    margin-left: 3px;
    font-size: 10px;
    color: #d9d2ff;
    font-weight: 800;
  }}
  .subtitle {{
    margin-top: 12px;
    color: var(--muted);
    font-size: 13px;
    letter-spacing: 8px;
    text-indent: 8px;
    font-weight: 700;
  }}
  .spinner {{
    width: 40px;
    height: 40px;
    margin-top: 40px;
    border-radius: 50%;
    background:
      conic-gradient(from 0deg, transparent 0 64%, var(--accent) 76%, #a88cff 88%, transparent 100%);
    animation: spin .95s linear infinite;
    position: relative;
  }}
  .spinner::after {{
    content: "";
    position: absolute;
    inset: 4px;
    border-radius: 50%;
    background: var(--bg);
    box-shadow: inset 0 0 0 1px rgba(255,255,255,.06);
  }}
  .status {{
    margin-top: 24px;
    min-height: 20px;
    color: #b9c7ef;
    font-size: 14px;
    font-weight: 600;
  }}
  .detail {{
    margin-top: 8px;
    min-height: 16px;
    color: var(--dim);
    font-size: 12px;
    font-weight: 600;
  }}
  @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
  @keyframes tileFloat {{
    0%, 100% {{ transform: translateY(0); }}
    50% {{ transform: translateY(-4px); }}
  }}
</style>
</head>
<body>
<div class="wrap">
  <main class="splash">
    <div class="tile">{f'<img src="{icon}" alt="ReylAI">' if icon else ''}</div>
    <h1>ReylAI<span class="tm">™</span></h1>
    <div class="spinner" aria-hidden="true"></div>
    <div class="status" id="statusText">Başlatılıyor ✓</div>
    <div class="detail" id="detailText">Uygulama güncel</div>
  </main>
</div>
<script>
  window.setLoadingState = function(message, progress, detail) {{
    document.getElementById('statusText').textContent = message + (progress >= 96 ? ' ✓' : '');
    if (detail) document.getElementById('detailText').textContent = detail;
  }};
</script>
</body>
</html>"""


def _complex_loading_html_unused():
    icon = icon_data_url()
    icon_markup = f'<img src="{icon}" alt="ReylAI">' if icon else '<span class="logo-fallback">R</span>'
    return """<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ReylAI Y&uuml;kleniyor</title>
<style>
  :root {
    color-scheme: dark;
    --bg: #05030c;
    --panel: rgba(14, 9, 27, 0.78);
    --edge: rgba(167, 139, 250, 0.20);
    --accent: #8b5cf6;
    --accent-deep: #4c1d95;
    --cyan: #5eead4;
    --text: #f3efff;
    --muted: #bfb0dc;
    --dim: #7f7193;
    --motion: cubic-bezier(0.22, 1, 0.36, 1);
  }
  * { box-sizing: border-box; }
  html, body {
    height: 100%;
    margin: 0;
    overflow: hidden;
    background:
      linear-gradient(135deg, rgba(5, 3, 12, 1) 0%, rgba(16, 9, 31, 0.99) 52%, rgba(5, 4, 14, 1) 100%),
      linear-gradient(90deg, rgba(124, 58, 237, 0.12), transparent 38%, rgba(94, 234, 212, 0.045));
    font-family: Inter, Segoe UI, Arial, sans-serif;
    color: var(--text);
  }
  body::before,
  body::after {
    content: "";
    position: fixed;
    inset: 0;
    pointer-events: none;
  }
  body::before {
    background:
      repeating-linear-gradient(90deg, rgba(167, 139, 250, 0.038) 0 1px, transparent 1px 42px),
      repeating-linear-gradient(0deg, rgba(167, 139, 250, 0.024) 0 1px, transparent 1px 42px);
    opacity: 0.42;
    animation: gridDrift 18s ease-in-out infinite alternate;
  }
  body::after {
    inset: -20%;
    background:
      linear-gradient(110deg, transparent 0%, rgba(255, 255, 255, 0.08) 43%, rgba(94, 234, 212, 0.07) 50%, transparent 58%),
      linear-gradient(180deg, rgba(255, 255, 255, 0.06), transparent 34%, rgba(76, 29, 149, 0.16));
    transform: translateX(-35%);
    opacity: 0.55;
    animation: liquidSweep 5.6s var(--motion) infinite;
  }
  .wrap {
    position: relative;
    z-index: 1;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 34px 26px;
  }
  .splash {
    position: relative;
    width: min(430px, 92vw);
    min-height: 500px;
    display: grid;
    justify-items: center;
    align-content: center;
    text-align: center;
    padding: 44px 34px 38px;
    border: 1px solid var(--edge);
    border-radius: 30px;
    background:
      linear-gradient(135deg, rgba(31, 20, 58, 0.72), rgba(10, 6, 22, 0.50)),
      rgba(8, 5, 19, 0.76);
    box-shadow:
      0 28px 82px rgba(0, 0, 0, 0.52),
      0 0 42px rgba(109, 40, 217, 0.16),
      inset 0 1px 0 rgba(255,255,255,0.10);
    overflow: hidden;
    animation: splashIn .68s var(--motion) both;
  }
  .splash::before {
    content: "";
    position: absolute;
    inset: 0;
    border-radius: inherit;
    background: linear-gradient(135deg, rgba(255,255,255,0.13), transparent 48%, rgba(124, 58, 237, 0.16));
    opacity: 0.72;
    pointer-events: none;
  }
  .tile {
    position: relative;
    width: 104px;
    height: 104px;
    border-radius: 26px;
    display: grid;
    place-items: center;
    background:
      linear-gradient(145deg, rgba(49,31,88,.94), rgba(13,8,30,.98)),
      linear-gradient(45deg, rgba(139,92,246,.22), rgba(94,234,212,.08));
    border: 1px solid rgba(216, 180, 254, 0.24);
    box-shadow:
      0 0 64px rgba(109, 40, 217, .36),
      0 18px 44px rgba(0, 0, 0, .52),
      inset 0 1px 0 rgba(255,255,255,.12);
    animation: tileBreath 3.2s ease-in-out infinite;
    isolation: isolate;
  }
  .tile::before,
  .tile::after {
    content: "";
    position: absolute;
    border-radius: inherit;
    pointer-events: none;
  }
  .tile::before {
    inset: -9px;
    border: 1px solid rgba(94, 234, 212, 0.18);
    animation: haloPulse 2.8s ease-in-out infinite;
  }
  .tile::after {
    inset: 7px;
    border: 1px solid rgba(216, 180, 254, 0.24);
    box-shadow: inset 0 0 16px rgba(139, 92, 246, 0.16);
  }
  .tile img {
    width: 86px;
    height: 86px;
    object-fit: contain;
    filter:
      drop-shadow(0 0 7px rgba(255,255,255,0.46))
      drop-shadow(0 0 18px rgba(139,92,246,0.82))
      drop-shadow(0 12px 18px rgba(0,0,0,.42));
    z-index: 1;
  }
  .logo-fallback {
    color: var(--text);
    font-size: 38px;
    font-weight: 900;
  }
  h1 {
    margin: 32px 0 0;
    font-size: 40px;
    line-height: 1;
    letter-spacing: 0;
    font-weight: 800;
    color: var(--text);
    text-shadow: 0 0 28px rgba(139,92,246,.30);
  }
  .tm {
    position: relative;
    top: -13px;
    margin-left: 3px;
    font-size: 10px;
    color: #d9d2ff;
    font-weight: 800;
  }
  .subtitle {
    margin-top: 12px;
    color: var(--muted);
    font-size: 13px;
    letter-spacing: 0.12em;
    font-weight: 700;
  }
  .loader-ring {
    width: 42px;
    height: 42px;
    margin-top: 34px;
    border-radius: 50%;
    background:
      conic-gradient(from 0deg, transparent 0 62%, var(--accent) 74%, var(--cyan) 88%, transparent 100%);
    animation: ringSpin 1.05s linear infinite;
    position: relative;
    box-shadow: 0 0 24px rgba(139,92,246,0.18);
  }
  .loader-ring::after {
    content: "";
    position: absolute;
    inset: 4px;
    border-radius: 50%;
    background: var(--bg);
    box-shadow: inset 0 0 0 1px rgba(255,255,255,.06);
  }
  .status-shell {
    width: 100%;
    margin-top: 26px;
    display: grid;
    gap: 10px;
  }
  .status-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 14px;
  }
  .status {
    min-height: 20px;
    color: var(--text);
    font-size: 14px;
    font-weight: 800;
  }
  .pct {
    min-width: 44px;
    color: var(--cyan);
    font-size: 13px;
    font-weight: 800;
    text-align: right;
  }
  .progress-track {
    height: 8px;
    border-radius: 999px;
    border: 1px solid rgba(216, 180, 254, 0.16);
    background: rgba(255,255,255,0.06);
    overflow: hidden;
    box-shadow: inset 0 1px 2px rgba(0,0,0,0.34);
  }
  .progress-fill {
    height: 100%;
    width: 8%;
    border-radius: inherit;
    background: linear-gradient(90deg, var(--accent-deep), var(--accent), var(--cyan));
    box-shadow: 0 0 18px rgba(139,92,246,0.30);
    transition: width .48s var(--motion);
    animation: progressGlow 1.8s ease-in-out infinite;
  }
  .detail {
    min-height: 16px;
    color: var(--dim);
    font-size: 12px;
    font-weight: 700;
    animation: statusFade .42s var(--motion) both;
  }
  body.ready .loader-ring {
    animation-duration: 1.4s;
    opacity: 0.74;
  }
  body.ready .progress-fill {
    box-shadow: 0 0 28px rgba(94,234,212,0.26);
  }
  body.handoff::before,
  body.handoff::after {
    opacity: 0;
    transition: opacity .32s var(--motion);
  }
  body.handoff .splash {
    animation: splashOut .34s var(--motion) forwards;
  }
  @keyframes splashIn {
    from { opacity: 0; transform: translateY(18px) scale(.97); filter: saturate(.82) brightness(.86); }
    to { opacity: 1; transform: none; filter: none; }
  }
  @keyframes splashOut {
    to { opacity: 0; transform: translateY(-10px) scale(.985); filter: blur(7px) saturate(.82) brightness(.72); }
  }
  @keyframes tileBreath {
    0%, 100% { transform: translateY(0) scale(1); box-shadow: 0 0 58px rgba(109,40,217,.32), 0 18px 44px rgba(0,0,0,.52), inset 0 1px 0 rgba(255,255,255,.12); }
    50% { transform: translateY(-5px) scale(1.015); box-shadow: 0 0 78px rgba(139,92,246,.42), 0 22px 50px rgba(0,0,0,.56), inset 0 1px 0 rgba(255,255,255,.14); }
  }
  @keyframes haloPulse {
    0%, 100% { opacity: .32; transform: scale(.98); }
    50% { opacity: .74; transform: scale(1.05); }
  }
  @keyframes ringSpin { to { transform: rotate(360deg); } }
  @keyframes liquidSweep {
    0% { transform: translateX(-48%); opacity: .32; }
    42%, 100% { transform: translateX(42%); opacity: .58; }
  }
  @keyframes gridDrift {
    from { background-position: 0 0, 0 0; }
    to { background-position: 72px 36px, 36px 72px; }
  }
  @keyframes progressGlow {
    0%, 100% { filter: saturate(1); }
    50% { filter: saturate(1.25) brightness(1.08); }
  }
  @keyframes statusFade {
    from { opacity: 0; transform: translateY(4px); }
    to { opacity: 1; transform: none; }
  }
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
      animation-duration: .001ms !important;
      animation-iteration-count: 1 !important;
      transition-duration: .001ms !important;
    }
  }
</style>
</head>
<body>
<div class="wrap">
  <main class="splash">
    <div class="tile">__ICON__</div>
    <h1>ReylAI<span class="tm">TM</span></h1>
    <div class="subtitle">DERS K&#304;TAPLARI &#304;&#199;&#304;N AI TOOL'U</div>
    <div class="loader-ring" aria-hidden="true"></div>
    <div class="status-shell">
      <div class="status-row">
        <div class="status" id="statusText">Ba&#351;lat&#305;l&#305;yor</div>
        <div class="pct" id="progressText">0%</div>
      </div>
      <div class="progress-track" aria-hidden="true"><div class="progress-fill" id="progressFill"></div></div>
      <div class="detail" id="detailText">Uygulama g&#252;ncel</div>
    </div>
  </main>
</div>
<script>
  window.setLoadingState = function(message, progress, detail) {
    var pct = Math.max(0, Math.min(100, Number(progress) || 0));
    document.getElementById('statusText').textContent = message;
    document.getElementById('progressText').textContent = Math.round(pct) + '%';
    document.getElementById('progressFill').style.width = pct + '%';
    if (detail) document.getElementById('detailText').textContent = detail;
    document.body.classList.toggle('ready', pct >= 96);
  };
</script>
</body>
</html>""".replace("__ICON__", icon_markup)


def loading_html():
    icon = icon_data_url()
    icon_markup = f'<img src="{icon}" alt="ReylAI">' if icon else '<span class="logo-fallback">R</span>'
    return """<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ReylAI Y&uuml;kleniyor</title>
<style>
  :root {
    color-scheme: dark;
    --bg: #05030c;
    --ink: #f5f1ff;
    --muted: #9d8fbd;
    --purple: #7c3aed;
    --purple-deep: #2e1065;
    --green: #18e6ae;
    --motion: cubic-bezier(0.22, 1, 0.36, 1);
  }
  * { box-sizing: border-box; }
  html, body {
    height: 100%;
    margin: 0;
    overflow: hidden;
    background: var(--bg);
    color: var(--ink);
    font-family: Inter, Segoe UI, Arial, sans-serif;
  }
  body::before {
    content: "";
    position: fixed;
    inset: 0;
    background:
      radial-gradient(circle at 50% 42%, rgba(124, 58, 237, 0.16), transparent 22%),
      linear-gradient(180deg, rgba(9, 6, 20, 0.96), #05030c 54%, #030207 100%);
    opacity: 1;
    transition: opacity .34s var(--motion);
  }
  .stage {
    position: relative;
    z-index: 1;
    height: 100%;
    display: grid;
    place-items: center;
    padding: 32px;
  }
  .center {
    display: grid;
    justify-items: center;
    text-align: center;
    transform-origin: center;
    animation: intro .58s var(--motion) both;
  }
  .tile {
    width: 76px;
    height: 76px;
    border-radius: 20px;
    display: grid;
    place-items: center;
    background:
      linear-gradient(145deg, rgba(80, 36, 158, 0.76), rgba(18, 8, 38, 0.96)),
      rgba(31, 15, 66, 0.86);
    border: 1px solid rgba(167, 139, 250, 0.20);
    box-shadow:
      0 0 54px rgba(124, 58, 237, 0.34),
      0 16px 38px rgba(0, 0, 0, 0.48),
      inset 0 1px 0 rgba(255, 255, 255, 0.10);
    animation: tileFloat 3.2s ease-in-out infinite;
  }
  .tile img {
    width: 60px;
    height: 60px;
    object-fit: contain;
    filter: drop-shadow(0 0 10px rgba(167, 139, 250, 0.78));
  }
  .logo-fallback {
    color: var(--ink);
    font-size: 34px;
    font-weight: 900;
  }
  h1 {
    margin: 28px 0 0;
    color: #8b5cf6;
    font-size: 38px;
    line-height: 1;
    font-weight: 850;
    letter-spacing: 0;
    text-shadow: 0 0 22px rgba(124, 58, 237, 0.38);
  }
  .tm {
    position: relative;
    top: -13px;
    margin-left: 3px;
    color: #b9a7ff;
    font-size: 10px;
    font-weight: 800;
  }
  .subtitle {
    margin-top: 10px;
    color: var(--muted);
    font-size: 12px;
    font-weight: 760;
    letter-spacing: 0.30em;
  }
  .spinner {
    width: 42px;
    height: 42px;
    margin-top: 38px;
    border-radius: 50%;
    border: 3px solid rgba(255, 255, 255, 0.09);
    border-top-color: var(--purple);
    border-right-color: rgba(24, 230, 174, 0.72);
    box-shadow: 0 0 28px rgba(124, 58, 237, 0.20);
    animation: spin 0.92s linear infinite;
  }
  .status {
    min-height: 20px;
    margin-top: 18px;
    color: var(--green);
    font-size: 14px;
    font-weight: 700;
  }
  .detail {
    min-height: 18px;
    margin-top: 5px;
    color: rgba(157, 143, 189, 0.72);
    font-size: 12px;
    font-weight: 650;
  }
  body.handoff::before { opacity: 0; }
  body.handoff .center {
    animation: outro .34s var(--motion) forwards;
  }
  @keyframes intro {
    from { opacity: 0; transform: translateY(14px) scale(.975); filter: blur(8px) saturate(.8); }
    to { opacity: 1; transform: none; filter: none; }
  }
  @keyframes outro {
    to { opacity: 0; transform: translateY(-8px) scale(.986); filter: blur(7px) saturate(.84); }
  }
  @keyframes tileFloat {
    0%, 100% { transform: translateY(0) scale(1); }
    50% { transform: translateY(-5px) scale(1.018); }
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
      animation-duration: .001ms !important;
      animation-iteration-count: 1 !important;
      transition-duration: .001ms !important;
    }
  }
</style>
</head>
<body>
<main class="stage">
  <section class="center" aria-label="ReylAI açılıyor">
    <div class="tile">__ICON__</div>
    <h1>ReylAI<span class="tm">TM</span></h1>
    <div class="subtitle">DERS K&#304;TAPLARI &#304;&#199;&#304;N AI TOOL'U</div>
    <div class="spinner" aria-hidden="true"></div>
    <div class="status" id="statusText">Uygulama g&#252;ncel &#10003;</div>
    <div class="detail" id="detailText">Ba&#351;lat&#305;l&#305;yor</div>
  </section>
</main>
<script>
  window.setLoadingState = function(message, progress, detail) {
    var done = Number(progress) >= 96;
    document.getElementById('statusText').textContent = done ? 'Uygulama g\\u00fcncel \\u2713' : (message || 'Ba\\u015flat\\u0131l\\u0131yor');
    document.getElementById('detailText').textContent = detail || (done ? 'Haz\\u0131r' : 'Y\\u00fckleniyor');
  };
</script>
</body>
</html>""".replace("__ICON__", icon_markup)


def update_window(window, message, progress, detail=""):
    safe_message = json.dumps(message)
    safe_detail = json.dumps(detail)
    try:
        window.evaluate_js(f"window.setLoadingState({safe_message}, {int(progress)}, {safe_detail})")
    except Exception:
        pass


def primary_screen(webview_module):
    screens = getattr(webview_module, "screens", None) or []
    return screens[0] if screens else None


def windows_dpi_scale():
    if os.name != "nt":
        return 1.0
    try:
        import ctypes

        dpi = ctypes.windll.user32.GetDpiForSystem()
        return max(float(dpi) / 96.0, 1.0)
    except Exception:
        return 1.0


def windows_work_area():
    if os.name != "nt":
        return None
    try:
        import ctypes

        class Rect(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_long),
                ("top", ctypes.c_long),
                ("right", ctypes.c_long),
                ("bottom", ctypes.c_long),
            ]

        rect = Rect()
        if ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(rect), 0):
            return rect.left, rect.top, rect.right, rect.bottom
    except Exception:
        return None
    return None


def centered_position(screen, width, height):
    work_area = windows_work_area()
    if work_area:
        scale = windows_dpi_scale()
        left, top, right, bottom = work_area
        logical_w = (right - left) / scale
        logical_h = (bottom - top) / scale
        x = (left / scale) + max((logical_w - width) / 2, 0)
        y = (top / scale) + max((logical_h - height) / 2, 0)
        return int(round(x)), int(round(y))

    if not screen:
        return None, None
    screen_x = int(getattr(screen, "x", 0) or 0)
    screen_y = int(getattr(screen, "y", 0) or 0)
    screen_w = int(getattr(screen, "width", 0) or 0)
    screen_h = int(getattr(screen, "height", 0) or 0)
    if screen_w <= 0 or screen_h <= 0:
        return None, None
    x = screen_x + max((screen_w - width) // 2, 0)
    y = screen_y + max((screen_h - height) // 2, 0)
    return x, y


def maximize_windowed(window, screen):
    try:
        window.maximize()
        return
    except Exception:
        pass

    work_area = windows_work_area()
    if work_area:
        scale = windows_dpi_scale()
        left, top, right, bottom = work_area
        try:
            window.move(int(round(left / scale)), int(round(top / scale)))
        except Exception:
            pass
        try:
            window.resize(int(round((right - left) / scale)), int(round((bottom - top) / scale)))
        except Exception:
            pass
        return

    if not screen:
        try:
            window.resize(1440, 920)
        except Exception:
            pass
        return

    screen_x = int(getattr(screen, "x", 0) or 0)
    screen_y = int(getattr(screen, "y", 0) or 0)
    screen_w = int(getattr(screen, "width", 1440) or 1440)
    screen_h = int(getattr(screen, "height", 920) or 920)
    try:
        window.move(screen_x, screen_y)
    except Exception:
        pass
    try:
        window.resize(screen_w, screen_h)
    except Exception:
        pass


def launch_server_process(app_dir, port):
    env = os.environ.copy()
    env["REYLAI_APP_DIR"] = str(app_dir)
    env["REYLAI_SERVER_ONLY"] = "1"
    env["REYLAI_FLASK_HOST"] = HOST
    env["REYLAI_FLASK_PORT"] = str(port)

    if getattr(sys, "frozen", False):
        # One-file PyInstaller children can keep the parent's _MEI temp folder locked.
        # Run the Flask server in-process so task-ending the app does not orphan a locker.
        thread = threading.Thread(
            target=run_server,
            args=(app_dir, port),
            daemon=True,
            name="ReylAI-Flask",
        )
        thread.start()
        return None

    cmd = [sys.executable, str(Path(__file__).resolve()), "--server", "--app-dir", str(app_dir), "--port", str(port)]

    creationflags = 0
    startupinfo = None
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0

    return subprocess.Popen(
        cmd,
        cwd=str(app_dir),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        creationflags=creationflags,
        startupinfo=startupinfo,
    )


def run_launcher():
    try:
        import webview
    except ImportError as exc:
        raise RuntimeError("pywebview kurulu değil. requirements.txt içindeki bağımlılıkları yükleyin.") from exc

    app_dir = find_app_dir()
    port = find_free_port()
    url = f"http://{HOST}:{port}"
    server_process = {"process": None}
    screen = primary_screen(webview)
    loading_x, loading_y = centered_position(screen, LOADING_WIDTH, LOADING_HEIGHT)

    window = webview.create_window(
        APP_NAME,
        html=loading_html(),
        width=LOADING_WIDTH,
        height=LOADING_HEIGHT,
        x=loading_x,
        y=loading_y,
        screen=screen,
        min_size=LOADING_MIN_SIZE,
        background_color="#05030c",
    )

    def stop_server():
        process = server_process.get("process")
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=4)
            except subprocess.TimeoutExpired:
                process.kill()

    try:
        window.events.closed += stop_server
    except Exception:
        pass

    def worker():
        started_at = time.monotonic()
        try:
            update_window(window, "Kitaplar yükleniyor", 18, "Yerel kütüphane hazırlanıyor")
            server_process["process"] = launch_server_process(app_dir, port)
            update_window(window, "AI modeli yükleniyor", 42, "ReylAI servisleri başlatılıyor")
            wait_for_server(url, timeout=60)
            update_window(window, "Kitaplar yükleniyor", 72, "Kapaklar ve tarama durumu okunuyor")
            try:
                urllib.request.urlopen(f"{url}/api/library?grade=9", timeout=5).read(1024)
            except Exception:
                pass
            update_window(window, "Uygulama açılıyor", 96, "Neredeyse hazır")
            remaining = SPLASH_MIN_SECONDS - (time.monotonic() - started_at)
            if remaining > 0:
                time.sleep(remaining)
            update_window(window, "Uygulama açılıyor", 100, "Hazır")
            try:
                window.evaluate_js("document.body.classList.add('handoff')")
            except Exception:
                pass
            time.sleep(HANDOFF_FADE_SECONDS)
            window.load_url(url)
            maximize_windowed(window, screen)
        except Exception as exc:
            update_window(window, "Başlatma hatası", 100, str(exc))

    def on_start():
        threading.Thread(target=worker, daemon=True).start()

    webview.start(on_start, debug=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", action="store_true")
    parser.add_argument("--app-dir", default="")
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()

    if args.server:
        app_dir = Path(args.app_dir).resolve() if args.app_dir else find_app_dir()
        port = args.port or int(os.environ.get("REYLAI_FLASK_PORT", "5000"))
        run_server(app_dir, port)
        return

    run_launcher()


if __name__ == "__main__":
    main()
