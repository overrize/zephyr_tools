"""Zephyr Tools interactive REPL -- Claude Code-style conversational CLI."""

from __future__ import annotations

import re
import shlex
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from .client import ZephyrToolsClient
from .errors import ZephyrToolsError
from .llm.codegen import SYSTEM_PROMPT

HISTORY_FILE = Path.home() / ".zephyr_tools_history"

style = Style.from_dict({"prompt": "bold cyan"})
console = Console()


def _ok(text: str):
    console.print(f"[green]Y[/green] {text}")


def _fail(text: str):
    console.print(f"[red]X[/red] {text}")


def _info(text: str):
    console.print(f"[dim]{text}[/dim]")


ZEPHYR_COMMANDS: dict[str, tuple[str, str]] = {
    "doctor": ("Environment check", "Check Zephyr dev environment (west, cmake, ninja, python, probe)"),
    "init": ("Initialize workspace", "Init west workspace with --manifest-url URL --update"),
    "boards": ("List boards", "List Zephyr boards [filter]"),
    "board": ("Set default board", "board <name> -- set current target board"),
    "create": ("Create project", "create <name> [--board B] [--output DIR] -- create Zephyr app"),
    "select": ("Switch context", "select <path> -- set current project path"),
    "build": ("Build project", "build [--board B] [--pristine] [--build-dir DIR] -- build project"),
    "flash": ("Flash firmware", "flash [--runner R] [--build-dir DIR] -- flash to device"),
    "monitor": ("Monitor logs", "monitor [--build-dir DIR] -- connect serial/RTT log"),
    "gen": ("AI generate code", 'gen "<prompt>" [--board B] [--output DIR] -- LLM generate Zephyr app'),
    "fix": ("AI fix errors", 'fix <project> "<prompt>" --error-file FILE -- LLM fix build errors'),
    "ask": ("AI Q&A", 'ask "<question>" -- ask Zephyr questions to LLM'),
    "status": ("Show context", "Show session context (project, board, build dir)"),
    "clear": ("Clear screen", "Clear terminal screen"),
    "help": ("Help", "Show command list"),
    "quit": ("Quit", "Exit REPL"),
    "exit": ("Exit", "Exit REPL"),
}

NL_ROUTES: dict[str, str] = {
    "check": "doctor", "environment": "doctor", "env": "doctor", "diagnose": "doctor",
    "list": "boards", "search": "boards",
    "new": "create", "make": "create",
    "generate": "gen",
    "fix": "fix", "repair": "fix", "debug": "fix",
    "compile": "build", "make": "build",
    "burn": "flash", "write": "flash", "upload": "flash", "program": "flash", "deploy": "flash",
    "log": "monitor", "serial": "monitor", "console": "monitor",
    "help": "help", "what": "help", "commands": "help",
    "status": "status", "context": "status", "info": "status", "project": "status",
}


class ZephyrCompleter(Completer):
    def __init__(self, commands: dict[str, tuple[str, str]]):
        self.commands = commands

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.lstrip()
        if not text:
            for cmd in sorted(self.commands):
                yield Completion(cmd + " ", start_position=0, display=cmd, display_meta=self.commands[cmd][0])
            return
        parts = text.split()
        if len(parts) <= 1:
            word = parts[0].lower() if parts else ""
            for cmd in sorted(self.commands):
                if cmd.startswith(word):
                    yield Completion(cmd + " ", start_position=-len(word), display=cmd, display_meta=self.commands[cmd][0])
            return


def route_command(text: str) -> str | None:
    text_lower = text.strip().lower()
    if text_lower.split()[0] in ZEPHYR_COMMANDS:
        return text_lower.split()[0]
    tokens = set(re.findall(r"[a-zA-Z]+", text_lower))
    for token in tokens:
        if token in NL_ROUTES:
            return NL_ROUTES[token]
    return None


