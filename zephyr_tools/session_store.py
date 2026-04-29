"""Session persistence for Zephyr Tools REPL — remain / resume support."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from uuid import uuid4

SESSIONS_DIR = Path.home() / ".zephyr_sessions"
MAX_SESSIONS = 10


@dataclass
class ZephyrSession:
    session_id: str
    created_at: float
    updated_at: float
    work_dir: str
    board: str
    project: str | None
    build_dir: str
    messages: list[dict]
    message_count: int = 0

    @classmethod
    def new(cls, work_dir: str, board: str = "nucleo_f411re") -> "ZephyrSession":
        now = time.time()
        return cls(
            session_id=uuid4().hex[:12],
            created_at=now,
            updated_at=now,
            work_dir=work_dir,
            board=board,
            project=None,
            build_dir="build",
            messages=[],
            message_count=0,
        )


def _path(session_id: str) -> Path:
    return SESSIONS_DIR / f"{session_id}.json"


def save_session(session: ZephyrSession) -> Path:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    session.updated_at = time.time()
    session.message_count = len(session.messages)
    path = _path(session.session_id)
    path.write_text(json.dumps(asdict(session), indent=2, ensure_ascii=False), encoding="utf-8")
    _cleanup_old()
    return path


def load_session(session_id: str) -> ZephyrSession | None:
    path = _path(session_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    return ZephyrSession(**data)


def list_sessions() -> list[dict]:
    if not SESSIONS_DIR.exists():
        return []
    sessions = []
    for path in sorted(SESSIONS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, dict) or "session_id" not in data:
            continue
        sessions.append({
            "id": data["session_id"],
            "created": data["created_at"],
            "updated": data["updated_at"],
            "work_dir": data["work_dir"],
            "board": data.get("board", "nucleo_f411re"),
            "project": data.get("project"),
            "messages": data.get("message_count", 0),
        })
    return sessions


def delete_session(session_id: str) -> bool:
    path = _path(session_id)
    if path.exists():
        path.unlink()
        return True
    return False


def _cleanup_old():
    sessions = sorted(SESSIONS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in sessions[MAX_SESSIONS:]:
        old.unlink()
