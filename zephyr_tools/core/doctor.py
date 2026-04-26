"""Environment diagnostics for Zephyr Tools."""

from pathlib import Path
import shutil

from .models import DoctorCheck
from .runner import CommandRunner


class DoctorService:
    """Check host tools required by a Zephyr workflow."""

    REQUIRED_TOOLS = {
        "west": "安装 west: pip install west",
        "cmake": "安装 CMake 并加入 PATH",
        "ninja": "安装 Ninja 并加入 PATH",
        "python": "安装 Python 3.10+ 并加入 PATH",
    }

    OPTIONAL_TOOLS = {
        "dtc": "Zephyr SDK 通常会提供 dtc",
        "openocd": "烧录/调试部分板卡时需要 OpenOCD",
        "pyocd": "部分 ARM 板卡可通过 pyOCD runner 烧录",
    }

    def __init__(self, work_dir: str | Path, runner: CommandRunner | None = None):
        self.work_dir = Path(work_dir).resolve()
        self.runner = runner or CommandRunner()

    def run(self) -> list[DoctorCheck]:
        checks: list[DoctorCheck] = []
        for tool, hint in self.REQUIRED_TOOLS.items():
            path = shutil.which(tool)
            checks.append(
                DoctorCheck(
                    name=tool,
                    ok=path is not None,
                    detail=path or "未找到",
                    hint="" if path else hint,
                )
            )

        for tool, hint in self.OPTIONAL_TOOLS.items():
            path = shutil.which(tool)
            checks.append(
                DoctorCheck(
                    name=tool,
                    ok=path is not None,
                    detail=path or "未找到",
                    hint="" if path else hint,
                )
            )

        checks.extend(self._west_checks())
        return checks

    def _west_checks(self) -> list[DoctorCheck]:
        if shutil.which("west") is None:
            return []

        version = self.runner.run(["west", "--version"], cwd=self.work_dir)
        workspace = self.runner.run(["west", "topdir"], cwd=self.work_dir)
        return [
            DoctorCheck(
                name="west-version",
                ok=version.ok,
                detail=(version.stdout or version.stderr).strip() or "无法获取版本",
                hint="" if version.ok else "确认 west 安装可执行",
            ),
            DoctorCheck(
                name="west-workspace",
                ok=workspace.ok,
                detail=(workspace.stdout or workspace.stderr).strip() or "当前目录不在 workspace 中",
                hint="" if workspace.ok else "运行 `zt init` 或进入已有 Zephyr workspace",
            ),
        ]
