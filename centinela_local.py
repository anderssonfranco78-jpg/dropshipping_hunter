"""Centinela local del Dropshipping Hunter: el motor que corre en TU PC.

Sirve el panel (index.html) en http://127.0.0.1:8765 y le da botones que funcionan de verdad:

    GET  /api/status   -> estado de la corrida + últimas líneas del log + estado de la sincronización
    POST /api/refresh  -> lanza `python main.py` (el Hunter rastrea; el panel solo lo dispara)
    POST /api/product  -> crea / edita / borra un producto en data/user_products.json
                          (lo que antes había que editar a mano: costos de DSers, "en mi tienda", etc.)
    POST /api/sync     -> sube los datos a GitHub para verlos desde el teléfono

Tras cada corrida exitosa y cada cambio de producto, los datos se suben solos a GitHub (si este PC
tiene permiso para hacer `git push`), así el panel del teléfono (GitHub Pages) muestra lo mismo.

Todo corre en segundo plano y sin ventanas. Solo escucha en 127.0.0.1 (nunca en la red local).

Uso:
    python centinela_local.py                  # o doble clic en "Abrir Hunter" (escritorio)
    pythonw centinela_local.py --no-browser    # lo que arranca con Windows (invisible)
    python centinela_local.py --no-sync        # sin subir datos a GitHub
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOCAL_HOSTS = ("127.0.0.1", "localhost")
PRODUCTS = ROOT / "data" / "user_products.json"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # Windows: never flash a console window

# pythonw has no console: keep a log file instead of crashing on sys.stderr.write
if sys.stderr is None or sys.stdout is None:
    _log = open(ROOT / "data" / "centinela.log", "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stdout or _log
    sys.stderr = sys.stderr or _log

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from hunter.n8n_bridge import bridge_status, sync_dsers_stock_payload  # noqa: E402
from hunter.user_products import product_to_candidate  # noqa: E402  (validation = same rules as the robot)


# ----------------------------------------------------------------------------------------------
# Sincronización con GitHub (PC -> teléfono)
# ----------------------------------------------------------------------------------------------
SYNC_PATHS = ["data/user_products.json", "data/radar_ideas.json", "data/candidates.json", "data/audit_results.json",
              "data/data_health.json", "data/dashboard_data.js", "data/radar.json", "data/trends_cache.json",
              "data/history", "assets/images", "cuentas.html", "ranking_productos.html", "ranking_productos.png", "dossier_productos_ganadores.md"]


class Sync:
    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled
        self.lock = threading.Lock()
        self.state = {"enabled": enabled, "running": False, "ok": None, "at": None, "message": "Aún no se ha sincronizado"}

    def snapshot(self) -> dict:
        with self.lock:
            return dict(self.state)

    def _git(self, *args: str, timeout: int = 90) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout, creationflags=NO_WINDOW)

    def _merge_trends_cache(self) -> None:
        """Preserve the newest measurement per keyword across local disk and git refs before staging."""
        cache_path = ROOT / "data" / "trends_cache.json"
        if not cache_path.exists():
            return
        try:
            merged = json.loads(cache_path.read_text(encoding="utf-8"))
            if not isinstance(merged, dict):
                merged = {}
        except (OSError, ValueError):
            merged = {}
        for ref in (":2:data/trends_cache.json", ":3:data/trends_cache.json", "HEAD:data/trends_cache.json"):
            res = self._git("show", ref)
            if res.returncode != 0:
                continue
            try:
                other = json.loads(res.stdout)
            except ValueError:
                continue
            if not isinstance(other, dict):
                continue
            for k, v in other.items():
                if not isinstance(v, dict):
                    continue
                cur = merged.get(k)
                cur_ts = (cur.get("_measured_ts") or cur.get("until_ts") or 0) if isinstance(cur, dict) else 0
                new_ts = v.get("_measured_ts") or v.get("until_ts") or 0
                if not isinstance(cur, dict) or new_ts > cur_ts:
                    merged[k] = v
        if merged:
            cache_path.write_text(json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8")

    def start(self, reason: str) -> None:
        if not self.enabled:
            return
        with self.lock:
            if self.state["running"]:
                return
            self.state["running"] = True
        threading.Thread(target=self._run, args=(reason,), daemon=True).start()

    def _run(self, reason: str) -> None:
        ok, msg = False, ""
        try:
            if self._git("rev-parse", "--is-inside-work-tree").returncode != 0:
                raise RuntimeError("esta carpeta no es un repositorio de git")
            self._merge_trends_cache()
            existing = [p for p in SYNC_PATHS if (ROOT / p).exists()]
            self._git("add", "--", *existing)
            if self._git("diff", "--cached", "--quiet").returncode != 0:
                commit = self._git("commit", "-m", f"🖥️ chore(pc): {reason} [skip ci]")
                if commit.returncode != 0:
                    raise RuntimeError(commit.stderr.strip() or commit.stdout.strip())
            pull = self._git("pull", "--rebase", "--autostash", "-X", "theirs", timeout=120)
            if pull.returncode != 0:
                self._git("rebase", "--abort")
                self._git("reset", "--merge")
                raise RuntimeError("no se pudo combinar con GitHub: " + (pull.stderr.strip() or pull.stdout.strip())[:300])
            push = self._git("push", timeout=120)
            if push.returncode != 0:
                raise RuntimeError("GitHub rechazó la subida: " + (push.stderr.strip() or push.stdout.strip())[:300])
            ok, msg = True, "Datos subidos a GitHub: el teléfono los verá en 1–2 minutos"
        except Exception as exc:  # never break the panel because of git
            msg = str(exc)
        with self.lock:
            self.state.update({"running": False, "ok": ok, "at": time.time(), "message": msg})


# ----------------------------------------------------------------------------------------------
# Corrida del Hunter
# ----------------------------------------------------------------------------------------------
class Job:
    """Single refresh job. Only one run at a time."""

    def __init__(self, sync: Sync) -> None:
        self.sync = sync
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
                "can_edit": True,
                "running": self.running,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "exit_code": self.exit_code,
                "log": list(self.log)[-14:],
                "sync": self.sync.snapshot(),
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
                [sys.executable, "main.py"], cwd=ROOT, env=env, creationflags=NO_WINDOW,
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
        if code == 0:
            self.sync.start("corrida del Hunter en el PC")


# ----------------------------------------------------------------------------------------------
# Edición de productos (data/user_products.json) desde el panel
# ----------------------------------------------------------------------------------------------
PRODUCT_LOCK = threading.Lock()
TOP_FIELDS = ("name", "category", "source_url", "srp_usd", "unit_cost_usd", "shipping_cost_usd", "target_variant_name",
              "verified_stock", "verified_date", "notes", "trends_keyword", "video_keyword", "en_tienda", "image_url",
              "description")  # ordered: new products are written in a readable field order
SHIP_FIELDS = {"days_min", "days_max", "carrier"}
RULE_FIELDS = {"demo_visual_speed_sec", "pain_level_score", "retail_availability_score", "has_fragile_material",
               "has_sizing_requirements", "ad_active_days", "competitor_ad_count", "google_trends_momentum"}


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:48] or "producto"


def save_product(body: dict) -> dict:
    """Create, update or delete one product. Validates with the robot's own rules before writing."""
    with PRODUCT_LOCK:
        raw = json.loads(PRODUCTS.read_text(encoding="utf-8")) if PRODUCTS.exists() else {"products": []}
        items = raw["products"] if isinstance(raw, dict) else raw
        pid = str(body.get("id") or "").strip()
        index = next((i for i, p in enumerate(items) if p.get("id") == pid), None)

        if body.get("_delete"):
            if index is None:
                raise ValueError("ese producto no existe")
            removed = items.pop(index)
            message = f"{removed.get('name', pid)} quitado de la evaluación"
        else:
            item = dict(items[index]) if index is not None else {}
            if index is None:
                pid = pid or slugify(str(body.get("video_keyword") or body.get("name") or ""))
                if any(p.get("id") == pid for p in items):
                    raise ValueError(f"ya existe un producto con id '{pid}'")
                item["id"] = pid
            for key in (k for k in TOP_FIELDS if k in body):
                value = body[key]
                item[key] = value.strip() if isinstance(value, str) else value
            for group, allowed in (("shipping", SHIP_FIELDS), ("rule_inputs", RULE_FIELDS)):
                if isinstance(body.get(group), dict):
                    merged = dict(item.get(group) or {})
                    merged.update({k: v for k, v in body[group].items() if k in allowed})
                    item[group] = merged
            if not item.get("source_url"):
                q = item.get("video_keyword") or item.get("name") or pid
                item["source_url"] = "https://www.aliexpress.com/wholesale?SearchText=" + urllib.request.quote(str(q))
            product_to_candidate(item)  # raises ValueError with a readable message
            if index is None:
                items.append(item)
            else:
                items[index] = item
            message = f"{item.get('name', pid)} guardado"

        tmp = PRODUCTS.with_suffix(".tmp")
        tmp.write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(tmp, PRODUCTS)
        return {"ok": True, "id": pid, "message": message}


