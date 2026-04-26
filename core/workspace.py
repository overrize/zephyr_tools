"""Zephyr workspace discovery and initialization."""

from pathlib import Path

from zephyr_tools.errors import ConfigurationError

from .models import CommandResult
from .runner import CommandRunner


class WorkspaceManager:
    """Manage a west workspace without leaking west details to frontends."""

    def __init__(self, work_dir: str | Path, runner: CommandRunner | None = None):
        self.work_dir = Path(work_dir).resolve()
        self.runner = runner or CommandRunner()

    def find_workspace_root(self, start: str | Path | None = None) -> Path | None:
        """Walk up from *start* until a west workspace marker is found."""

        current = Path(start or self.work_dir).resolve()
        candidates = [current, *current.parents]
        for path in candidates:
            if (path / ".west").exists() or (path / "west.yml").exists():
                return path
        return None

    def require_workspace(self, start: str | Path | None = None) -> Path:
        root = self.find_workspace_root(start)
        if root is None:
            raise ConfigurationError(
                "未找到 Zephyr west workspace。请先运行 `zt init`，或在已有 workspace 中执行命令。"
            )
        return root

    def init(
        self,
        manifest_url: str | None = None,
        manifest_rev: str | None = None,
        update: bool = False,
    ) -> list[CommandResult]:
        """Initialize a west workspace in the configured working directory."""

        self.work_dir.mkdir(parents=True, exist_ok=True)
        cmd = ["west", "init"]
        if manifest_url:
            cmd.extend(["-m", manifest_url])
        if manifest_rev:
            cmd.extend(["--mr", manifest_rev])
        cmd.append(str(self.work_dir))

        results = [self.runner.run(cmd)]
        if results[-1].ok and update:
            results.append(self.runner.run(["west", "update"], cwd=self.work_dir))
        return results
