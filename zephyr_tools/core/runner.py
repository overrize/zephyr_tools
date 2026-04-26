"""Small wrapper around subprocess for west and host tools."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Mapping, Sequence

from .models import CommandResult


class CommandRunner:
    """Run external commands with captured output."""

    def run(
        self,
        args: Sequence[str],
        cwd: str | Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout: int | None = None,
    ) -> CommandResult:
        merged_env = dict(os.environ)
        if env:
            merged_env.update(env)

        cwd_path = Path(cwd).resolve() if cwd is not None else None
        try:
            completed = subprocess.run(
                list(args),
                cwd=cwd_path,
                env=merged_env,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except FileNotFoundError as exc:
            return CommandResult(
                args=list(args),
                returncode=127,
                stderr=f"命令未找到: {args[0]} ({exc})",
                cwd=cwd_path,
            )
        except subprocess.TimeoutExpired as exc:
            return CommandResult(
                args=list(args),
                returncode=124,
                stdout=exc.stdout or "",
                stderr=exc.stderr or f"命令超时: {' '.join(args)}",
                cwd=cwd_path,
            )

        return CommandResult(
            args=list(args),
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            cwd=cwd_path,
        )
