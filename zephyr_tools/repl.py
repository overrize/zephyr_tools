"""Interactive REPL shell for Zephyr Tools — like a conversational CLI."""

from __future__ import annotations

import cmd
import shlex
import sys
from pathlib import Path

from .client import ZephyrToolsClient
from .errors import ZephyrToolsError
from .llm.codegen import SYSTEM_PROMPT

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.syntax import Syntax
    from rich.markdown import Markdown

    console = Console()
    RICH = True
except ImportError:
    console = None
    RICH = False


class ZephyrRepl(cmd.Cmd):
    prompt = "zt> "

    def __init__(self, work_dir: str | Path = None, default_board: str = "nucleo_f411re"):
        super().__init__()
        self.client = ZephyrToolsClient(work_dir=work_dir, default_board=default_board)
        self._ctx_project: str | None = None
        self._ctx_build_dir: str = "build"
        self._ctx_board: str = default_board
        self.intro = _make_intro()

    def _show(self, *args, **kwargs):
        if RICH:
            console.print(*args, **kwargs)
        else:
            print(*args)

    def _ok(self, text: str):
        if RICH:
            console.print(f"[green][OK][/green] {text}")
        else:
            print(f"[OK] {text}")

    def _fail(self, text: str):
        if RICH:
            console.print(f"[red][FAIL][/red] {text}")
        else:
            print(f"[FAIL] {text}")

    def _hint(self, text: str):
        if RICH:
            console.print(f"  [dim]hint: {text}[/dim]")
        else:
            print(f"  hint: {text}")

    def _require_project(self) -> str | None:
        if not self._ctx_project:
            self._fail("No project in context. Use 'create <name>' first.")
            return None
        return self._ctx_project

    def do_doctor(self, _arg):
        """doctor — check Zephyr environment"""
        failed = False
        for check in self.client.doctor():
            if check.ok:
                self._ok(f"{check.name}: {check.detail}")
            else:
                self._fail(f"{check.name}: {check.detail}")
            if check.hint:
                self._hint(check.hint)
            if not check.ok and check.name in {"west", "cmake", "ninja", "python"}:
                failed = True

    def do_init(self, arg):
        """init [--manifest-url URL] [--manifest-rev REV] [--update] — init west workspace"""
        args = shlex.split(arg)
        manifest_url = None
        manifest_rev = None
        update = False
        i = 0
        while i < len(args):
            if args[i] == "--manifest-url" and i + 1 < len(args):
                manifest_url = args[i + 1]
                i += 2
            elif args[i] == "--manifest-rev" and i + 1 < len(args):
                manifest_rev = args[i + 1]
                i += 2
            elif args[i] == "--update":
                update = True
                i += 1
            else:
                i += 1
        results = self.client.init(manifest_url, manifest_rev, update=update)
        for r in results:
            self._show(r.output or f"Ran: {' '.join(r.args)}")
            if not r.ok:
                self._fail("init failed")
                return
        self._ok("Workspace initialized")

    def do_boards(self, arg):
        """boards [filter] — list Zephyr boards"""
        name_filter = arg.strip() or None
        boards = self.client.list_boards(name_filter)
        if not boards:
            self._fail("No boards found. Are you in a Zephyr workspace?")
            return
        if RICH:
            t = Table(title="Zephyr Boards")
            t.add_column("Name", style="cyan")
            t.add_column("Arch")
            t.add_column("Vendor")
            for b in boards:
                t.add_row(b.name, b.arch or "-", b.vendor or "-")
            console.print(t)
        else:
            for b in boards:
                self._show(b.name)

    def do_create(self, arg):
        """create <name> [--board BOARD] [--output DIR] — create a Zephyr app"""
        args = shlex.split(arg)
        if not args:
            self._fail("Usage: create <name> [--board BOARD] [--output DIR]")
            return
        name = args[0]
        board = self._ctx_board
        output_dir = None
        i = 1
        while i < len(args):
            if args[i] == "--board" and i + 1 < len(args):
                board = args[i + 1]
                i += 2
            elif args[i] == "--output" and i + 1 < len(args):
                output_dir = Path(args[i + 1])
                i += 2
            else:
                i += 1
        project = self.client.create(name, board=board, output_dir=output_dir)
        self._ctx_project = str(project.path)
        self._ctx_board = board
        self._ok(f"Project '{name}' created at {project.path} (board: {board})")

    def do_select(self, arg):
        """select <project_path> — set current project context"""
        path = Path(arg.strip()).resolve()
        if not path.exists():
            self._fail(f"Path does not exist: {path}")
            return
        self._ctx_project = str(path)
        self._ok(f"Context set to: {path}")

    def do_board(self, arg):
        """board <name> — set default board"""
        name = arg.strip()
        if not name:
            self._fail("Usage: board <name>")
            return
        self._ctx_board = name
        self.client.default_board = name
        self._ok(f"Default board set to: {name}")

    def do_build(self, arg):
        """build [project_path] [--board BOARD] [--pristine] — west build"""
        project = self._require_project()
        if not project:
            return
        args = shlex.split(arg)
        board = self._ctx_board
        pristine = False
        build_dir = self._ctx_build_dir
        i = 0
        while i < len(args):
            if args[i] == "--board" and i + 1 < len(args):
                board = args[i + 1]
                i += 2
            elif args[i] == "--pristine":
                pristine = True
                i += 1
            elif args[i] == "--build-dir" and i + 1 < len(args):
                build_dir = args[i + 1]
                i += 2
            else:
                if not args[i].startswith("--"):
                    project = args[i]
                i += 1
        self._show(f"Building {project} for {board}...")
        result = self.client.build(project, board=board, build_dir=build_dir, pristine=pristine)
        self._ctx_build_dir = str(result.build_dir)
        self._ok(f"Build complete: {result.build_dir}")
        if result.elf_path:
            self._hint(f"ELF: {result.elf_path}")

    def do_flash(self, arg):
        """flash [--runner RUNNER] [--build-dir DIR] — west flash"""
        args = shlex.split(arg)
        runner = None
        build_dir = self._ctx_build_dir
        i = 0
        while i < len(args):
            if args[i] == "--runner" and i + 1 < len(args):
                runner = args[i + 1]
                i += 2
            elif args[i] == "--build-dir" and i + 1 < len(args):
                build_dir = args[i + 1]
                i += 2
            else:
                i += 1
        self._show(f"Flashing {build_dir}...")
        self.client.flash(build_dir, runner_name=runner)
        self._ok("Flash complete")

    def do_monitor(self, arg):
        """monitor [--build-dir DIR] — connect to Zephyr logs"""
        args = shlex.split(arg)
        build_dir = self._ctx_build_dir
        i = 0
        while i < len(args):
            if args[i] == "--build-dir" and i + 1 < len(args):
                build_dir = args[i + 1]
                i += 2
            else:
                i += 1
        result = self.client.monitor(build_dir=build_dir)
        self._show(result.output)

    def do_gen(self, arg):
        """gen "<prompt>" [--board BOARD] [--output DIR] — LLM generate Zephyr app code"""
        if not arg.strip():
            self._fail('Usage: gen "<prompt>" [--board BOARD] [--output DIR]')
            return
        args = shlex.split(arg)
        prompt_parts = []
        board = self._ctx_board
        output = "generated"
        i = 0
        while i < len(args):
            if args[i] == "--board" and i + 1 < len(args):
                board = args[i + 1]
                i += 2
            elif args[i] == "--output" and i + 1 < len(args):
                output = args[i + 1]
                i += 2
            else:
                prompt_parts.append(args[i])
                i += 1
        prompt = " ".join(prompt_parts)
        self._show(f"Generating: {prompt[:80]}...")
        project = self.client.gen(prompt, Path(output), board=board)
        self._ctx_project = str(project.path)
        self._ok(f"Generated: {project.path}")

    def do_fix(self, arg):
        """fix <project> "<prompt>" [--error-file FILE] — LLM fix build errors"""
        args = shlex.split(arg)
        if len(args) < 2:
            self._fail('Usage: fix <project> "<prompt>" [--error-file FILE]')
            return
        project = args[0]
        prompt_parts = []
        error_file = None
        i = 1
        while i < len(args):
            if args[i] == "--error-file" and i + 1 < len(args):
                error_file = args[i + 1]
                i += 2
            else:
                prompt_parts.append(args[i])
                i += 1
        prompt = " ".join(prompt_parts)
        if error_file:
            build_error = Path(error_file).read_text(encoding="utf-8")
        else:
            self._fail("--error-file required")
            return
        project = self.client.fix(project, prompt, build_error, board=self._ctx_board)
        self._ok(f"Fixed: {project.path}")

    def do_ask(self, arg):
        """ask "<question>" — ask LLM about Zephyr"""
        if not arg.strip():
            self._fail('Usage: ask "<question>"')
            return
        try:
            from openai import OpenAI

            cfg = self.client.codegen._resolve_config(None, None, None)
            client = OpenAI(api_key=cfg[0], base_url=cfg[1])
            resp = client.chat.completions.create(
                model=cfg[2],
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": arg.strip()},
                ],
            )
            self._show(resp.choices[0].message.content or "")
        except Exception as e:
            self._fail(str(e))

    def do_status(self, _arg):
        """status — show current context"""
        self._show(f"Project:  {self._ctx_project or '(none)'}")
        self._show(f"Board:    {self._ctx_board}")
        self._show(f"Build dir:{self._ctx_build_dir}")
        self._show(f"Work dir: {self.client.work_dir}")

    def do_help(self, _arg):
        """help — show available commands"""
        self._show(HELP_TEXT)

    def do_quit(self, _arg):
        """quit — exit REPL"""
        self._show("Bye.")
        return True

    def do_exit(self, _arg):
        return self.do_quit(_arg)

    def do_EOF(self, _arg):
        self._show("")
        return True

    def emptyline(self):
        pass

    def default(self, line):
        if line.lower() in ("q", "quit", "exit"):
            return self.do_quit(line)
        self._fail(f"Unknown command: {line}")
        self._hint("Type 'help' for available commands.")


