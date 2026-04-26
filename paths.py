"""Path helpers shared by CLI, TUI, API, and core services."""

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent


def resolve_work_dir(work_dir: str | Path | None = None) -> Path:
    """Return an absolute working directory."""

    return Path(work_dir or Path.cwd()).resolve()


def get_projects_dir(work_dir: str | Path | None = None) -> Path:
    """Return the default project root for generated Zephyr applications."""

    return resolve_work_dir(work_dir)


def get_templates_dir() -> Path:
    """Return the repository-level template directory."""

    return REPO_ROOT / "templates"


def get_zephyr_template_dir() -> Path:
    """Return the default Zephyr application template directory."""

    return get_templates_dir() / "zephyr_app"
