"""Programmable facade shared by CLI, TUI, Desktop, and Web API."""

from pathlib import Path

from .core import (
    BoardRegistry,
    BuildResult,
    BuildService,
    CommandResult,
    DoctorCheck,
    DoctorService,
    FlashService,
    MonitorService,
    ProjectInfo,
    ProjectManager,
    WorkspaceManager,
)
from .llm import CodegenService


class ZephyrToolsClient:
    """High-level Zephyr workflow API."""

    def __init__(self, work_dir: str | Path | None = None, default_board: str = "nucleo_f411re"):
        self.work_dir = Path(work_dir or Path.cwd()).resolve()
        self.default_board = default_board
        self.workspace = WorkspaceManager(self.work_dir)
        self.projects = ProjectManager(self.work_dir)
        self.boards = BoardRegistry(self.work_dir)
        self.builder = BuildService(self.work_dir)
        self.flasher = FlashService(self.work_dir)
        self.monitor_service = MonitorService(self.work_dir)
        self.doctor_service = DoctorService(self.work_dir)
        self.codegen = CodegenService(self.work_dir)

    def doctor(self) -> list[DoctorCheck]:
        return self.doctor_service.run()

    def init(
        self,
        manifest_url: str | None = None,
        manifest_rev: str | None = None,
        update: bool = False,
    ) -> list[CommandResult]:
        return self.workspace.init(manifest_url=manifest_url, manifest_rev=manifest_rev, update=update)

    def list_boards(self, name_filter: str | None = None):
        return self.boards.list(name_filter=name_filter)

    def create(
        self,
        name: str,
        board: str | None = None,
        output_dir: str | Path | None = None,
        overwrite: bool = False,
    ) -> ProjectInfo:
        return self.projects.create(
            name=name,
            board=board or self.default_board,
            output_dir=output_dir,
            overwrite=overwrite,
        )

    def build(
        self,
        project_dir: str | Path,
        board: str | None = None,
        build_dir: str | Path | None = None,
        pristine: bool = False,
    ) -> BuildResult:
        return self.builder.build(
            project_dir=project_dir,
            board=board or self.default_board,
            build_dir=build_dir,
            pristine=pristine,
        )

    def flash(
        self,
        build_dir: str | Path,
        runner_name: str | None = None,
    ) -> CommandResult:
        return self.flasher.flash(build_dir=build_dir, runner_name=runner_name)

    def monitor(self, build_dir: str | Path | None = None) -> CommandResult:
        return self.monitor_service.monitor(build_dir=build_dir)

    def gen(
        self,
        prompt: str,
        output_dir: str | Path,
        board: str | None = None,
        overwrite: bool = True,
    ) -> ProjectInfo:
        board_name = board or self.default_board
        project = self.create(Path(output_dir).name, board_name, output_dir=output_dir, overwrite=overwrite)
        generated = self.codegen.generate(prompt)
        self._write_generated(project.path, board_name, generated.main_c, generated.prj_conf, generated.overlay)
        return project

    def fix(
        self,
        project_dir: str | Path,
        prompt: str,
        build_error: str,
        board: str | None = None,
    ) -> ProjectInfo:
        project_path = Path(project_dir).resolve()
        main_c = self._read_text(project_path / "src" / "main.c")
        prj_conf = self._read_text(project_path / "prj.conf")
        overlay_path = project_path / "boards" / f"{board or self.default_board}.overlay"
        overlay = self._read_text(overlay_path)
        generated = self.codegen.fix(prompt, main_c, prj_conf, overlay, build_error)
        self._write_generated(
            project_path,
            board or self.default_board,
            generated.main_c,
            generated.prj_conf,
            generated.overlay,
        )
        return self.projects.discover(project_path, board=board or self.default_board)

    def _write_generated(
        self,
        project_path: Path,
        board: str,
        main_c: str,
        prj_conf: str,
        overlay: str,
    ) -> None:
        (project_path / "src").mkdir(parents=True, exist_ok=True)
        (project_path / "src" / "main.c").write_text(main_c, encoding="utf-8")
        if prj_conf:
            (project_path / "prj.conf").write_text(prj_conf, encoding="utf-8")
        if overlay:
            overlay_dir = project_path / "boards"
            overlay_dir.mkdir(parents=True, exist_ok=True)
            (overlay_dir / f"{board}.overlay").write_text(overlay, encoding="utf-8")

    def _read_text(self, path: Path) -> str:
        return path.read_text(encoding="utf-8") if path.exists() else ""