class ZephyrRepl:
    def __init__(self, work_dir: str | Path | None = None, default_board: str = "nucleo_f411re"):
        self.client = ZephyrToolsClient(work_dir=work_dir, default_board=default_board)
        self.session = PromptSession(
            history=FileHistory(str(HISTORY_FILE)),
            completer=ZephyrCompleter(ZEPHYR_COMMANDS),
            style=style,
            enable_history_search=True,
        )
        self.ctx_project: str | None = None
        self.ctx_board: str = default_board
        self.ctx_build_dir: str = "build"

    def run(self):
        self._banner()
        while True:
            try:
                text = self.session.prompt([("class:prompt", "zt> ")]).strip()
            except (EOFError, KeyboardInterrupt):
                console.print("\n[yellow]Bye.[/yellow]")
                break
            if not text:
                continue
            result = self._execute(text)
            if result == "quit":
                break

    def _execute(self, text: str) -> str | None:
        cmd_name = route_command(text)
        if cmd_name is None:
            _fail(f"Unknown command: {text[:60]}")
            _info("Type 'help' to see available commands.")
            return None
        try:
            handler = getattr(self, f"cmd_{cmd_name}", None)
            if handler is None:
                _fail(f"Command '{cmd_name}' not implemented")
                return None
            return handler(text)
        except ZephyrToolsError as e:
            _fail(str(e)[:300])
        except Exception as e:
            _fail(f"Error: {e}")
        return None

    def cmd_doctor(self, text: str) -> str | None:
        checks = self.client.doctor()
        t = Table(box=box.SIMPLE)
        t.add_column("Status", width=6)
        t.add_column("Check", width=14)
        t.add_column("Detail")
        t.add_column("Hint")
        for c in checks:
            status = "[green]OK[/green]" if c.ok else "[red]FAIL[/red]"
            t.add_row(status, c.name, c.detail, c.hint or "")
        console.print(Panel(t, title="[bold]Environment Check[/bold]", border_style="blue"))
        return None

    def cmd_init(self, text: str) -> str | None:
        args = shlex.split(text)[1:]
        manifest_url = None
        manifest_rev = None
        update = False
        i = 0
        while i < len(args):
            if args[i] == "--manifest-url" and i + 1 < len(args):
                manifest_url = args[i + 1]; i += 2
            elif args[i] == "--manifest-rev" and i + 1 < len(args):
                manifest_rev = args[i + 1]; i += 2
            elif args[i] == "--update":
                update = True; i += 1
            else:
                i += 1
        results = self.client.init(manifest_url, manifest_rev, update=update)
        for r in results:
            if r.ok:
                _ok(r.output or f"Ran: {' '.join(r.args)}")
            else:
                _fail(r.output or "init failed")
                return None
        _ok("Workspace initialized")
        return None

    def cmd_boards(self, text: str) -> str | None:
        parts = shlex.split(text)
        name_filter = parts[1] if len(parts) > 1 else None
        boards = self.client.list_boards(name_filter)
        if not boards:
            _fail("No boards found. Are you in a Zephyr workspace?")
            return None
        t = Table(box=box.SIMPLE)
        t.add_column("Board Name", style="cyan")
        t.add_column("Arch")
        t.add_column("Vendor")
        for b in boards:
            t.add_row(b.name, b.arch or "-", b.vendor or "-")
        console.print(Panel(t, title=f"Zephyr Boards ({len(boards)})", border_style="green"))
        return None

    def cmd_board(self, text: str) -> str | None:
        parts = shlex.split(text)
        if len(parts) < 2:
            _fail("Usage: board <name>")
            return None
        name = parts[1]
        self.ctx_board = name
        self.client.default_board = name
        _ok(f"Default board set to: {name}")
        return None

    def cmd_create(self, text: str) -> str | None:
        args = shlex.split(text)
        if len(args) < 2:
            _fail("Usage: create <name> [--board BOARD] [--output DIR]")
            return None
        name = args[1]
        board = self.ctx_board
        output_dir = None
        i = 2
        while i < len(args):
            if args[i] == "--board" and i + 1 < len(args):
                board = args[i + 1]; i += 2
            elif args[i] == "--output" and i + 1 < len(args):
                output_dir = Path(args[i + 1]); i += 2
            else:
                i += 1
        project = self.client.create(name, board=board, output_dir=output_dir)
        self.ctx_project = str(project.path)
        self.ctx_board = board
        _ok(f"Project [bold]{name}[/bold] created at [cyan]{project.path}[/cyan]")
        _info(f"Board: {board}")
        return None

    def cmd_select(self, text: str) -> str | None:
        parts = shlex.split(text)
        if len(parts) < 2:
            _fail("Usage: select <path>")
            return None
        path = Path(parts[1]).resolve()
        if not path.exists():
            _fail(f"Path does not exist: {path}")
            return None
        self.ctx_project = str(path)
        _ok(f"Context set to: {path}")
        return None

    def cmd_build(self, text: str) -> str | None:
        project = self.ctx_project
        if not project:
            _fail("No project in context. Use 'create <name>' or 'select <path>' first.")
            return None
        args = shlex.split(text)
        board = self.ctx_board
        pristine = False
        build_dir = self.ctx_build_dir
        i = 1
        while i < len(args):
            if args[i] == "--board" and i + 1 < len(args):
                board = args[i + 1]; i += 2
            elif args[i] == "--pristine":
                pristine = True; i += 1
            elif args[i] == "--build-dir" and i + 1 < len(args):
                build_dir = args[i + 1]; i += 2
            else:
                if not args[i].startswith("--"):
                    project = args[i]
                i += 1
        with console.status(f"[bold blue]Building {Path(project).name} for {board}...", spinner="dots"):
            result = self.client.build(project, board=board, build_dir=build_dir, pristine=pristine)
        self.ctx_build_dir = str(result.build_dir)
        _ok("Build complete")
        _info(f"Build dir: [cyan]{result.build_dir}[/cyan]")
        if result.elf_path:
            _info(f"ELF: [cyan]{result.elf_path}[/cyan]")
        return None

    def cmd_flash(self, text: str) -> str | None:
        args = shlex.split(text)
        runner = None
        build_dir = self.ctx_build_dir
        i = 1
        while i < len(args):
            if args[i] == "--runner" and i + 1 < len(args):
                runner = args[i + 1]; i += 2
            elif args[i] == "--build-dir" and i + 1 < len(args):
                build_dir = args[i + 1]; i += 2
            else:
                i += 1
        with console.status(f"[bold blue]Flashing {build_dir}...", spinner="dots"):
            self.client.flash(build_dir, runner_name=runner)
        _ok("Flash complete")
        return None

    def cmd_monitor(self, text: str) -> str | None:
        args = shlex.split(text)
        build_dir = self.ctx_build_dir
        i = 1
        while i < len(args):
            if args[i] == "--build-dir" and i + 1 < len(args):
                build_dir = args[i + 1]; i += 2
            else:
                i += 1
        _info("Connecting to monitor...")
        result = self.client.monitor(build_dir=build_dir)
        console.print(result.output)
        return None

    def cmd_gen(self, text: str) -> str | None:
        args = shlex.split(text)
        if len(args) < 2:
            _fail('Usage: gen "<prompt>" [--board BOARD] [--output DIR]')
            return None
        prompt_parts = []
        board = self.ctx_board
        output = "generated"
        i = 1
        while i < len(args):
            if args[i] == "--board" and i + 1 < len(args):
                board = args[i + 1]; i += 2
            elif args[i] == "--output" and i + 1 < len(args):
                output = args[i + 1]; i += 2
            else:
                prompt_parts.append(args[i]); i += 1
        prompt = " ".join(prompt_parts)
        with console.status(f"[bold blue]Generating: {prompt[:60]}...", spinner="dots"):
            project = self.client.gen(prompt, Path(output), board=board)
        self.ctx_project = str(project.path)
        _ok(f"Generated at [cyan]{project.path}[/cyan]")
        return None

    def cmd_fix(self, text: str) -> str | None:
        args = shlex.split(text)
        if len(args) < 3:
            _fail('Usage: fix <project> "<prompt>" --error-file FILE')
            return None
        project = args[1] if len(args) > 1 else self.ctx_project
        prompt_parts = []
        error_file = None
        i = 2
        while i < len(args):
            if args[i] == "--error-file" and i + 1 < len(args):
                error_file = args[i + 1]; i += 2
            else:
                prompt_parts.append(args[i]); i += 1
        prompt = " ".join(prompt_parts)
        if not error_file:
            _fail("--error-file is required")
            return None
        path = Path(error_file)
        build_error = path.read_text(encoding="utf-8") if path.exists() else error_file
        with console.status("[bold blue]Fixing...", spinner="dots"):
            result = self.client.fix(project, prompt, build_error, board=self.ctx_board)
        _ok(f"Fixed at [cyan]{result.path}[/cyan]")
        return None

    def cmd_ask(self, text: str) -> str | None:
        parts = shlex.split(text)
        if len(parts) < 2:
            _fail('Usage: ask "<question>"')
            return None
        question = " ".join(parts[1:])
        try:
            from openai import OpenAI
            cfg = self.client.codegen._resolve_config(None, None, None)
            client = OpenAI(api_key=cfg[0], base_url=cfg[1])
            with console.status("[bold blue]Thinking...", spinner="dots"):
                resp = client.chat.completions.create(
                    model=cfg[2],
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": question},
                    ],
                )
            console.print(Panel(resp.choices[0].message.content or "", title="Answer", border_style="green"))
        except Exception as e:
            _fail(str(e)[:200])
        return None

    def cmd_status(self, text: str) -> str | None:
        t = Table(box=box.SIMPLE, show_header=False)
        t.add_column("Key", style="bold", width=14)
        t.add_column("Value")
        t.add_row("Project", self.ctx_project or "(none)")
        t.add_row("Board", self.ctx_board)
        t.add_row("Build dir", self.ctx_build_dir)
        t.add_row("Work dir", str(self.client.work_dir))
        console.print(Panel(t, title="Session Context", border_style="blue"))
        return None

    def cmd_help(self, text: str) -> str | None:
        t = Table(box=box.SIMPLE)
        t.add_column("Command", style="cyan", width=10)
        t.add_column("Description")
        t.add_column("Usage")
        for cmd, (desc, usage) in sorted(ZEPHYR_COMMANDS.items()):
            if cmd in ("quit", "exit"):
                continue
            t.add_row(cmd, desc, usage)
        console.print(Panel(t, title="Zephyr Tools Commands", border_style="blue"))
        _info("\nTip: You can also use natural language like 'check environment' -> doctor, 'list boards' -> boards")
        return None

    def cmd_clear(self, text: str) -> str | None:
        console.clear()
        return None

    def cmd_quit(self, text: str) -> str | None:
        console.print("[yellow]Bye.[/yellow]")
        return "quit"

    def cmd_exit(self, text: str) -> str | None:
        return self.cmd_quit(text)

    def _banner(self):
        from . import __version__
        banner = Panel(
            Text.from_markup(
                f"[bold cyan]Zephyr Tools v{__version__}[/bold cyan]\n"
                "[dim]Interactive CLI for Zephyr RTOS embedded development[/dim]\n"
                "[dim]Type [bold]help[/bold] for commands  |  Ctrl+C or [bold]quit[/bold] to exit[/dim]"
            ),
            box=box.HEAVY,
            border_style="cyan",
        )
        console.print(banner)


def run_repl(work_dir: str | Path | None = None, default_board: str = "nucleo_f411re") -> int:
    repl = ZephyrRepl(work_dir=work_dir, default_board=default_board)
    repl.run()
    return 0
