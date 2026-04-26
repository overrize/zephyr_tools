"""Lightweight terminal UI for Zephyr Tools."""

from pathlib import Path

from .client import ZephyrToolsClient
from .errors import ZephyrToolsError


MENU = """
Zephyr Tools TUI
================
1. Doctor - 检查环境
2. Boards - 列出 boards
3. Create - 创建项目
4. Build - 构建项目
5. Flash - 烧录项目
6. Monitor - 连接日志/调试会话
q. 退出
"""


def run_tui(client: ZephyrToolsClient) -> int:
    """Run a simple interactive TUI loop."""

    while True:
        print(MENU)
        choice = _input("请选择: ").lower()
        if choice in {"q", "quit", "exit"}:
            return 0
        try:
            if choice == "1":
                _doctor(client)
            elif choice == "2":
                _boards(client)
            elif choice == "3":
                _create(client)
            elif choice == "4":
                _build(client)
            elif choice == "5":
                _flash(client)
            elif choice == "6":
                _monitor(client)
            else:
                print("未知选项")
        except ZephyrToolsError as exc:
            print(f"错误: {exc}")


def _doctor(client: ZephyrToolsClient) -> None:
    for check in client.doctor():
        mark = "OK" if check.ok else "FAIL"
        print(f"[{mark}] {check.name}: {check.detail}")
        if check.hint:
            print(f"      提示: {check.hint}")


def _boards(client: ZephyrToolsClient) -> None:
    name_filter = _input("过滤关键字（可空）: ") or None
    boards = client.list_boards(name_filter)
    if not boards:
        print("未发现 board")
        return
    for board in boards:
        print(board.name)


def _create(client: ZephyrToolsClient) -> None:
    name = _input("项目名称: ")
    board = _input(f"Board [{client.default_board}]: ") or client.default_board
    output = _input("输出目录（可空）: ")
    project = client.create(name, board=board, output_dir=Path(output) if output else None)
    print(f"项目已创建: {project.path}")


def _build(client: ZephyrToolsClient) -> None:
    project = Path(_input("项目目录: "))
    board = _input(f"Board [{client.default_board}]: ") or client.default_board
    result = client.build(project, board=board)
    print(f"构建完成: {result.build_dir}")


def _flash(client: ZephyrToolsClient) -> None:
    build_dir = Path(_input("构建目录 [build]: ") or "build")
    runner = _input("Runner（可空）: ") or None
    client.flash(build_dir, runner_name=runner)
    print("烧录完成")


def _monitor(client: ZephyrToolsClient) -> None:
    build_dir_raw = _input("构建目录（可空）: ")
    result = client.monitor(Path(build_dir_raw) if build_dir_raw else None)
    print(result.output)


def _input(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        return "q"
