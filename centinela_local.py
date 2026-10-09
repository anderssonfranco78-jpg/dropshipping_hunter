"""Centinela local del Dropshipping Hunter.

Sirve el panel (index.html) en http://127.0.0.1:8765 y expone dos endpoints que usa el botón
"Actualizar ahora" del panel:

    GET  /api/status   -> estado de la última corrida + últimas líneas del log
    POST /api/refresh  -> lanza `python main.py` (el Hunter hace el rastreo, no el panel)

La corrida es 100% en segundo plano (Chrome sin ventana). Nunca abre tu navegador.

Uso:
    python centinela_local.py            # o doble clic en iniciar_centinela.bat
    python centinela_local.py --port 9000 --no-browser
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import subprocess
import sys
import threading
import time
import webbrowser
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOCAL_HOSTS = ("127.0.0.1", "localhost")


class Job:
    """Single refresh job. Only one run at a time."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.running = False
        self.started_at: float | None = None
        self.finished_at: float | None = None
        self.exit_code: int | None = None
        self.log: collections.deque[str] = collections.deque(maxlen=400)

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "available": True,
                "running": self.running,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "exit_code": self.exit_code,
                "log": list(self.log)[-14:],
            }

    def start(self) -> bool:
        with self.lock:
            if self.running:
                return False
            self.running = True
            self.started_at = time.time()
            self.finished_at = None
            self.exit_code = None
            self.log.clear()
        threading.Thread(target=self._run, daemon=True).start()
        return True

    def _run(self) -> None:
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")  # sin --scrape-suppliers: no hay Selenium ni ventanas
        try:
            proc = subprocess.Popen(
                [sys.executable, "main.py"], cwd=ROOT, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
            )
            log_path = ROOT / "data" / "ultima_corrida.log"  # full log kept for diagnosis
            with open(log_path, "w", encoding="utf-8") as log_file:
                for line in proc.stdout:  # type: ignore[union-attr]
                    log_file.write(line)
                    log_file.flush()
                    with self.lock:
                        self.log.append(line.rstrip())
            code = proc.wait()
        except Exception as exc:  # could not even start the Hunter
            with self.lock:
                self.log.append(f"No se pudo iniciar el Hunter: {exc}")
            code = -1
        with self.lock:
            self.running = False
            self.finished_at = time.time()
            self.exit_code = code


JOB = Job()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")  # the panel must always see fresh data
        super().end_headers()

    def _json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _same_origin(self) -> bool:
        """Block other websites from triggering a refresh through the user's browser."""
        origin = self.headers.get("Origin")
        if origin is None:
            return True
        host = origin.split("://", 1)[-1].split(":")[0]
        return host in LOCAL_HOSTS

    def do_GET(self) -> None:
        if self.path.split("?")[0] == "/api/status":
            return self._json(JOB.snapshot())
        return super().do_GET()

    def do_POST(self) -> None:
        if self.path.split("?")[0] != "/api/refresh":
            return self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        if not self._same_origin() or self.headers.get("X-Hunter") != "1":
            return self._json({"error": "forbidden"}, HTTPStatus.FORBIDDEN)
        started = JOB.start()
        return self._json({"started": started, **JOB.snapshot()}, HTTPStatus.ACCEPTED if started else HTTPStatus.CONFLICT)

    def log_message(self, fmt: str, *args) -> None:  # keep the console readable
        if "/api/status" not in (args[0] if args else ""):
            super().log_message(fmt, *args)


def main() -> int:
    parser = argparse.ArgumentParser(description="Centinela local del Dropshipping Hunter")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)  # localhost only, never the LAN
    url = f"http://127.0.0.1:{args.port}/index.html"
    print("=" * 70)
    print(" CENTINELA LOCAL — Dropshipping Hunter")
    print(f" Panel: {url}")
    print(" Pulsa 'Actualizar ahora' en el panel para que el Hunter rastree.")
    print(" Ctrl+C para detener.")
    print("=" * 70)
    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nCentinela detenido.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
