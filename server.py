#!/usr/bin/env python3
import json
import mimetypes
import os
import re
import threading
import time
import uuid
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
WORKFLOW_ROOT = DATA_ROOT / "workflows"
TASKS_DIR = WORKFLOW_ROOT / "tasks"
RUNS_DIR = WORKFLOW_ROOT / "runs"
EVENTS_DIR = WORKFLOW_ROOT / "events"
ARTIFACTS_DIR = WORKFLOW_ROOT / "artifacts"
WORKFLOW_LOCK = threading.RLock()

ITEMS_DIR.mkdir(parents=True, exist_ok=True)
FILES_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_META_DIR.mkdir(parents=True, exist_ok=True)
for _directory in (TASKS_DIR, RUNS_DIR, EVENTS_DIR, ARTIFACTS_DIR):
    _directory.mkdir(parents=True, exist_ok=True)


def _json_bytes(payload) -> bytes:
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:16]}"


def _atomic_json(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _load_json(path: Path) -> dict | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _persist(directory: Path, identifier: str, payload: dict) -> None:
    with WORKFLOW_LOCK:
        _atomic_json(directory / f"{identifier}.json", payload)


def _append_event(run_id: str, task_id: str, event_type: str, status: str, message: str, metadata: dict | None = None) -> dict:
    event = {
        "id": _new_id("event"),
        "run_id": run_id,
        "task_id": task_id,
        "event_type": event_type,
        "status": status,
        "timestamp": _now(),
        "source": "ui-dashboard",
        "message": message[:500],
        "metadata": metadata or {},
    }
    path = EVENTS_DIR / f"{run_id}.jsonl"
    with WORKFLOW_LOCK:
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


def _read_events(run_id: str) -> list[dict]:
    path = EVENTS_DIR / f"{run_id}.jsonl"
    if not path.is_file():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            events.append(item)
    return events


def _update_task(task_id: str, **changes) -> dict | None:
    path = TASKS_DIR / f"{task_id}.json"
    task = _load_json(path)
    if task is None:
        return None
    task.update(changes)
    task["updated_at"] = _now()
    _persist(TASKS_DIR, task_id, task)
    return task


def _update_run(run_id: str, **changes) -> dict | None:
    path = RUNS_DIR / f"{run_id}.json"
    run = _load_json(path)
    if run is None:
        return None
    run.update(changes)
    _persist(RUNS_DIR, run_id, run)
    return run


def _task_artifact(task_id: str, run_id: str, content: str, conversation_id: str, title: str) -> dict:
    artifact_id = _new_id("artifact")
    artifact = {
        "id": artifact_id,
        "task_id": task_id,
        "run_id": run_id,
        "conversation_id": conversation_id,
        "title": title[:200],
        "mime_type": "text/markdown",
        "storage_path": str(ARTIFACTS_DIR / f"{artifact_id}.json"),
        "source_type": "hermes-session-api",
        "source_id": conversation_id,
        "created_at": _now(),
        "summary": content[:300],
        "content": content,
        "metadata": {"execution": "Hermes Session API", "response_captured": True},
        "health_state": "observed",
        "data_origin": "ui-workflow-run",
        "last_verified_at": _now(),
    }
    _persist(ARTIFACTS_DIR, artifact_id, artifact)
    inbox_item = {
        "id": artifact_id,
        "created_at": artifact["created_at"],
        "service": "hermes-workflow",
        "title": artifact["title"],
        "type": "artifact",
        "tags": ["artifact", "workflow", task_id, run_id],
        "content": content,
        "artifact_id": artifact_id,
        "task_id": task_id,
        "run_id": run_id,
        "conversation_id": conversation_id,
        "kind": "result",
        "source_type": artifact["source_type"],
        "source_id": artifact["source_id"],
        "last_verified_at": artifact["last_verified_at"],
        "health_state": "observed",
        "data_origin": artifact["data_origin"],
    }
    _persist(ITEMS_DIR, artifact_id, inbox_item)
    return artifact


def _run_task(task_id: str, run_id: str, failure_mode: str = "") -> None:
    task = _load_json(TASKS_DIR / f"{task_id}.json") or {}
    conversation_id = task.get("conversation_id", "")
    _update_task(task_id, status="planning")
    _append_event(run_id, task_id, "task.planning", "planning", "Task accepted and prepared")
    _update_task(task_id, status="running")
    _update_run(run_id, status="running", started_at=_now())
    _append_event(run_id, task_id, "run.started", "running", "Hermes Session API request started", {"profile": task.get("profile", "default")})
    try:
        if failure_mode == "hermes-unreachable":
            _hermes_request("/api/__vertical_slice_test_failure__")
        else:
            _ensure_session(conversation_id)
            response = _hermes_request(
                f"/api/sessions/{quote(conversation_id)}/chat",
                {"message": task.get("prompt", "")},
                method="POST",
                session_id=conversation_id,
            )
        reply = (((response.get("message") or {}).get("content")) or "").strip()
        if not reply:
            raise RuntimeError("Hermes returned an empty response")
        _append_event(run_id, task_id, "hermes.response", "running", "Hermes response captured", {"response_received": True})
        artifact = _task_artifact(task_id, run_id, reply, conversation_id, task.get("title", "Hermes task result"))
        _append_event(run_id, task_id, "artifact.created", "running", "Artifact normalized and added to Inbox", {"artifact_id": artifact["id"]})
        _update_run(run_id, status="completed", completed_at=_now(), error=None, execution_metadata={"response_received": True})
        _update_task(task_id, status="completed", active_run_id=run_id, artifact_id=artifact["id"])
        _append_event(run_id, task_id, "run.completed", "completed", "Run completed successfully", {"artifact_id": artifact["id"]})
    except Exception as exc:
        safe_error = str(exc).replace(API_SERVER_KEY, "[REDACTED]")[:500]
        _update_run(run_id, status="failed", completed_at=_now(), error=safe_error, execution_metadata={"response_received": False})
        _update_task(task_id, status="failed", active_run_id=run_id, error=safe_error)
        _append_event(run_id, task_id, "run.failed", "failed", "Run failed", {"error": safe_error})


def _start_task(payload: dict, failure_mode: str = "", task_id: str | None = None) -> tuple[dict, dict]:
    task_id = task_id or _new_id("task")
    run_id = _new_id("run")
    conversation_id = f"{SESSION_PREFIX}_{_safe_user(payload.get('user', 'owner'))}"
    now = _now()
    task = {
        "id": task_id,
        "title": str(payload.get("title") or "AgentHost task")[:200],
        "prompt": str(payload.get("prompt") or "").strip()[:MAX_CHAT_CHARS],
        "status": "received",
        "created_at": now,
        "updated_at": now,
        "project_reference": payload.get("project_reference"),
        "conversation_id": conversation_id,
        "active_run_id": run_id,
        "profile": str(payload.get("profile") or "default")[:40],
    }
    run = {
        "id": run_id,
        "task_id": task_id,
        "external_run_id": None,
        "profile": task["profile"],
        "status": "received",
        "started_at": None,
        "completed_at": None,
        "error": None,
        "execution_metadata": {"transport": "Hermes Session API", "conversation_id": conversation_id},
    }
    _persist(TASKS_DIR, task_id, task)
    _persist(RUNS_DIR, run_id, run)
    _append_event(run_id, task_id, "task.received", "received", "Task received from UI")
    thread = threading.Thread(target=_run_task, args=(task_id, run_id, failure_mode), daemon=True)
    thread.start()
    return task, run


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
        if path in ("/api/tasks", "/api/tasks/"):
            tasks = []
            for task_path in sorted(TASKS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
                task = _load_json(task_path)
                if task:
                    tasks.append(task)
            self._send_json({"tasks": tasks[:MAX_ITEMS], "data_origin": "ui-workflow-storage"})
            return
        if path.startswith("/api/tasks/"):
            tail = path.removeprefix("/api/tasks/").strip("/")
            if tail.endswith("/retry"):
                self._send_json({"error": "method_not_allowed"}, 405)
                return
            task = _load_json(TASKS_DIR / f"{tail}.json")
            if task is None:
                self._send_json({"error": "not_found"}, 404)
                return
            run = _load_json(RUNS_DIR / f"{task.get('active_run_id', '')}.json") if task.get("active_run_id") else None
            self._send_json({"task": task, "run": run, "events": _read_events(task.get("active_run_id", ""))})
            return
        if path.startswith("/api/runs/") and path.endswith("/events"):
            run_id = path.removeprefix("/api/runs/").removesuffix("/events").strip("/")
            self._send_json({"run_id": run_id, "events": _read_events(run_id)})
            return
        if path.startswith("/api/runs/"):
            run_id = path.removeprefix("/api/runs/").strip("/")
            run = _load_json(RUNS_DIR / f"{run_id}.json")
            if run is None:
                self._send_json({"error": "not_found"}, 404)
                return
            self._send_json({"run": run, "events": _read_events(run_id)})
            return
        if path.startswith("/api/artifacts/"):
            artifact_id = Path(path.removeprefix("/api/artifacts/")).name
            artifact = _load_json(ARTIFACTS_DIR / f"{artifact_id}.json")
            if artifact is None:
                self._send_json({"error": "not_found"}, 404)
                return
            self._send_json(artifact)
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
        if path == "/api/tasks":
            payload = self._read_json()
            if payload is None:
                return
            prompt = str(payload.get("prompt") or "").strip()
            if not prompt:
                self._send_json({"error": "prompt_required"}, 400)
                return
            failure_mode = ""
            if self.headers.get("X-UI-Test-Failure") == "hermes-unreachable":
                failure_mode = "hermes-unreachable"
            task, run = _start_task(payload, failure_mode)
            self._send_json({"ok": True, "task": task, "run": run}, 202)
            return
        if path.startswith("/api/tasks/") and path.endswith("/retry"):
            task_id = path.removeprefix("/api/tasks/").removesuffix("/retry").strip("/")
            task = _load_json(TASKS_DIR / f"{task_id}.json")
            if task is None:
                self._send_json({"error": "not_found"}, 404)
                return
            payload = {"title": task.get("title"), "prompt": task.get("prompt"), "profile": task.get("profile"), "user": "owner"}
            retry_task, retry_run = _start_task(payload, task_id=task_id)
            retry_task["created_at"] = task.get("created_at", retry_task["created_at"])
            retry_task["project_reference"] = task.get("project_reference")
            _persist(TASKS_DIR, task_id, retry_task)
            self._send_json({"ok": True, "task": retry_task, "run": retry_run}, 202)
            return
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
