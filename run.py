"""
BillingPro cross-platform launcher.
Installs dependencies from requirements.txt and starts the web server.

Usage:
  python run.py              (Windows / Mac / Linux)
  START_BILLINGPRO.bat       (Windows double-click)

Default: HTTP on port 8003 (http://localhost:8003).
For phone live camera (HTTPS): set BILLINGPRO_HTTPS=1  → https://PC-IP:8443
Photo barcode scan works on HTTP too.
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
# Default HTTP — more reliable on Windows. HTTPS: set BILLINGPRO_HTTPS=1
HTTPS = os.environ.get("BILLINGPRO_HTTPS", "0").lower() in ("1", "true", "yes")
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


def _port_pids(port: int) -> list[int]:
    """PIDs listening on TCP port (Windows netstat / Unix lsof)."""
    pids: set[int] = set()
    if sys.platform.startswith("win"):
        try:
            out = subprocess.check_output(
                ["netstat", "-ano", "-p", "tcp"],
                text=True,
                errors="replace",
            )
            needle = f":{port}"
            for line in out.splitlines():
                if "LISTENING" not in line.upper():
                    continue
                if needle not in line:
                    continue
                # Match ...:8443 in local address column
                parts = line.split()
                if len(parts) < 5:
                    continue
                local = parts[1] if parts[0].upper().startswith("TCP") else parts[0]
                if not local.endswith(needle) and f"]{needle}" not in local:
                    # also accept 0.0.0.0:8443 / [::]:8443
                    if not (local.endswith(needle)):
                        continue
                try:
                    pids.add(int(parts[-1]))
                except ValueError:
                    pass
        except Exception:
            pass
    else:
        try:
            out = subprocess.check_output(
                ["lsof", "-ti", f"TCP:{port}", "-sTCP:LISTEN"],
                text=True,
                errors="replace",
            )
            for tok in out.split():
                try:
                    pids.add(int(tok))
                except ValueError:
                    pass
        except Exception:
            pass
    return sorted(p for p in pids if p > 0)


def _cmdline(pid: int) -> str:
    if sys.platform.startswith("win"):
        try:
            out = subprocess.check_output(
                [
                    "powershell", "-NoProfile", "-Command",
                    f"(Get-CimInstance Win32_Process -Filter \"ProcessId={pid}\").CommandLine",
                ],
                text=True,
                errors="replace",
            )
            return (out or "").strip()
        except Exception:
            return ""
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            return f.read().decode("utf-8", "replace").replace("\x00", " ")
    except Exception:
        return ""


def free_port(port: int) -> bool:
    """Stop leftover BillingPro/uvicorn processes holding the port."""
    pids = _port_pids(port)
    if not pids:
        return True
    killed = []
    for pid in pids:
        if pid == os.getpid():
            continue
        cmd = _cmdline(pid).lower()
        ours = (
            "uvicorn" in cmd
            or "billingpro" in cmd
            or "app:app" in cmd
            or f"--port {port}" in cmd
            or f"--port={port}" in cmd
        )
        if not ours and cmd:
            print(f"Port {port} is used by PID {pid} (not BillingPro):")
            print(f"  {cmd[:160]}")
            print(f"  Close that app, or set BILLINGPRO_PORT / BILLINGPRO_HTTPS_PORT to another port.")
            return False
        try:
            if sys.platform.startswith("win"):
                subprocess.call(["taskkill", "/PID", str(pid), "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                os.kill(pid, 15)
            killed.append(pid)
        except Exception as exc:
            print(f"Could not stop PID {pid}: {exc}")
            return False
    if killed:
        print(f"Freed port {port} (stopped PID: {', '.join(map(str, killed))})")
        time.sleep(1.2)
    # Re-check
    left = _port_pids(port)
    return not left


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
    time.sleep(2.5)
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
            # uvicorn --reload + SSL often hangs on Windows
            if reload and os.environ.get("BILLINGPRO_RELOAD_SSL", "").lower() not in ("1", "true", "yes"):
                reload = False
                print("Note: auto-reload is OFF with HTTPS (avoids Windows hang).\n")
        except Exception as exc:
            print(f"WARNING: HTTPS disabled ({exc})")
            print("Photo barcode scan still works on HTTP.\n")
            scheme = "http"
            listen_port = PORT
            ssl_kwargs = {}

    if not free_port(listen_port):
        print(f"\nERROR: Port {listen_port} is already in use (WinError 10048).")
        print("  1) Close the other BillingPro window, OR")
        print("  2) Run:  taskkill /F /IM python.exe   (stops all Python apps), OR")
        print("  3) Use HTTP: set BILLINGPRO_HTTPS=0  then start again")
        sys.exit(1)

    local_url = f"{scheme}://localhost:{listen_port}"
    print(f"Starting server at {local_url}")
    for ip in _lan_ips():
        print(f"  Phone / LAN : {scheme}://{ip}:{listen_port}")
    if scheme == "https":
        print("  Tip: phone → Advanced → Proceed (self-signed cert)")
        print("  Desktop: https://localhost:8443")
    else:
        print("  Desktop: http://localhost:8003")
        print("  For live phone camera: set BILLINGPRO_HTTPS=1 and restart")
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
