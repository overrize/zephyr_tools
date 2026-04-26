"""Zephyr build service."""

from pathlib import Path

from zephyr_tools.errors import BuildError

from .models import BuildResult
from .runner import CommandRunner


class BuildService:
    """Run `west build` and return structured outputs."""

    def __init__(self, work_dir: str | Path, runner: CommandRunner | None = None):
        self.work_dir = Path(work_dir).resolve()
        self.runner = runner or CommandRunner()

    def build(
        self,
        project_dir: str | Path,
        board: str,
        build_dir: str | Path | None = None,
        pristine: bool = False,
        extra_args: list[str] | None = None,
    ) -> BuildResult:
        project_path = Path(project_dir).resolve()
        build_path = Path(build_dir).resolve() if build_dir else project_path / "build"

        cmd = ["west", "build", "-b", board, str(project_path), "-d", str(build_path)]
        if pristine:
            cmd.extend(["--pristine", "always"])
        if extra_args:
            cmd.extend(extra_args)

        command = self.runner.run(cmd, cwd=self.work_dir)
        elf = build_path / "zephyr" / "zephyr.elf"
        hex_file = build_path / "zephyr" / "zephyr.hex"
        result = BuildResult(
            project_dir=project_path,
            build_dir=build_path,
            board=board,
            command=command,
            elf_path=elf if elf.exists() else None,
            hex_path=hex_file if hex_file.exists() else None,
        )
        if not command.ok:
            raise BuildError(command.output or "west build 失败")
        return result
