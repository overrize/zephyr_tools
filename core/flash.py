"""Zephyr flashing service."""

from pathlib import Path

from zephyr_tools.errors import HardwareError

from .models import CommandResult
from .runner import CommandRunner


class FlashService:
    """Run `west flash` for a built Zephyr project."""

    def __init__(self, work_dir: str | Path, runner: CommandRunner | None = None):
        self.work_dir = Path(work_dir).resolve()
        self.runner = runner or CommandRunner()

    def flash(
        self,
        build_dir: str | Path,
        runner_name: str | None = None,
        extra_args: list[str] | None = None,
    ) -> CommandResult:
        cmd = ["west", "flash", "-d", str(Path(build_dir).resolve())]
        if runner_name:
            cmd.extend(["--runner", runner_name])
        if extra_args:
            cmd.extend(extra_args)

        result = self.runner.run(cmd, cwd=self.work_dir)
        if not result.ok:
            raise HardwareError(result.output or "west flash 失败")
        return result
