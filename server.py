#!/usr/bin/env python3
import json
import mimetypes
import os
import re
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

ROOT = Path(__file__).resolve().parent
DATA_ROOT = Path(os.environ.get("RESULTS_DATA_DIR", "/data"))
ITEMS_DIR = DATA_ROOT / "items"
FILES_DIR = DATA_ROOT / "files"
UPLOADS_DIR = DATA_ROOT / "uploads"
UPLOAD_META_DIR = DATA_ROOT / "upload-meta"
HERMES_UPSTREAM = os.environ.get(
    "HERMES_UPSTREAM", "http://hermes-agent-8yvs-hermes-agent-1:8642"
).rstrip("/")
API_SERVER_KEY = os.environ.get("API_SERVER_KEY", "").strip()
SESSION_PREFIX = os.environ.get("UI_SESSION_PREFIX", "ui_dashboard")
MAX_ITEMS = 100
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_CHAT_CHARS = 12000
UI_BUILD = "vertical-slice-20260724-1"

ITEMS_DIR.mkdir(parents=True, exist_ok=True)
FILES_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_META_DIR.mkdir(parents=True, exist_ok=True)


def _json_bytes(payload) -> bytes:
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def _safe_user(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9._-]+", "-", value)
    return value[:60] or "default"


def _safe_filename(value: str) -> str:
    value = Path(value or "").name
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value)[:180]
    return value or f"upload-{int(time.time())}.bin"


def _load_result_items(limit: int = 20):
    items = []
    for path in sorted(
        ITEMS_DIR.glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    ):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        if payload.get("file"):
            payload["file_url"] = payload["file"].replace(
                "/api/results/files/", "/api/inbox/files/"
            )
        payload["kind"] = "result"
        items.append(payload)
        if len(items) >= max(limit * 8, 120):
            break
    return items


def _load_upload_items(limit: int = 20):
    items = []
    for path in sorted(
        UPLOAD_META_DIR.glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    ):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        payload["kind"] = "upload"
        items.append(payload)
        if len(items) >= limit:
            break
    return items


def _combined_inbox(limit: int = 24):
    items = _load_result_items(limit) + _load_upload_items(limit)
    items.sort(
        key=lambda item: (
            1 if (item.get("file") or item.get("file_url")) else 0,
            item.get("created_at", ""),
        ),
        reverse=True,
    )
    return [_with_provenance(item) for item in items[:limit]]


def _with_provenance(item: dict) -> dict:
    """Attach traceability without rewriting the underlying result record."""
    enriched = dict(item)
    kind = enriched.get("kind", "unknown")
    item_id = str(enriched.get("id", ""))
    enriched.setdefault("source_type", "results-data" if kind == "result" else "ui-upload")
    enriched.setdefault("source_id", item_id or "UNAVAILABLE")
    enriched.setdefault("last_verified_at", enriched.get("created_at") or "UNAVAILABLE")
    enriched.setdefault("health_state", "observed")
    enriched.setdefault("data_origin", "file-backed-results-data")
    return enriched


def _hermes_headers(session_id: str | None = None) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {API_SERVER_KEY}",
        "Content-Type": "application/json",
    }
    if session_id:
        headers["X-Hermes-Session-Id"] = session_id
        headers["X-Hermes-Session-Key"] = session_id
    return headers


def _hermes_request(path: str, payload: dict | None = None, method: str = "GET", session_id: str | None = None):
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        HERMES_UPSTREAM + path,
        data=data,
        headers=_hermes_headers(session_id),
        method=method,
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body) if body else {}


def _ensure_session(session_id: str):
    try:
        _hermes_request(f"/api/sessions/{quote(session_id)}")
        return
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
    _hermes_request(
        "/api/sessions",
        {"session_id": session_id, "title": f"UI session {session_id}"},
        method="POST",
    )


