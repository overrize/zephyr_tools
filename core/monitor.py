"""Serial, RTT, and shell monitoring hooks."""

from pathlib import Path

from zephyr_tools.errors import HardwareError

from .models import CommandResult
from .runner import CommandRunner


class MonitorService:
    """Start monitor commands through west or an explicit host command."""

    def __init__(self, work_dir: str | Path, runner: CommandRunner | None = None):
        self.work_dir = Path(work_dir).resolve()
        self.runner = runner or CommandRunner()

    def monitor(
        self,
        build_dir: str | Path | None = None,
        command: list[str] | None = None,
    ) -> CommandResult:
        """Run a monitor command once and capture its output.

        Long-lived interactive monitors should use the same command generated here
        from a frontend process that can stream output.
        """

        if command:
            cmd = command
        else:
            cmd = ["west", "attach"]
            if build_dir:
                cmd.extend(["-d", str(Path(build_dir).resolve())])

        result = self.runner.run(cmd, cwd=self.work_dir)
        if not result.ok:
            raise HardwareError(result.output or "监控命令失败")
        return result