HELP_TEXT = """
Available commands:

  doctor                  Check Zephyr development environment
  init [--manifest-url URL] [--update]
                          Initialize west workspace
  boards [filter]         List Zephyr boards
  board <name>            Set default board
  create <name> [--board B] [--output DIR]
                          Create a Zephyr application
  select <path>           Set current project context
  build [--board B] [--pristine] [--build-dir DIR]
                          Build current (or specified) project
  flash [--runner R] [--build-dir DIR]
                          Flash built binary to target
  monitor [--build-dir DIR]
                          Connect to serial/RTT log output
  gen "<prompt>" [--board B] [--output DIR]
                          Use LLM to generate Zephyr app code
  fix <project> "<prompt>" --error-file FILE
                          Use LLM to fix build errors
  ask "<question>"        Ask Zephyr-related question to LLM
  status                  Show current session context
  help                    Show this help
  quit / exit / Ctrl+D    Exit REPL

Context is remembered between commands — create once, build multiple times.
"""


def _make_intro() -> str:
    from . import __version__

    header = f"Zephyr Tools v{__version__}  |  type 'help' for commands  |  'quit' to exit"
    if RICH:
        return f"[bold cyan]{header}[/bold cyan]"
    return header


def run_repl(work_dir: str | Path | None = None, default_board: str = "nucleo_f411re") -> int:
    repl = ZephyrRepl(work_dir=work_dir, default_board=default_board)
    try:
        repl.cmdloop()
    except KeyboardInterrupt:
        repl._show("")
        return 0
    return 0