# ----------------------------------------------------------------------------------------------
# HTTP
# ----------------------------------------------------------------------------------------------
SYNC = Sync(enabled=True)
JOB = Job(SYNC)


HUB_ROOT = ROOT.parent / "multi_account_hub"
HUB_DATA = HUB_ROOT / "data" / "negocios.json"


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def translate_path(self, path: str) -> str:
        clean = path.split("?", 1)[0].split("#", 1)[0]
        if clean.startswith("/multi_account_hub/") and HUB_ROOT.exists():
            rel = clean[len("/multi_account_hub/"):].lstrip("/") or "index.html"
            target = (HUB_ROOT / rel).resolve()
            if str(target).startswith(str(HUB_ROOT.resolve())):
                return str(target)
        return super().translate_path(path)

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
        """Block other websites from triggering actions through the user's browser."""
        origin = self.headers.get("Origin")
        if origin is None:
            return True
        host = origin.split("://", 1)[-1].split(":")[0]
        return host in LOCAL_HOSTS

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length > 200_000:
            raise ValueError("petición demasiado grande")
        data = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(data, dict):
            raise ValueError("se esperaba un objeto JSON")
        return data

    def do_GET(self) -> None:
        route = self.path.split("?")[0]
        if route == "/api/status":
            return self._json(JOB.snapshot())
        if route == "/api/hub/status":
            return self._json({"available": HUB_ROOT.exists(), "can_edit": HUB_DATA.exists()})
        if route == "/api/n8n/status":
            return self._json(bridge_status(PRODUCTS))
        return super().do_GET()

    def do_POST(self) -> None:
        route = self.path.split("?")[0]
        if route == "/api/n8n/sync-stock":
            if not self._same_origin():
                return self._json({"error": "forbidden"}, HTTPStatus.FORBIDDEN)
            try:
                result = sync_dsers_stock_payload(self._body(), products_path=PRODUCTS)
            except (ValueError, TypeError, KeyError) as exc:
                return self._json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
            SYNC.start("stock sincronizado desde DSers/Shopify vía n8n")
            return self._json(result)
        if route in ("/api/hub/refresh", "/api/hub/save", "/api/hub/action"):
            if not self._same_origin():
                return self._json({"error": "forbidden"}, HTTPStatus.FORBIDDEN)
            if route == "/api/hub/refresh" and (HUB_ROOT / "hub_engine.py").exists():
                proc = subprocess.run(
                    [sys.executable, str(HUB_ROOT / "hub_engine.py"), "refresh", "--all"],
                    cwd=str(HUB_ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=NO_WINDOW,
                )
                return self._json({"ok": proc.returncode == 0, "output": (proc.stdout or "")[-400:]})
            if route == "/api/hub/action" and (HUB_ROOT / "hub_engine.py").exists():
                try:
                    payload = self._body()
                    act = str(payload.get("action") or "").strip()
                    bid = str(payload.get("business_id") or "").strip()
                    cmd = [sys.executable, str(HUB_ROOT / "hub_engine.py")]
                    if act == "refresh":
                        cmd += ["refresh", "--all"]
                    elif act == "log_metrics" and bid:
                        cmd += [
                            "log-metrics", "--business-id", bid,
                            "--videos", str(int(payload.get("videos", 0))),
                            "--views", str(int(payload.get("views", 0))),
                            "--clicks", str(int(payload.get("clicks", 0))),
                        ]
                    elif act == "set_status" and bid:
                        cmd += ["set-status", "--business-id", bid, "--status", str(payload.get("status") or "activo")]
                    elif act == "warmup_day" and bid:
                        cmd += ["warmup", "--business-id", bid, "--day", str(int(payload.get("day", 1)))]
                    else:
                        return self._json({"ok": False, "error": "invalid hub action"}, HTTPStatus.BAD_REQUEST)
                    proc = subprocess.run(
                        cmd, cwd=str(HUB_ROOT), capture_output=True, text=True,
                        encoding="utf-8", errors="replace", creationflags=NO_WINDOW,
                    )
                    data = json.loads(HUB_DATA.read_text(encoding="utf-8")) if HUB_DATA.exists() else {}
                    return self._json({"ok": proc.returncode == 0, "output": (proc.stdout or "")[-400:], "data": data})
                except Exception as exc:
                    return self._json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
            if route == "/api/hub/save" and HUB_DATA.exists():
                try:
                    payload = self._body()
                    if isinstance(payload.get("businesses"), list):
                        tmp = HUB_DATA.with_suffix(".tmp")
                        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                        os.replace(tmp, HUB_DATA)
                        return self._json({"ok": True})
                except Exception as exc:
                    return self._json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return self._json({"ok": False, "error": "hub unavailable"}, HTTPStatus.BAD_REQUEST)
        if route not in ("/api/refresh", "/api/product", "/api/sync"):
            return self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        if not self._same_origin() or self.headers.get("X-Hunter") != "1":
            return self._json({"error": "forbidden"}, HTTPStatus.FORBIDDEN)
        if route == "/api/refresh":
            started = JOB.start()
            return self._json({"started": started, **JOB.snapshot()}, HTTPStatus.ACCEPTED if started else HTTPStatus.CONFLICT)
        if route == "/api/sync":
            SYNC.start("sincronización pedida desde el panel")
            return self._json({"ok": True, **SYNC.snapshot()}, HTTPStatus.ACCEPTED)
        try:
            result = save_product(self._body())
        except (ValueError, TypeError, KeyError) as exc:
            return self._json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
        SYNC.start("producto editado desde el panel")
        return self._json(result)

    def log_message(self, fmt: str, *args) -> None:  # keep the log readable
        line = str(args[0]) if args else ""
        if "/api/status" not in line and "dashboard_data.js" not in line:  # periodic panel polls
            super().log_message(fmt, *args)


def already_running(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=2) as resp:
            return json.loads(resp.read()).get("available") is True
    except Exception:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Centinela local del Dropshipping Hunter")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--no-sync", action="store_true", help="no subir los datos a GitHub")
    args = parser.parse_args()
    SYNC.enabled = not args.no_sync
    SYNC.state["enabled"] = SYNC.enabled
    url = f"http://127.0.0.1:{args.port}/index.html"

    if already_running(args.port):  # double click while it already runs in the background: just open it
        if not args.no_browser:
            webbrowser.open(url)
        return 0

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)  # localhost only, never the LAN
    print("=" * 70)
    print(" CENTINELA LOCAL — Dropshipping Hunter")
    print(f" Panel: {url}")
    print(" Pulsa 'Actualizar ahora' en el panel para que el Hunter rastree.")
    print(" Sincronización con GitHub: " + ("activada" if SYNC.enabled else "apagada"))
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
