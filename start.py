"""Quick start (no pip install). Prefer `python run.py` for full setup + HTTPS."""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
HOST = os.environ.get("BILLINGPRO_HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT") or os.environ.get("BILLINGPRO_PORT", "8003"))
HTTPS = os.environ.get("BILLINGPRO_HTTPS", "1").lower() not in ("0", "false", "no")
HTTPS_PORT = int(os.environ.get("BILLINGPRO_HTTPS_PORT", "8443"))


if __name__ == "__main__":
    import uvicorn

    kwargs: dict = {
        "app": "app:app",
        "host": HOST,
        "port": PORT,
        "reload": True,
    }
    if HTTPS:
        try:
            sys.path.insert(0, ROOT)
            from ssl_util import ensure_ssl_certs

            certfile, keyfile = ensure_ssl_certs(ROOT)
            kwargs["port"] = HTTPS_PORT
            kwargs["ssl_certfile"] = certfile
            kwargs["ssl_keyfile"] = keyfile
            print(f"HTTPS on https://0.0.0.0:{HTTPS_PORT} (use phone LAN IP)")
        except Exception as exc:
            print(f"HTTPS unavailable ({exc}); starting HTTP on {PORT}")

    uvicorn.run(**kwargs)
