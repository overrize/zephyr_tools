"""Board discovery through west."""

from pathlib import Path

from .models import BoardInfo
from .runner import CommandRunner


class BoardRegistry:
    """Expose Zephyr board names as structured records."""

    def __init__(self, work_dir: str | Path, runner: CommandRunner | None = None):
        self.work_dir = Path(work_dir).resolve()
        self.runner = runner or CommandRunner()

    def list(self, name_filter: str | None = None) -> list[BoardInfo]:
        result = self.runner.run(["west", "boards"], cwd=self.work_dir)
        if not result.ok:
            return []

        boards: list[BoardInfo] = []
        for raw in result.stdout.splitlines():
            name = raw.strip()
            if not name or name.startswith("-") or name.lower().startswith("board"):
                continue
            if name_filter and name_filter.lower() not in name.lower():
                continue
            boards.append(BoardInfo(name=name))
        return boards
