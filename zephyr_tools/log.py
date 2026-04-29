"""Simple logging for Zephyr Tools."""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

_LOG_DIR = Path.home() / ".zephyr_sessions"
_LOG_FILE = _LOG_DIR / "debug.log"


def debug(msg: str):
    _log("DEBUG", msg)


def info(msg: str):
    _log("INFO", msg)


def error(msg: str):
    _log("ERROR", msg)


def _log(level: str, msg: str):
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%H:%M:%S.%f")[:12]
    line = f"[{ts}][{level}] {msg}"
    with open(_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def tail(lines: int = 50) -> str:
    if not _LOG_FILE.exists():
        return "(no logs)"
    text = _LOG_FILE.read_text(encoding="utf-8")
    parts = text.strip().split("\n")
    return "\n".join(parts[-lines:])
