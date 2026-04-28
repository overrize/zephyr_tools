"""Command line interface for Zephyr Tools."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .client import ZephyrToolsClient
from .errors import ZephyrToolsError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="zt",
        description="Zephyr Tools - CLI/TUI/Desktop/Web shared Zephyr workflow",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-C", "--work-dir", type=Path, default=Path.cwd(), help="工作目录")
    parser.add_argument("-b", "--board", default="nucleo_f411re", help="默认 Zephyr board")

    sub = parser.add_subparsers(dest="cmd", required=True)

    p_doctor = sub.add_parser("doctor", help="检查 Zephyr 开发环境")
    p_doctor.set_defaults(func=_cmd_doctor)

    p_init = sub.add_parser("init", help="初始化 west workspace")
    p_init.add_argument("--manifest-url", help="west manifest 仓库 URL")
    p_init.add_argument("--manifest-rev", help="west manifest revision")
    p_init.add_argument("--update", action="store_true", help="初始化后运行 west update")
    p_init.set_defaults(func=_cmd_init)

    p_boards = sub.add_parser("boards", help="列出 Zephyr boards")
    p_boards.add_argument("filter", nargs="?", help="按名称过滤")
    p_boards.set_defaults(func=_cmd_boards)

    p_create = sub.add_parser("create", help="创建 Zephyr app")
    p_create.add_argument("name", help="项目名称")
    p_create.add_argument("-o", "--output", type=Path, help="输出目录")
    p_create.add_argument("--overwrite", action="store_true", help="允许覆盖已有目录")
    p_create.set_defaults(func=_cmd_create)

    p_build = sub.add_parser("build", help="执行 west build")
    p_build.add_argument("project", type=Path, help="项目目录")
    p_build.add_argument("-d", "--build-dir", type=Path, help="构建目录")
    p_build.add_argument("--pristine", action="store_true", help="强制 pristine build")
    p_build.set_defaults(func=_cmd_build)

    p_flash = sub.add_parser("flash", help="执行 west flash")
    p_flash.add_argument("-d", "--build-dir", type=Path, default=Path("build"), help="构建目录")
    p_flash.add_argument("--runner", help="Zephyr runner 名称")
    p_flash.set_defaults(func=_cmd_flash)

    p_monitor = sub.add_parser("monitor", help="连接 Zephyr 日志/调试会话")
    p_monitor.add_argument("-d", "--build-dir", type=Path, help="构建目录")
    p_monitor.set_defaults(func=_cmd_monitor)

    p_shell = sub.add_parser("shell", help="连接 Zephyr shell")
    p_shell.add_argument("-d", "--build-dir", type=Path, help="构建目录")
    p_shell.set_defaults(func=_cmd_monitor)

    p_gen = sub.add_parser("gen", help="根据自然语言生成 Zephyr app")
    p_gen.add_argument("prompt", help="需求描述")
    p_gen.add_argument("-o", "--output", type=Path, default=Path("generated"), help="输出目录")
    p_gen.add_argument("--build", action="store_true", help="生成后构建")
    p_gen.add_argument("--flash", action="store_true", help="构建后烧录")
    p_gen.set_defaults(func=_cmd_gen)

    p_fix = sub.add_parser("fix", help="根据构建错误修复 Zephyr app")
    p_fix.add_argument("project", type=Path, help="项目目录")
    p_fix.add_argument("prompt", help="原始需求")
    p_fix.add_argument("--error-file", type=Path, help="包含构建错误的文本文件")
    p_fix.set_defaults(func=_cmd_fix)

    p_repl = sub.add_parser("repl", help="启动交互式 REPL (类似 Claude Code 的对话式 CLI)")
    p_repl.set_defaults(func=_cmd_repl)

    p_tui = sub.add_parser("tui", help="启动 TUI (简单菜单界面)")
    p_tui.set_defaults(func=_cmd_tui)

    p_api = sub.add_parser("api", help="启动 Desktop/Web 共用的本地 API")
    p_api.add_argument("--host", default="127.0.0.1", help="监听地址")
    p_api.add_argument("--port", type=int, default=8765, help="监听端口")
    p_api.set_defaults(func=_cmd_api)

    args = parser.parse_args(argv)
    client = ZephyrToolsClient(work_dir=args.work_dir, default_board=args.board)
    try:
        return args.func(client, args)
    except ZephyrToolsError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1
    except FileExistsError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1


def _cmd_doctor(client: ZephyrToolsClient, args) -> int:
    checks = client.doctor()
    failed = False
    for check in checks:
        mark = "OK" if check.ok else "FAIL"
        print(f"[{mark}] {check.name}: {check.detail}")
        if check.hint:
            print(f"      提示: {check.hint}")
        failed = failed or not check.ok and check.name in {"west", "cmake", "ninja", "python"}
    return 1 if failed else 0


def _cmd_init(client: ZephyrToolsClient, args) -> int:
    results = client.init(args.manifest_url, args.manifest_rev, update=args.update)
    for result in results:
        print(result.output or f"执行完成: {' '.join(result.args)}")
        if not result.ok:
            return result.returncode or 1
    return 0


def _cmd_boards(client: ZephyrToolsClient, args) -> int:
    boards = client.list_boards(args.filter)
    for board in boards:
        print(board.name)
    if not boards:
        print("未发现 board。请确认已在 Zephyr workspace 中运行。")
    return 0


def _cmd_create(client: ZephyrToolsClient, args) -> int:
    project = client.create(args.name, output_dir=args.output, overwrite=args.overwrite)
    print(f"项目已创建: {project.path}")
    print(f"默认 board: {project.board}")
    return 0


def _cmd_build(client: ZephyrToolsClient, args) -> int:
    result = client.build(args.project, build_dir=args.build_dir, pristine=args.pristine)
    print(f"构建完成: {result.build_dir}")
    if result.elf_path:
        print(f"ELF: {result.elf_path}")
    return 0


def _cmd_flash(client: ZephyrToolsClient, args) -> int:
    client.flash(args.build_dir, runner_name=args.runner)
    print("烧录完成")
    return 0


def _cmd_monitor(client: ZephyrToolsClient, args) -> int:
    result = client.monitor(build_dir=args.build_dir)
    print(result.output)
    return 0


def _cmd_gen(client: ZephyrToolsClient, args) -> int:
    project = client.gen(args.prompt, args.output)
    print(f"工程已生成: {project.path}")
    if args.build:
        build = client.build(project.path)
        print(f"构建完成: {build.build_dir}")
        if args.flash:
            client.flash(build.build_dir)
            print("烧录完成")
    return 0


def _cmd_fix(client: ZephyrToolsClient, args) -> int:
    if args.error_file:
        build_error = args.error_file.read_text(encoding="utf-8")
    else:
        build_error = sys.stdin.read()
    project = client.fix(args.project, args.prompt, build_error)
    print(f"已修复项目: {project.path}")
    return 0


def _cmd_repl(client: ZephyrToolsClient, args) -> int:
    from .repl import run_repl

    return run_repl(work_dir=client.work_dir, default_board=client.default_board)


def _cmd_tui(client: ZephyrToolsClient, args) -> int:
    from .tui import run_tui

    return run_tui(client)


def _cmd_api(client: ZephyrToolsClient, args) -> int:
    from .api import run_api_server

    return run_api_server(
        work_dir=client.work_dir,
        host=args.host,
        port=args.port,
        default_board=client.default_board,
    )


if __name__ == "__main__":
    raise SystemExit(main())