class Handler(BaseHTTPRequestHandler):
    server_version = "AgentHostUI/2.0"

    def _common_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")

    def _send_json(self, payload, status=200):
        body = _json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._common_headers()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, download_name: str | None = None):
        if not path.is_file():
            self._send_json({"error": "not_found"}, 404)
            return
        data = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        if download_name:
          self.send_header("Content-Disposition", f'inline; filename="{download_name}"')
        self._common_headers()
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_body(self, maximum: int) -> bytes | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json({"error": "invalid_content_length"}, 400)
            return None
        if length < 0 or length > maximum:
            self._send_json({"error": "payload_too_large"}, 413)
            return None
        return self.rfile.read(length)

    def _read_json(self):
        raw = self._read_body(MAX_UPLOAD_BYTES)
        if raw is None:
            return None
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            self._send_json({"error": "invalid_json"}, 400)
            return None
        if not isinstance(payload, dict):
            self._send_json({"error": "json_object_required"}, 400)
            return None
        return payload

    def _session_id(self) -> str:
        remote_user = (
            self.headers.get("Remote-User")
            or self.headers.get("X-Forwarded-User")
            or "owner"
        )
        return f"{SESSION_PREFIX}_{_safe_user(remote_user)}"

    def _serve_static(self, path: str):
        rel = path.lstrip("/") or "index.html"
        if rel.startswith("api/"):
            self._send_json({"error": "not_found"}, 404)
            return
        target = (ROOT / rel).resolve()
        if ROOT not in target.parents and target != ROOT:
            self._send_json({"error": "forbidden"}, 403)
            return
        if target.is_dir():
            target = target / "index.html"
        if not target.exists():
            target = ROOT / "index.html"
        self._send_file(target, target.name)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path in ("/health", "/api/health"):
            self._send_json({"ok": True, "service": "ui-dashboard"})
            return
        if path == "/api/system/overview":
            self._send_json({
                "service": "ui-dashboard",
                "build": UI_BUILD,
                "health_state": "healthy",
                "data_origin": "runtime-and-file-backed-observations",
                "last_verified_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "sources": {
                    "hermes_chat": {
                        "source_type": "hermes-api",
                        "source_id": HERMES_UPSTREAM,
                        "health_state": "configured",
                        "data_origin": "live-session-api",
                    },
                    "inbox": {
                        "source_type": "filesystem",
                        "source_id": str(DATA_ROOT),
                        "health_state": "available",
                        "data_origin": "shared-results-data",
                    },
                    "knowledge_graph": {
                        "source_type": "obsidian-vault",
                        "source_id": "UNAVAILABLE",
                        "health_state": "UNAVAILABLE",
                        "data_origin": "no-vault-mounted-in-ui-container",
                    },
                },
            })
            return
        if path == "/api/knowledge/graph":
            self._send_json({
                "status": "UNAVAILABLE",
                "reason": "No Obsidian vault is mounted into the UI container; no graph data was invented.",
                "source_type": "obsidian-vault",
                "source_id": "UNAVAILABLE",
                "last_verified_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "health_state": "UNAVAILABLE",
                "data_origin": "no-vault-mounted-in-ui-container",
                "nodes": [],
                "edges": [],
            })
            return
        if path in ("/api/inbox", "/api/inbox/"):
            query = parse_qs(parsed.query)
            try:
                limit = int(query.get("limit", ["24"])[0])
            except ValueError:
                limit = 24
            limit = max(1, min(limit, MAX_ITEMS))
            self._send_json({"items": _combined_inbox(limit), "limit": limit, "data_origin": "shared-results-data"})
            return
        if path.startswith("/api/inbox/files/"):
            name = Path(path.removeprefix("/api/inbox/files/")).name
            if not re.fullmatch(r"[A-Za-z0-9._-]+", name):
                self._send_json({"error": "not_found"}, 404)
                return
            for candidate in (FILES_DIR / name, UPLOADS_DIR / name):
                if candidate.is_file():
                    self._send_file(candidate, name)
                    return
            self._send_json({"error": "not_found"}, 404)
            return
        if path.startswith("/api/inbox/item/"):
            item_id = Path(path.removeprefix("/api/inbox/item/")).stem
            if not re.fullmatch(r"[A-Za-z0-9._-]+", item_id):
                self._send_json({"error": "not_found"}, 404)
                return
            candidates = [
                ITEMS_DIR / f"{item_id}.json",
                UPLOAD_META_DIR / f"{item_id}.json",
            ]
            for candidate in candidates:
                if candidate.is_file():
                    try:
                        payload = json.loads(candidate.read_text(encoding="utf-8"))
                    except Exception:
                        self._send_json({"error": "invalid_item"}, 500)
                        return
                    if payload.get("file"):
                        payload["file_url"] = payload["file"].replace(
                            "/api/results/files/", "/api/inbox/files/"
                        )
                    self._send_json(_with_provenance(payload))
                    return
            self._send_json({"error": "not_found"}, 404)
            return
        if path == "/api/chat/history":
            session_id = self._session_id()
            try:
                _ensure_session(session_id)
                data = _hermes_request(f"/api/sessions/{quote(session_id)}/messages")
            except Exception as exc:
                self._send_json({"error": "chat_history_failed", "detail": str(exc)[:400]}, 502)
                return
            messages = []
            for row in data.get("data", [])[-40:]:
                if not isinstance(row, dict):
                    continue
                role = row.get("role")
                content = row.get("content")
                if isinstance(content, list):
                    text_parts = []
                    for block in content:
                        if isinstance(block, dict) and block.get("text"):
                            text_parts.append(str(block["text"]))
                    content = "\n".join(text_parts)
                messages.append({
                    "role": role,
                    "content": str(content or ""),
                })
            self._send_json({"session_id": session_id, "messages": messages})
            return
        self._serve_static(path)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/chat":
            payload = self._read_json()
            if payload is None:
                return
            message = str(payload.get("message") or "").strip()[:MAX_CHAT_CHARS]
            if not message:
                self._send_json({"error": "message_required"}, 400)
                return
            session_id = self._session_id()
            try:
                _ensure_session(session_id)
                data = _hermes_request(
                    f"/api/sessions/{quote(session_id)}/chat",
                    {"message": message},
                    method="POST",
                    session_id=session_id,
                )
            except Exception as exc:
                self._send_json({"error": "chat_failed", "detail": str(exc)[:500]}, 502)
                return
            reply = (((data.get("message") or {}).get("content")) or "").strip()
            self._send_json({"ok": True, "session_id": session_id, "reply": reply})
            return

        if path == "/api/inbox/upload":
            raw = self._read_body(MAX_UPLOAD_BYTES)
            if raw is None:
                return
            filename = _safe_filename(self.headers.get("X-Filename", "upload.bin"))
            sender = (self.headers.get("X-Sender") or "user-upload").strip()[:80]
            title = (self.headers.get("X-Title") or filename).strip()[:200]
            item_id = f"upload-{int(time.time())}-{filename}"
            stored = UPLOADS_DIR / item_id
            stored.write_bytes(raw)
            meta = {
                "id": item_id,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "service": sender,
                "title": title,
                "type": "file",
                "tags": ["upload", "inbox"],
                "content": "",
                "file_url": f"/api/inbox/files/{item_id}",
                "file": f"/api/inbox/files/{item_id}",
                "kind": "upload",
                "source_type": "ui-upload",
                "source_id": item_id,
                "last_verified_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "health_state": "observed",
                "data_origin": "file-backed-results-data",
            }
            (UPLOAD_META_DIR / f"{item_id}.json").write_text(
                json.dumps(meta, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self._send_json({"ok": True, "item": meta}, 201)
            return

        self._send_json({"error": "not_found"}, 404)

    def log_message(self, fmt, *args):
        print(f"{self.client_address[0]} - {fmt % args}", flush=True)


class Server(ThreadingHTTPServer):
    daemon_threads = True


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    Server(("0.0.0.0", port), Handler).serve_forever()
