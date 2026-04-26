"""Minimal local HTTP API for Desktop and Web frontends."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from zephyr_tools.client import ZephyrToolsClient
from zephyr_tools.errors import ZephyrToolsError


def run_api_server(
    work_dir: str | Path | None = None,
    host: str = "127.0.0.1",
    port: int = 8765,
    default_board: str = "nucleo_f411re",
) -> int:
    client = ZephyrToolsClient(work_dir=work_dir, default_board=default_board)
    handler = _make_handler(client)
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Zephyr Tools API listening on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


def _make_handler(client: ZephyrToolsClient):
    class ApiHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            try:
                if parsed.path == "/health":
                    self._json({"ok": True, "name": "zephyr-tools-api"})
                elif parsed.path == "/doctor":
                    self._json([_serialize(check) for check in client.doctor()])
                elif parsed.path == "/boards":
                    name_filter = _first(query, "filter")
                    self._json([_serialize(board) for board in client.list_boards(name_filter)])
                else:
                    self._json({"error": "not found"}, status=404)
            except ZephyrToolsError as exc:
                self._json({"error": str(exc)}, status=400)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            payload = self._payload()
            try:
                if parsed.path == "/projects":
                    project = client.create(
                        payload["name"],
                        board=payload.get("board"),
                        output_dir=payload.get("output_dir"),
                        overwrite=bool(payload.get("overwrite", False)),
                    )
                    self._json(_serialize(project))
                elif parsed.path == "/build":
                    result = client.build(
                        payload["project_dir"],
                        board=payload.get("board"),
                        build_dir=payload.get("build_dir"),
                        pristine=bool(payload.get("pristine", False)),
                    )
                    self._json(_serialize(result))
                elif parsed.path == "/flash":
                    result = client.flash(payload["build_dir"], runner_name=payload.get("runner"))
                    self._json(_serialize(result))
                elif parsed.path == "/generate":
                    project = client.gen(
                        payload["prompt"],
                        payload.get("output_dir", "generated"),
                        board=payload.get("board"),
                    )
                    self._json(_serialize(project))
                elif parsed.path == "/fix":
                    project = client.fix(
                        payload["project_dir"],
                        payload["prompt"],
                        payload["build_error"],
                        board=payload.get("board"),
                    )
                    self._json(_serialize(project))
                else:
                    self._json({"error": "not found"}, status=404)
            except (KeyError, ZephyrToolsError, FileExistsError) as exc:
                self._json({"error": str(exc)}, status=400)

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _payload(self) -> dict[str, Any]:
            length = int(self.headers.get("content-length", "0"))
            if length == 0:
                return {}
            raw = self.rfile.read(length).decode("utf-8")
            return json.loads(raw)

        def _json(self, payload: Any, status: int = 200) -> None:
            body = json.dumps(_serialize(payload), ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("content-type", "application/json; charset=utf-8")
            self.send_header("access-control-allow-origin", "http://localhost:5173")
            self.send_header("access-control-allow-methods", "GET, POST, OPTIONS")
            self.send_header("access-control-allow-headers", "content-type")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self) -> None:
            self._json({"ok": True})

    return ApiHandler


def _first(query: dict[str, list[str]], key: str) -> str | None:
    values = query.get(key)
    return values[0] if values else None


def _serialize(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return {key: _serialize(item) for key, item in asdict(value).items()}
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    return value
