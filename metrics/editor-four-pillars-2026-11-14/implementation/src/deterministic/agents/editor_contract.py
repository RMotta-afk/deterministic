"""Executable HTTP oracle for the pinned Project Editor backend."""

import copy
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from deterministic.agents.validator import ValidationResult


def _port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class _State:
    def __init__(self):
        self.reset()

    def reset(self):
        self.project = {
            "id": "P-1001",
            "name": "Original",
            "sector": "energy",
            "country": "Chile",
            "stage": "idea",
            "key_dates": [{"label": "Tender", "date": "2027-01-01"}],
            "linked_companies": [{"name": "Owner Ltd", "role": "owner"}],
            "internal_code": "must not reach browser",
        }
        self.put_count = 0
        self.timeout_mode = ""
        self.read_status = 200
        self.keys = []
        self.last_write = None


def _handler(state: _State):
    class Upstream(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def _send(self, status, body):
            data = json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _authorized(self):
            key = self.headers.get("X-Api-Key")
            state.keys.append(key)
            if key != "contract-secret":
                self._send(401, {"detail": "bad key"})
                return False
            return True

        def do_GET(self):
            if not self._authorized():
                return
            if state.read_status != 200:
                self._send(state.read_status, {"detail": "unavailable"})
            elif self.path == "/projects":
                self._send(200, [state.project])
            elif self.path == "/projects/P-1001":
                self._send(200, state.project)
            else:
                self._send(404, {"detail": "missing"})

        def do_PUT(self):
            if not self._authorized():
                return
            if self.path != "/projects/P-1001":
                self._send(404, {"detail": "missing"})
                return
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            state.put_count += 1
            state.last_write = body
            if state.timeout_mode != "drop":
                state.project.update(body)
            if state.timeout_mode:
                self._send(504, {"detail": "ambiguous"})
            else:
                self._send(200, state.project)

    return Upstream


def _request(port: int, method: str, path: str, body: dict | None = None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=7) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        return exc.code, json.load(exc)


def _editable(project):
    return {
        key: copy.deepcopy(project[key])
        for key in ("name", "sector", "country", "stage", "key_dates")
    }


def validate_editor(output: Path, source_root: Path | None = None) -> ValidationResult:
    """Compile and exercise the generated Node API against a controlled upstream."""
    source = output / "server.ts"
    if not source.is_file() or not shutil.which("tsc") or not shutil.which("node"):
        return ValidationResult(
            passed=False,
            checks={"syntax_or_compile": False, "behavioral": False},
            output="Editor validation requires server.ts, node, and tsc",
        )
    compiled = output / ".compiled"
    result = subprocess.run(
        [
            "tsc",
            "--target",
            "ES2020",
            "--module",
            "commonjs",
            "--outDir",
            str(compiled),
            str(source),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode:
        return ValidationResult(
            passed=False,
            checks={"syntax_or_compile": False, "behavioral": False},
            output=result.stdout + result.stderr,
        )
    state = _State()
    upstream = ThreadingHTTPServer(("127.0.0.1", 0), _handler(state))
    thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    thread.start()
    port = _port()
    env = os.environ.copy()
    env.update(
        PORT=str(port),
        UPSTREAM_URL=f"http://127.0.0.1:{upstream.server_port}",
        UPSTREAM_API_KEY="contract-secret",
    )
    checks = {}
    errors = []
    with (output / "node-stderr.log").open("w", encoding="utf-8") as stderr:
        process = subprocess.Popen(
            ["node", str(compiled / "server.js")],
            cwd=output,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=stderr,
        )
        try:
            for _ in range(50):
                if process.poll() is not None:
                    raise RuntimeError("generated Node server exited during startup")
                try:
                    _request(port, "GET", "/api/projects")
                    break
                except (OSError, TimeoutError):
                    time.sleep(0.1)
            else:
                raise RuntimeError("generated Node server did not listen")

            def check(name, fn):
                try:
                    fn()
                    checks[name] = True
                except (AssertionError, KeyError, TypeError, ValueError, OSError) as exc:
                    checks[name] = False
                    errors.append(f"{name}: {type(exc).__name__}: {exc}")

            def list_show():
                state.reset()
                status, body = _request(port, "GET", "/api/projects")
                assert status == 200 and len(body["projects"]) == 1
                assert set(body["projects"][0]) == {"id", "name", "sector", "country", "stage"}
                status, body = _request(port, "GET", "/api/projects/P-1001")
                assert status == 200 and body["project"]["name"] == "Original"
                assert "linked_companies" not in body["project"]
                assert "internal_code" not in body["project"]
                assert state.keys and all(key == "contract-secret" for key in state.keys)

            def validation():
                state.reset()
                base = _editable(state.project)
                bad = base | {"name": " ", "stage": "invalid"}
                assert (
                    _request(port, "PUT", "/api/projects/P-1001", {"base": base, "proposed": bad})[
                        0
                    ]
                    == 422
                )
                assert state.put_count == 0
                bad = base | {"key_dates": [{"label": "Tender", "date": "2027-02-31"}]}
                assert (
                    _request(port, "PUT", "/api/projects/P-1001", {"base": base, "proposed": bad})[
                        0
                    ]
                    == 422
                )
                assert state.put_count == 0

            def merge():
                state.reset()
                base = _editable(state.project)
                first = base | {"name": "First"}
                assert (
                    _request(
                        port, "PUT", "/api/projects/P-1001", {"base": base, "proposed": first}
                    )[0]
                    == 200
                )
                state.project["linked_companies"] = [{"name": "Latest Ltd", "role": "developer"}]
                second = base | {"country": "Peru"}
                status, body = _request(
                    port, "PUT", "/api/projects/P-1001", {"base": base, "proposed": second}
                )
                assert status == 200 and body["project"]["name"] == "First"
                assert body["project"]["country"] == "Peru"
                assert state.last_write["linked_companies"] == state.project["linked_companies"]

            def conflict():
                state.reset()
                base = _editable(state.project)
                _request(
                    port,
                    "PUT",
                    "/api/projects/P-1001",
                    {"base": base, "proposed": base | {"name": "First"}},
                )
                status, body = _request(
                    port,
                    "PUT",
                    "/api/projects/P-1001",
                    {"base": base, "proposed": base | {"name": "Second"}},
                )
                assert status == 409 and body["conflicting_fields"] == ["name"]
                assert body["current"]["name"] == "First" and state.put_count == 1

            def key_date_conflict():
                state.reset()
                base = _editable(state.project)
                first = base | {"key_dates": [{"label": "First", "date": "2027-02-01"}]}
                second = base | {"key_dates": [{"label": "Second", "date": "2027-03-01"}]}
                assert (
                    _request(
                        port, "PUT", "/api/projects/P-1001", {"base": base, "proposed": first}
                    )[0]
                    == 200
                )
                status, body = _request(
                    port, "PUT", "/api/projects/P-1001", {"base": base, "proposed": second}
                )
                assert status == 409 and body["conflicting_fields"] == ["key_dates"]
                assert state.put_count == 1

            def key_dates_add_remove():
                state.reset()
                base = _editable(state.project)
                added = base | {
                    "key_dates": base["key_dates"]
                    + [{"label": "Construction", "date": "2028-01-01"}]
                }
                status, body = _request(
                    port, "PUT", "/api/projects/P-1001", {"base": base, "proposed": added}
                )
                assert status == 200 and len(body["project"]["key_dates"]) == 2
                new_base = _editable(body["project"])
                status, body = _request(
                    port,
                    "PUT",
                    "/api/projects/P-1001",
                    {"base": new_base, "proposed": new_base | {"key_dates": []}},
                )
                assert status == 200 and body["project"]["key_dates"] == []

            def no_op():
                state.reset()
                base = _editable(state.project)
                status, body = _request(
                    port, "PUT", "/api/projects/P-1001", {"base": base, "proposed": base}
                )
                assert status == 200 and body["project"]["name"] == "Original"
                assert state.put_count == 0

            def failures():
                state.reset()
                assert _request(port, "GET", "/api/projects/missing")[0] == 404
                state.read_status = 503
                status, body = _request(port, "GET", "/api/projects")
                assert status == 502 and body["code"] == "upstream_unavailable"

            def uncertain(mode):
                state.reset()
                state.timeout_mode = mode
                base = _editable(state.project)
                status, body = _request(
                    port,
                    "PUT",
                    "/api/projects/P-1001",
                    {"base": base, "proposed": base | {"name": "Attempted"}},
                )
                assert status == 504 and body["code"] == "write_uncertain"
                assert body["observed"]["name"] == ("Original" if mode == "drop" else "Attempted")
                assert state.put_count == 1

            for name, fn in (
                ("list_show_key_boundary", list_show),
                ("validation_422", validation),
                ("merge_latest_companies", merge),
                ("conflict_409", conflict),
                ("key_date_conflict_409", key_date_conflict),
                ("key_dates_add_remove", key_dates_add_remove),
                ("unchanged_update_no_put", no_op),
                ("missing_and_upstream_502", failures),
                ("uncertain_applied_504", lambda: uncertain("apply")),
                ("uncertain_dropped_504", lambda: uncertain("drop")),
            ):
                check(name, fn)
        except RuntimeError as exc:
            errors.append(str(exc))
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            upstream.shutdown()
            upstream.server_close()
    checks["syntax_or_compile"] = True
    if source_root is not None:
        try:
            _validate_real_upstream(output, compiled / "server.js", source_root)
            checks["real_upstream_connection"] = True
        except (AssertionError, OSError, RuntimeError, ValueError) as exc:
            checks["real_upstream_connection"] = False
            errors.append(f"real_upstream_connection: {type(exc).__name__}: {exc}")
        frontend_proxy = (source_root / "frontend" / "vite.config.ts").read_text(encoding="utf-8")
        checks["frontend_proxy_configuration"] = (
            "'/api'" in frontend_proxy and "http://127.0.0.1:8080" in frontend_proxy
        )
        if not checks["frontend_proxy_configuration"]:
            errors.append("frontend_proxy_configuration: expected /api forwarding to port 8080")
    checks["behavioral"] = (
        all(value for key, value in checks.items() if key != "syntax_or_compile") and not errors
    )
    return ValidationResult(passed=checks["behavioral"], checks=checks, output="\n".join(errors))


def _validate_real_upstream(output: Path, server_js: Path, source_root: Path) -> None:
    """Check the migrated API against Editor's preserved records service."""
    upstream_port = _port()
    api_port = 8080
    upstream_env = os.environ.copy()
    upstream_env.update(UPSTREAM_SLOW_RATE="0", UPSTREAM_TIMEOUT_RATE="0")
    api_env = os.environ.copy()
    api_env.update(
        PORT=str(api_port),
        UPSTREAM_URL=f"http://127.0.0.1:{upstream_port}",
        UPSTREAM_API_KEY="local-dev-key",
    )
    with (
        (output / "real-upstream-stderr.log").open("w", encoding="utf-8") as upstream_log,
        (output / "real-node-stderr.log").open("w", encoding="utf-8") as node_log,
    ):
        upstream = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "records_api.main:create_app",
                "--factory",
                "--app-dir",
                str(source_root / "upstream"),
                "--host",
                "127.0.0.1",
                "--port",
                str(upstream_port),
            ],
            stdout=subprocess.DEVNULL,
            stderr=upstream_log,
            env=upstream_env,
        )
        api = None
        try:
            for _ in range(50):
                if upstream.poll() is not None:
                    raise RuntimeError("preserved upstream exited during startup")
                try:
                    _request(upstream_port, "GET", "/projects")
                    break
                except (OSError, TimeoutError):
                    time.sleep(0.1)
            else:
                raise RuntimeError("preserved upstream did not listen")
            api = subprocess.Popen(
                ["node", str(server_js)],
                cwd=output,
                env=api_env,
                stdout=subprocess.DEVNULL,
                stderr=node_log,
            )
            for _ in range(50):
                if api.poll() is not None:
                    raise RuntimeError("generated Node API exited during startup")
                try:
                    status, body = _request(api_port, "GET", "/api/projects")
                    break
                except (OSError, TimeoutError):
                    time.sleep(0.1)
            else:
                raise RuntimeError("generated Node API did not listen")
            assert status == 200 and body["projects"]
            project_id = body["projects"][0]["id"]
            status, shown = _request(api_port, "GET", f"/api/projects/{project_id}")
            assert status == 200
            assert "linked_companies" not in shown["project"]
            assert "internal_code" not in shown["project"]
            base = _editable(shown["project"])
            status, saved = _request(
                api_port,
                "PUT",
                f"/api/projects/{project_id}",
                {"base": base, "proposed": base | {"country": "Peru"}},
            )
            assert status == 200 and saved["project"]["country"] == "Peru"
            status, reread = _request(api_port, "GET", f"/api/projects/{project_id}")
            assert status == 200 and reread["project"]["country"] == "Peru"
        finally:
            if api is not None:
                api.terminate()
                try:
                    api.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    api.kill()
                    api.wait(timeout=5)
            upstream.terminate()
            try:
                upstream.wait(timeout=5)
            except subprocess.TimeoutExpired:
                upstream.kill()
                upstream.wait(timeout=5)
