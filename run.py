"""
BillingPro cross-platform launcher.
Installs dependencies from requirements.txt and starts the web server.

Usage:
  python run.py              (Windows / Mac / Linux)
  START_BILLINGPRO.bat       (Windows double-click)

Phone camera barcode scan requires HTTPS. By default this launcher starts
HTTPS on port 8443 (self-signed cert). Open https://YOUR-PC-IP:8443 on the phone
and accept the browser security warning once.
Set BILLINGPRO_HTTPS=0 to use plain HTTP only.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
MIN_PYTHON = (3, 9)
HOST = os.environ.get("BILLINGPRO_HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT") or os.environ.get("BILLINGPRO_PORT", "8003"))
HTTPS = os.environ.get("BILLINGPRO_HTTPS", "1").lower() not in ("0", "false", "no")
HTTPS_PORT = int(os.environ.get("BILLINGPRO_HTTPS_PORT", "8443"))


def _banner():
    print(
        """
============================================================
  BillingPro - Point of Sale & Billing
============================================================
"""
    )


def _check_python():
    if sys.version_info < MIN_PYTHON:
        v = ".".join(map(str, MIN_PYTHON))
        print(f"ERROR: Python {v}+ is required. You have {sys.version.split()[0]}.")
        print("Download Python: https://www.python.org/downloads/")
        print("On Windows, check 'Add Python to PATH' during installation.")
        sys.exit(1)


def _pip(*args: str) -> bool:
    cmd = [sys.executable, "-m", "pip", *args]
    print(f"  > {' '.join(cmd)}")
    return subprocess.call(cmd) == 0


def install_dependencies() -> bool:
    req = os.path.join(ROOT, "requirements.txt")
    if not os.path.isfile(req):
        print(f"ERROR: requirements.txt not found at {req}")
        return False

    print("Checking / installing dependencies...\n")
    _pip("install", "--upgrade", "pip")
    if not _pip("install", "-r", req):
        print("\nERROR: Failed to install dependencies.")
        print("Try manually:  python -m pip install -r requirements.txt")
        return False
    print("\nAll dependencies installed.\n")
    return True


def _lan_ips() -> list[str]:
    ips: set[str] = set()
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127."):
                ips.add(ip)
    except Exception:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        if not ip.startswith("127."):
            ips.add(ip)
        s.close()
    except Exception:
        pass
    return sorted(ips)


def print_credentials():
    print(
        """LOGIN CREDENTIALS:
  Super Admin : superadmin / superadmin123   (all shops + feature packs)
  Store Admin : admin / admin123
  Cashier     : cashier / cashier123         (Counter 1)

Languages : English (default), Tamil, Hindi
Docs      : docs/SETUP.md , docs/FUNCTIONALITY.md
"""
    )


def open_browser(url: str):
    time.sleep(3)
    try:
        webbrowser.open(url)
    except Exception:
        pass


def start_server():
    os.chdir(ROOT)
    reload = os.environ.get("BILLINGPRO_RELOAD", "1") not in ("0", "false", "no")
    ssl_kwargs: dict = {}
    scheme = "http"
    listen_port = PORT

    if HTTPS:
        try:
            from ssl_util import ensure_ssl_certs

            certfile, keyfile = ensure_ssl_certs(ROOT)
            ssl_kwargs = {"ssl_certfile": certfile, "ssl_keyfile": keyfile}
            scheme = "https"
            listen_port = HTTPS_PORT
        except Exception as exc:
            print(f"WARNING: HTTPS disabled ({exc})")
            print("Phone live camera needs HTTPS. Photo-scan still works on HTTP.\n")

    local_url = f"{scheme}://localhost:{listen_port}"
    print(f"Starting server at {local_url}")
    for ip in _lan_ips():
        print(f"  Phone / LAN : {scheme}://{ip}:{listen_port}")
    if scheme == "https":
        print("  Tip: on phone, open the LAN URL above, tap Advanced → Proceed")
        print("       (self-signed cert — required for camera on Android/iPhone)")
    print("Press Ctrl+C to stop.")
    print("=" * 60 + "\n")
    threading.Thread(target=open_browser, args=(local_url,), daemon=True).start()

    cmd = [
        sys.executable, "-m", "uvicorn", "app:app",
        "--host", HOST, "--port", str(listen_port),
    ]
    if ssl_kwargs:
        cmd.extend(["--ssl-certfile", ssl_kwargs["ssl_certfile"], "--ssl-keyfile", ssl_kwargs["ssl_keyfile"]])
    if reload:
        cmd.append("--reload")
    sys.exit(subprocess.call(cmd))


def main():
    os.chdir(ROOT)
    _banner()
    _check_python()
    if not install_dependencies():
        sys.exit(1)
    print_credentials()
    start_server()


if __name__ == "__main__":
    main()
