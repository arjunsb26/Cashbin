"""Serve the backend on HTTPS :8443 and plain HTTP :8000 from one process.

Hypercorn takes a TLS bind and an insecure bind at the same time, so the phone gets the secure
origin it needs for the camera while the dashboard keeps a plain localhost port.

Run it with:

    uv run --project backend python scripts/run_backend.py
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from hypercorn.asyncio import serve  # noqa: E402
from hypercorn.config import Config  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.main import create_app  # noqa: E402
from scripts.make_cert import build_cert  # noqa: E402


def build_config(host: str, https_port: int, http_port: int | None, cert_dir: Path) -> Config:
    cert_path, key_path = build_cert(cert_dir)
    config = Config()
    config.bind = [f"{host}:{https_port}"]
    config.certfile = str(cert_path)
    config.keyfile = str(key_path)
    if http_port is not None:
        config.insecure_bind = [f"{host}:{http_port}"]
    config.accesslog = "-"
    config.errorlog = "-"
    config.websocket_ping_interval = 20.0
    return config


def main() -> int:
    conf = get_settings()
    parser = argparse.ArgumentParser(description="Run the backend.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--https-port", type=int, default=conf.https_port)
    parser.add_argument("--http-port", type=int, default=conf.http_port)
    parser.add_argument(
        "--no-http",
        action="store_true",
        help="Serve HTTPS only.",
    )
    args = parser.parse_args()

    config = build_config(
        args.host,
        args.https_port,
        None if args.no_http else args.http_port,
        conf.cert_dir,
    )
    app = create_app(conf)
    print(f"https on {args.host}:{args.https_port}")
    if not args.no_http:
        print(f"http on {args.host}:{args.http_port}")
    asyncio.run(serve(app, config))  # type: ignore[arg-type]
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
