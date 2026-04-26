"""Structured data exchanged between core services and frontends."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class CommandResult:
    """Captured result from an external command."""

    args: list[str]
    returncode: int
    stdout: str = ""
    stderr: str = ""
    cwd: Path | None = None

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def output(self) -> str:
        return "\n".join(part for part in (self.stdout, self.stderr) if part).strip()


@dataclass(slots=True)
class DoctorCheck:
    """One environment check shown by doctor commands and UIs."""

    name: str
    ok: bool
    detail: str
    hint: str = ""


@dataclass(slots=True)
class BoardInfo:
    """Basic Zephyr board metadata."""

    name: str
    vendor: str | None = None
    arch: str | None = None
    soc: str | None = None
    source: str | None = None


@dataclass(slots=True)
class ProjectInfo:
    """Created or discovered Zephyr project."""

    name: str
    path: Path
    board: str
    files: list[Path] = field(default_factory=list)


@dataclass(slots=True)
class BuildResult:
    """Structured build outcome."""

    project_dir: Path
    build_dir: Path
    board: str
    command: CommandResult
    elf_path: Path | None = None
    hex_path: Path | None = None

    @property
    def ok(self) -> bool:
        return self.command.ok and self.elf_path is not None
