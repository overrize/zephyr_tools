"""Create and inspect Zephyr application projects."""

from pathlib import Path
import shutil

from zephyr_tools import paths

from .models import ProjectInfo


class ProjectManager:
    """Manage Zephyr application directories."""

    def __init__(self, work_dir: str | Path):
        self.work_dir = Path(work_dir).resolve()

    def create(
        self,
        name: str,
        board: str,
        output_dir: str | Path | None = None,
        overwrite: bool = False,
    ) -> ProjectInfo:
        """Create a minimal Zephyr application from the bundled template."""

        base = Path(output_dir).resolve() if output_dir else self.work_dir / name
        if base.exists() and any(base.iterdir()) and not overwrite:
            raise FileExistsError(f"项目目录已存在且非空: {base}")
        base.mkdir(parents=True, exist_ok=True)

        template_dir = paths.get_zephyr_template_dir()
        if template_dir.exists():
            shutil.copytree(template_dir, base, dirs_exist_ok=True)
        else:
            self._write_fallback_template(base)

        self._replace_tokens(base, name=name, board=board)
        files = [p for p in base.rglob("*") if p.is_file()]
        return ProjectInfo(name=name, path=base, board=board, files=files)

    def discover(self, project_dir: str | Path, board: str | None = None) -> ProjectInfo:
        project_path = Path(project_dir).resolve()
        name = project_path.name
        board_name = board or self._read_default_board(project_path) or "unknown"
        files = [p for p in project_path.rglob("*") if p.is_file()]
        return ProjectInfo(name=name, path=project_path, board=board_name, files=files)

    def _replace_tokens(self, root: Path, name: str, board: str) -> None:
        replacements = {
            "{{PROJECT_NAME}}": name,
            "{{DEFAULT_BOARD}}": board,
        }
        for file_path in root.rglob("*"):
            if not file_path.is_file():
                continue
            text = file_path.read_text(encoding="utf-8")
            for old, new in replacements.items():
                text = text.replace(old, new)
            file_path.write_text(text, encoding="utf-8")

    def _read_default_board(self, project_dir: Path) -> str | None:
        marker = project_dir / ".zephyr-tools"
        if not marker.exists():
            return None
        for line in marker.read_text(encoding="utf-8").splitlines():
            if line.startswith("board="):
                return line.split("=", 1)[1].strip() or None
        return None

    def _write_fallback_template(self, root: Path) -> None:
        (root / "src").mkdir(parents=True, exist_ok=True)
        (root / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.20.0)\n"
            "find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})\n"
            "project({{PROJECT_NAME}})\n"
            "target_sources(app PRIVATE src/main.c)\n",
            encoding="utf-8",
        )
        (root / "prj.conf").write_text("CONFIG_GPIO=y\n", encoding="utf-8")
        (root / "src" / "main.c").write_text(
            '#include <zephyr/kernel.h>\n\nint main(void)\n{\n    return 0;\n}\n',
            encoding="utf-8",
        )
        (root / ".zephyr-tools").write_text(
            "name={{PROJECT_NAME}}\nboard={{DEFAULT_BOARD}}\n",
            encoding="utf-8",
        )
