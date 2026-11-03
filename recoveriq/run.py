"""One-command launcher: installs what's missing, builds the web app if needed, starts the server.

    python run.py              # http://localhost:8000
    python run.py --reset      # wipe the demo database and re-seed
    python run.py --port 9000
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
WEB = ROOT / "web"
STATIC = BACKEND / "static"


def sh(cmd: list[str], cwd: Path) -> None:
    print(">", " ".join(cmd))
    subprocess.check_call(cmd, cwd=cwd, shell=os.name == "nt")


def free_port(start: int) -> int:
    import socket
    for port in range(start, start + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("0.0.0.0", port))
                return port
            except OSError:
                continue
    sys.exit(f"No free port between {start} and {start + 49}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")))
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--reset", action="store_true", help="delete the demo database and start fresh")
    ap.add_argument("--rebuild", action="store_true", help="rebuild the web app")
    ap.add_argument("--no-https", action="store_true", help="don't start the https listener for phones")
    args = ap.parse_args()

    try:
        import argon2, cryptography, fastapi, openpyxl, reportlab, sklearn, sqlalchemy, uvicorn  # noqa: F401
        import multipart  # noqa: F401
    except ImportError:
        sh([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], BACKEND)

    if args.rebuild or not (STATIC / "index.html").exists():
        if not shutil.which("npm"):
            sys.exit("Node.js (npm) is needed once to build the web app: https://nodejs.org")
        if not (WEB / "node_modules").exists():
            sh(["npm", "install", "--no-audit", "--no-fund"], WEB)
        sh(["npm", "run", "build"], WEB)

    if args.reset:
        data = BACKEND / "data"
        for f in data.glob("recoveriq.db*"):
            f.unlink()
        print("Demo database removed; it will be re-seeded on start.")

    port = free_port(args.port)
    if port != args.port:
        print(f"Port {args.port} is busy, using {port} instead.")
    os.environ["PORT"] = str(port)
    os.chdir(BACKEND)
    sys.path.insert(0, str(BACKEND))
    import asyncio
    import uvicorn

    servers = [uvicorn.Server(uvicorn.Config("app.main:app", host=args.host, port=port, log_level="info", proxy_headers=True))]
    https_port = None
    if not args.no_https:
        from app.api.admin import lan_ips
        from app.tls import ensure_cert
        https_port = free_port(port + 443 if port + 443 < 65535 else 8443)
        os.environ["HTTPS_PORT"] = str(https_port)
        cert, key = ensure_cert(BACKEND / "data" / "tls", lan_ips())
        # second listener on the same app; lifespan off so start-up jobs run once
        servers.append(uvicorn.Server(uvicorn.Config("app.main:app", host=args.host, port=https_port, log_level="warning",
                                                     ssl_certfile=str(cert), ssl_keyfile=str(key), lifespan="off")))
    print(f"\n  RecoverIQ  ->  http://localhost:{port}\n  Agent app  ->  http://localhost:{port}/agent\n"
          f"  API docs   ->  http://localhost:{port}/api/docs", flush=True)
    if https_port:
        from app.api.admin import lan_ips
        for ip in lan_ips():
            print(f"  Phones     ->  https://{ip}:{https_port}/agent   (self-signed: tap Advanced > Proceed once)", flush=True)
    print("  Demo password for every account: Demo@1234\n", flush=True)

    async def serve_all():
        await asyncio.gather(*(s.serve() for s in servers))
    asyncio.run(serve_all())


if __name__ == "__main__":
    main()
