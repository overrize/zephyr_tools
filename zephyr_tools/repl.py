"""Zephyr Tools conversational REPL -- Claude Code style agent loop."""

from __future__ import annotations

import itertools
import json
import os
import random
import subprocess
import sys
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich import box

from .client import ZephyrToolsClient
from .errors import ZephyrToolsError
from .llm.config import get_llm_config
from . import session_store
from . import workspace
from .skills import load_skills

console = Console()

_NO_COLOR = os.environ.get("NO_COLOR", "").strip()
if _NO_COLOR:
    console = Console(no_color=True)

try:
    from openai import OpenAI, APIError
except ImportError:
    OpenAI = None
    APIError = Exception

_TIPS = [
    "Tip: Say 'check my environment' to run doctor",
    "Tip: 'create blink --board nucleo_f411re' to start a project",
    "Tip: Context is remembered -- 'create' once, then just 'build'",
    "Tip: Type /new to start a fresh conversation",
    "Tip: 'status' shows your current project and board",
    "Tip: Use 'fix' with --error-file to auto-repair build errors",
]


SYSTEM_PROMPT = """You are a professional embedded development engineer for Zephyr RTOS. You autonomously handle everything from environment setup to building, flashing, debugging, and code generation.

You have tools for environment checks, board listing, project creation, building, flashing, monitoring, file editing, and running shell commands.

RULES:
1. You are a PROFESSIONAL engineer. Never ask the user to do things manually. Automatically fix issues yourself using your tools.
2. Always run doctor first if unsure about toolchain state. If something is missing (like west), install it automatically with run_command.
3. Use create_project to scaffold Zephyr apps. Default board: nucleo_f411re.
4. Use the current project context for builds unless the user specifies otherwise.
5. Explain what you are doing briefly, then DO IT. Don't just tell the user what to do.
6. Keep responses concise and action-oriented.
7. Context is maintained between turns (project, board, build dir)."""

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "doctor",
            "description": "Check Zephyr development environment (west, cmake, ninja, python, probe tools)",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_boards",
            "description": "List available Zephyr boards, optionally filtered by name",
            "parameters": {
                "type": "object",
                "properties": {
                    "filter": {"type": "string", "description": "Optional filter text to search board names"}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_board",
            "description": "Set the default target board for future operations",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Board name (e.g. nucleo_f411re)"}
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_project",
            "description": "Create a new Zephyr application project. After creation, the user can /fork to open a dedicated REPL for this project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Project name"},
                    "board": {"type": "string", "description": "Target board (default: current default)"},
                    "output_dir": {"type": "string", "description": "Output directory path (optional)"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "build_project",
            "description": "Build a Zephyr project using west build",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_dir": {"type": "string", "description": "Project directory (default: current context)"},
                    "board": {"type": "string", "description": "Board (default: current default)"},
                    "pristine": {"type": "boolean", "description": "Force clean build"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "flash_firmware",
            "description": "Flash built firmware to the target device",
            "parameters": {
                "type": "object",
                "properties": {
                    "build_dir": {"type": "string", "description": "Build directory (default: current build dir)"},
                    "runner": {"type": "string", "description": "Zephyr runner name (optional)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "monitor_logs",
            "description": "Connect to device serial/RTT log output",
            "parameters": {
                "type": "object",
                "properties": {
                    "build_dir": {"type": "string", "description": "Build directory (optional)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "show_context",
            "description": "Show current session context: project path, board, build directory",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read contents of a project file (main.c, prj.conf, overlay, CMakeLists.txt, etc.)",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path (relative or absolute)"}
                },
                "required": ["path"],
            },
        },
    },
        {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "Write content to a project file",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path (relative or absolute)"},
                        "content": {"type": "string", "description": "File content to write"},
                    },
                    "required": ["path", "content"],
                },
            },
        },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Run a shell command (e.g. pip install, git clone, west update). Use this to automatically fix environment issues.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute, e.g. 'pip install west'"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds (default 120)"},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "renode_run",
            "description": "Run a Zephyr binary in Renode simulator (no real hardware needed). Use this when the user wants to test without hardware.",
            "parameters": {
                "type": "object",
                "properties": {
                    "elf_path": {"type": "string", "description": "Path to the .elf binary to simulate"},
                    "machine": {"type": "string", "description": "Renode machine/platform name (default: 'nucleo_f411re')"},
                    "timeout": {"type": "integer", "description": "Simulation timeout in seconds (default: 10)"},
                },
                "required": ["elf_path"],
            },
        },
    },
]


class ZephyrRepl:
    def __init__(self, work_dir: str | Path | None = None, default_board: str = "nucleo_f411re", resume_session_id: str | None = None):
        self.client = ZephyrToolsClient(work_dir=work_dir, default_board=default_board)
        self.messages: list[dict] = []
        self.ctx_project: str | None = None
        self.ctx_board: str = default_board
        self.ctx_build_dir: str = "build"
        self._session: session_store.ZephyrSession | None = None
        self._resume_id = resume_session_id
        self.psession = PromptSession(
            history=FileHistory(str(Path.home() / ".zephyr_history")),
            mouse_support=True,
            enable_history_search=True,
        )

    def _prompt(self) -> str:
        ctx = ""
        if self.ctx_project:
            ctx = Path(self.ctx_project).name
        elif self.ctx_board:
            ctx = self.ctx_board
        if ctx:
            return f"zt [dim]{ctx}[/dim]> " if not _NO_COLOR else f"zt [{ctx}]> "
        return "zt> "

    def run(self):
        ws_path = workspace.prompt_workspace()
        if str(ws_path) != str(self.client.work_dir):
            self.client = ZephyrToolsClient(work_dir=ws_path, default_board=self.ctx_board)
        self._try_resume_or_new()
        api_key, base_url, model = self._resolve_api()
        if not api_key:
            return
        if OpenAI is None:
            console.print("[red]openai package not installed. Run: pip install openai[/red]")
            return
        self.llm = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.messages.append({"role": "system", "content": SYSTEM_PROMPT})
        ws_desc = workspace.describe_workspace(ws_path)
        context_blocks = [ws_desc, f"Default board: {self.ctx_board}"]
        loaded = load_skills(ws_path)
        if loaded:
            skill_summary = "Available skills:\n" + "\n".join(
                f"- {s['name']}" for s in loaded
            )
            context_blocks.append(skill_summary)
        self.messages.append({"role": "system", "content": "\n".join(context_blocks)})
        try:
            while True:
                try:
                    if _NO_COLOR:
                        prompt_str = "zt" + (f" [{Path(self.ctx_project).name}]" if self.ctx_project else "")
                        prompt_str += "> "
                    else:
                        cp = ""
                        if self.ctx_project:
                            cp = Path(self.ctx_project).name
                        elif self.ctx_board:
                            cp = self.ctx_board
                        prompt_str = f"\nzt [{cp}]> " if cp else "\nzt> "
                    text = self.psession.prompt(prompt_str).strip()
                except (EOFError, KeyboardInterrupt):
                    self._save_and_exit()
                    break
                if not text:
                    continue
                if text.lower() in ("quit", "exit"):
                    self._save_and_exit()
                    break
                if text.lower() == "clear":
                    console.clear()
                    continue
                if text.lower() == "/resume":
                    self._list_and_resume()
                    continue
                if text.lower() == "/sessions":
                    self._list_sessions()
                    continue
                if text.lower() == "/new":
                    self._start_new_session()
                    continue
                if text.lower() == "status":
                    self._show_context_full()
                    continue
                if text.lower().startswith("/fork"):
                    parts = text.split(maxsplit=1)
                    target = parts[1] if len(parts) > 1 else (self.ctx_project or "")
                    self._fork_session(target)
                    continue
                if text.lower() == "/help":
                    self._show_slash_help()
                    continue
                self.messages.append({"role": "user", "content": text})
                self._process_turn()
                self._auto_save()
        except Exception as e:
            console.print(f"\n[red]Fatal: {e}[/red]")
            self._auto_save()

    def _resolve_api(self) -> tuple[str | None, str | None, str]:
        api_key, base_url, model = get_llm_config(self.client.work_dir)
        if api_key:
            return api_key, base_url, model
        console.print(Panel(
            "[yellow]No API key found.[/yellow]\n\n"
            "The conversational REPL needs an OpenAI-compatible API key.\n\n"
            "Options:\n"
            "1. Set OPENAI_API_KEY in your environment\n"
            "2. Create a .env file:\n"
            "   OPENAI_API_KEY=sk-...\n"
            "   OPENAI_API_BASE=https://api.openai.com/v1\n"
            "   OPENAI_MODEL=gpt-4o-mini\n\n"
            "3. Enter one now:",
            title="LLM Configuration",
            border_style="yellow",
        ))
        try:
            key = input("API key (Enter to skip): ").strip()
            if not key:
                console.print("[yellow]Skipped. Use CLI mode instead.[/yellow]")
                return None, None, ""
            base = input("Base URL [https://api.openai.com/v1]: ").strip() or "https://api.openai.com/v1"
            mdl = input("Model [gpt-4o-mini]: ").strip() or "gpt-4o-mini"
            env_path = self.client.work_dir / ".env"
            with open(env_path, "w") as f:
                f.write(f"OPENAI_API_KEY={key}\nOPENAI_API_BASE={base}\nOPENAI_MODEL={mdl}\n")
            console.print(f"[green]Saved to {env_path}[/green]")
            return key, base, mdl
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]Skipped.[/yellow]")
            return None, None, ""

    def _process_turn(self):
        try:
            stream = self.llm.chat.completions.create(
                model=self.model,
                messages=self.messages,
                tools=TOOL_DEFINITIONS,
                tool_choice="auto",
                stream=True,
            )
        except APIError as e:
            console.print(f"[red]API error: {e}[/red]")
            self.messages.pop()
            return

        content_buffer = ""
        reasoning_buffer = ""
        tool_calls: dict[int, dict] = {}
        finish_reason = None
        _known_tool_names: set[str] = set()
        _anim = itertools.cycle(["[dim]|[/dim]", "[dim]/[/dim]", "[dim]-[/dim]", "[dim]\\[/dim]"])

        def _status(txt: str):
            sys.stdout.write(f"\r{next(_anim)} {txt}\r")
            sys.stdout.flush()

        _status("Thinking...")

        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            finish = chunk.choices[0].finish_reason
            if finish:
                finish_reason = finish
            if delta is None:
                continue
            if delta.content:
                content_buffer += delta.content
            rc = getattr(delta, "reasoning_content", None)
            if rc is None:
                rc = delta.model_extra.get("reasoning_content") if hasattr(delta, "model_extra") and delta.model_extra else None
            if rc:
                reasoning_buffer += rc
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls:
                        tool_calls[idx] = {"id": "", "function": {"name": "", "arguments": ""}}
                    if tc.id:
                        tool_calls[idx]["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            tool_calls[idx]["function"]["name"] += tc.function.name
                        if tc.function.arguments:
                            tool_calls[idx]["function"]["arguments"] += tc.function.arguments
                current_names = set()
                for tc in tool_calls.values():
                    if tc["function"]["name"]:
                        current_names.add(tc["function"]["name"])
                if current_names != _known_tool_names:
                    _known_tool_names = current_names
                    _status(f"Calling: {', '.join(sorted(current_names))}")

        if tool_calls:
            sys.stdout.write(f"\r{' ' * 60}\r")
            sys.stdout.flush()

        if content_buffer:
            msg: dict = {"role": "assistant", "content": content_buffer}
            if reasoning_buffer:
                msg["reasoning_content"] = reasoning_buffer
            self.messages.append(msg)
            if finish_reason != "tool_calls":
                console.print(content_buffer)

        if finish_reason == "tool_calls" and tool_calls:
            for tc in tool_calls.values():
                tc["function"]["arguments"] = _clean_json(tc["function"]["arguments"])
            assistant_msg: dict = {
                "role": "assistant",
                "content": content_buffer or None,
                "tool_calls": [
                    {"id": tc["id"], "type": "function", "function": tc["function"]}
                    for tc in tool_calls.values()
                ],
            }
            if reasoning_buffer:
                assistant_msg["reasoning_content"] = reasoning_buffer
            self.messages.append(assistant_msg)
            for tc in tool_calls.values():
                name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    args = {}
                arg_str = " ".join(f"{k}={v}" for k, v in args.items()) if args else ""
                label = f"[dim]▸ {name}[/dim]" + (f" [cyan]{arg_str}[/cyan]" if arg_str else "")
                console.print(label)
                result = self._exec_tool(name, args)
                for line in result.split("\n")[:6]:
                    if line.startswith("[OK]"):
                        console.print(f"  [green]{line}[/green]")
                    elif line.startswith("[FAIL]") or "ERROR" in line:
                        console.print(f"  [red]{line}[/red]")
                    elif line.strip():
                        console.print(f"  [dim]{line}[/dim]")
                if len(result.split("\n")) > 6:
                    console.print(f"  [dim]... ({len(result.split(chr(10))) - 6} more lines)[/dim]")
                self.messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})
            self._process_turn()

    def _exec_tool(self, name: str, args: dict) -> str:
        handler = getattr(self, f"_tool_{name}", None)
        if handler is None:
            return f"ERROR: unknown tool '{name}'"
        try:
            return handler(**args)
        except ZephyrToolsError as e:
            return f"ERROR: {e}"
        except FileNotFoundError as e:
            return f"ERROR: file not found: {e}"
        except TypeError as e:
            return f"ERROR: invalid arguments for {name}: {e}"
        except Exception as e:
            return f"ERROR: {e}"

    def _tool_doctor(self) -> str:
        results = self.client.doctor()
        return "\n".join(
            f"[{'OK' if c.ok else 'FAIL'}] {c.name}: {c.detail}"
            + (f"  hint: {c.hint}" if c.hint else "")
            for c in results
        )

    def _tool_list_boards(self, filter: str | None = None) -> str:
        boards = self.client.list_boards(filter or None)
        if not boards:
            return "No boards found." if not filter else f"No boards match filter '{filter}'"
        lines = [f"Found {len(boards)} board(s):"]
        for b in boards:
            lines.append(f"  {b.name}  arch={b.arch or '-'}  vendor={b.vendor or '-'}")
        return "\n".join(lines)

    def _tool_set_board(self, name: str) -> str:
        self.ctx_board = name
        self.client.default_board = name
        return f"Board set to {name}"

    def _tool_create_project(self, name: str, board: str | None = None, output_dir: str | None = None) -> str:
        board = board or self.ctx_board
        out = Path(output_dir) if output_dir else None
        project = self.client.create(name, board=board, output_dir=out)
        self.ctx_project = str(project.path)
        self.ctx_board = board
        return f"Project created at {project.path} (board: {board})"

    def _tool_build_project(self, project_dir: str | None = None, board: str | None = None, pristine: bool = False) -> str:
        project = project_dir or self.ctx_project
        if not project:
            return "ERROR: no project selected"
        board = board or self.ctx_board
        result = self.client.build(project, board=board, pristine=pristine)
        self.ctx_build_dir = str(result.build_dir)
        lines = [f"Build complete: {result.build_dir}"]
        if result.elf_path:
            lines.append(f"ELF: {result.elf_path}")
        return "\n".join(lines)

    def _tool_flash_firmware(self, build_dir: str | None = None, runner: str | None = None) -> str:
        bd = build_dir or self.ctx_build_dir
        self.client.flash(bd, runner_name=runner)
        return "Flash complete"

    def _tool_monitor_logs(self, build_dir: str | None = None) -> str:
        bd = build_dir or self.ctx_build_dir
        result = self.client.monitor(build_dir=bd)
        return result.output or "[connected]"

    def _tool_show_context(self) -> str:
        return (
            f"Project:  {self.ctx_project or '(none)'}\n"
            f"Board:    {self.ctx_board}\n"
            f"Build dir:{self.ctx_build_dir}\n"
            f"Work dir: {self.client.work_dir}"
        )

    def _tool_read_file(self, path: str) -> str:
        p = Path(path)
        if not p.is_absolute():
            p = (self.client.work_dir / p).resolve()
        if not p.exists():
            return f"ERROR: file not found: {p}"
        return p.read_text(encoding="utf-8")

    def _tool_write_file(self, path: str, content: str) -> str:
        p = Path(path)
        if not p.is_absolute():
            p = (self.client.work_dir / p).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Written {len(content)} bytes to {p}"

    def _tool_run_command(self, command: str, timeout: int = 120) -> str:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout.strip()
        if result.stderr:
            output += "\n" + result.stderr.strip()
        output = output or "(no output)"
        if result.returncode != 0:
            output = f"[FAIL] EXIT CODE: {result.returncode}\n{output}"
        return output[:2000]

    def _tool_renode_run(self, elf_path: str, machine: str = "nucleo_f411re", timeout: int = 10) -> str:
        import tempfile
        p = Path(elf_path)
        if not p.exists():
            return f"[FAIL] Binary not found: {elf_path}"
        resc = f"""
bin @{p.resolve()}
machine LoadPlatformDescription @platforms/boards/{machine}.repl
showAnalyzer uart0
sysbus LoadELF @{p.resolve()}
start
"""
        resc_file = Path(tempfile.mktemp(suffix=".resc"))
        resc_file.write_text(resc.strip())
        try:
            result = subprocess.run(
                f"renode --console --disable-xwt -e \"{resc_file.resolve()}\"",
                shell=True, capture_output=True, text=True, timeout=timeout,
            )
            output = result.stdout.strip() or result.stderr.strip() or "(no output)"
            return f"Renode simulation completed:\n{output[:1500]}"
        except subprocess.TimeoutExpired:
            return f"[OK] Renode simulation started (timeout after {timeout}s). Check Renode window for output."
        except FileNotFoundError:
            return "[FAIL] Renode not found. Install from https://renode.io"
        finally:
            resc_file.unlink(missing_ok=True)

    def _try_resume_or_new(self):
        sessions = session_store.list_sessions()
        if self._resume_id:
            sess = session_store.load_session(self._resume_id)
            if sess:
                self._restore_session(sess)
                self._banner(resumed=True)
                m = f"[dim]Resumed session {sess.session_id} ({sess.message_count} messages)[/dim]"
                console.print(m)
                return
        if sessions and not self._resume_id:
            self._banner()
            self._prompt_resume(sessions)
        else:
            self._banner()

    def _prompt_resume(self, sessions: list[dict]):
        from datetime import datetime

        console.print("\n[dim]Previous sessions:[/dim]")
        for i, s in enumerate(sessions[:5]):
            dt = datetime.fromtimestamp(s["updated"]).strftime("%m-%d %H:%M")
            m = f"  [cyan]{i+1}.[/cyan]  {dt}  {s['work_dir']}  ({s['messages']} msgs)"
            console.print(m)
        console.print("  [cyan]n.[/cyan]  Start fresh")
        try:
            choice = input("Resume? (1/2/... or Enter for fresh): ").strip()
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < min(len(sessions), 5):
                    sess = session_store.load_session(sessions[idx]["id"])
                    if sess:
                        self._restore_session(sess)
                        console.print(f"[green]Resumed session {sess.session_id}[/green]")
        except (EOFError, KeyboardInterrupt):
            pass

    def _restore_session(self, sess: session_store.ZephyrSession):
        self.messages = list(sess.messages)
        self.ctx_project = sess.project
        self.ctx_board = sess.board
        self.ctx_build_dir = sess.build_dir
        self.client.default_board = sess.board
        self.client.work_dir = Path(sess.work_dir)
        self._session = sess

    def _save_and_exit(self):
        self._auto_save()
        sid = self._session.session_id if self._session else ""
        console.print(f"\n[green]Session saved.[/green] [dim]Resume:[/dim] zt repl --resume {sid}")
        console.print("[yellow]Goodbye.[/yellow]")

    def _auto_save(self):
        if self._session is None:
            self._session = session_store.ZephyrSession.new(
                work_dir=str(self.client.work_dir), board=self.ctx_board,
            )
        self._session.messages = list(self.messages)
        self._session.project = self.ctx_project
        self._session.board = self.ctx_board
        self._session.build_dir = self.ctx_build_dir
        session_store.save_session(self._session)

    def _list_sessions(self):
        sessions = session_store.list_sessions()
        if not sessions:
            console.print("[dim]No saved sessions.[/dim]")
            return
        from datetime import datetime
        for s in sessions:
            dt = datetime.fromtimestamp(s["updated"]).strftime("%m-%d %H:%M")
            console.print(f"  [cyan]{s['id']}[/cyan]  {dt}  {s['work_dir']}  ({s['messages']} msgs)")

    def _list_and_resume(self):
        self._list_sessions()
        sid = input("Session ID: ").strip()
        if sid:
            sess = session_store.load_session(sid)
            if sess:
                self._restore_session(sess)
                m = f"[green]Resumed session {sid} ({len(sess.messages)} messages)[/green]"
                console.print(m)
            else:
                console.print(f"[red]Session not found: {sid}[/red]")

    def _start_new_session(self):
        self._auto_save()
        old_id = self._session.session_id if self._session else None
        self.messages = []
        self._session = session_store.ZephyrSession.new(
            work_dir=str(self.client.work_dir), board=self.ctx_board,
        )
        self.messages.append({"role": "system", "content": SYSTEM_PROMPT})
        self.messages.append({
            "role": "system", "content": workspace.describe_workspace(self.client.work_dir),
        })
        console.print(f"[green]New session started. Previous saved as[/green] [cyan]{old_id}[/cyan]")
        tip = random.choice(_TIPS)
        console.print(f"[dim]{tip}[/dim]")

    def _show_context_full(self):
        t = Table(box=box.SIMPLE, show_header=False)
        t.add_column("Key", style="bold", width=12)
        t.add_column("Value")
        t.add_row("Workspace", str(self.client.work_dir))
        t.add_row("Project", self.ctx_project or "(none)")
        t.add_row("Board", self.ctx_board)
        t.add_row("Build dir", self.ctx_build_dir)
        t.add_row("Messages", str(len(self.messages)))
        if self._session:
            t.add_row("Session", self._session.session_id)
        console.print(Panel(t, title="Context", border_style="blue"))

    def _fork_session(self, target: str):
        path = Path(target).resolve() if target else self.client.work_dir
        if not path.exists():
            console.print(f"[red]Path not found: {path}[/red]")
            return
        sid = self._session.session_id if self._session else "new"
        console.print(Panel(
            f"[yellow]Forking sub-agent[/yellow] for [cyan]{path.name}[/cyan]\n"
            f"[dim]Session: {sid}[/dim]\n"
            f"[dim]Path: {path}[/dim]",
            border_style="yellow",
            title="Fork",
        ))
        if os.name == "nt":
            cmd = f'start "Zephyr Tools - {path.name}" cmd /k "zt repl --resume {sid}"'
            subprocess.Popen(cmd, shell=True)
        else:
            cmd = ["x-terminal-emulator", "-e", f"zt repl --resume {sid}"]
            subprocess.Popen(cmd)
        console.print("[green]New terminal opened.[/green] [dim]The sub-agent has its own session.[/dim]")

    def _show_slash_help(self):
        console.print(Panel(
            "[bold]Slash Commands:[/bold]\n"
            "  /new        Start a fresh conversation (current session auto-saved)\n"
            "  /fork       Open a new terminal with a dedicated REPL for current project\n"
            "  /fork <dir> Open a new terminal with a dedicated REPL for a specific project\n"
            "  /resume     List and resume a saved session\n"
            "  /sessions   List all saved sessions\n"
            "  /help       Show this help\n"
            "  status      Show current context\n"
            "  clear       Clear screen\n"
            "  quit / exit Exit\n"
            "\n"
            "[dim]You can also just describe what you want in natural language.[/dim]",
            title="Help",
            border_style="blue",
        ))

    def _banner(self, resumed: bool = False):
        from . import __version__

        if resumed:
            tag = "[dim]Session resumed[/dim]"
        else:
            tag = "[dim]quit / Ctrl+C to exit  |  /new for fresh session[/dim]"
        tip = random.choice(_TIPS)
        console.print(Panel(
            Text.from_markup(
                f"[bold cyan]Zephyr Tools[/bold cyan]  "
                f"[dim]v{__version__}[/dim]  {tag}\n"
                f"[dim]{tip}[/dim]"
            ),
            box=box.HEAVY,
            border_style="cyan",
        ))


def _clean_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0]
    return text.strip()


def run_repl(work_dir: str | Path | None = None, default_board: str = "nucleo_f411re", resume_session_id: str | None = None) -> int:
    ZephyrRepl(work_dir=work_dir, default_board=default_board, resume_session_id=resume_session_id).run()
    return 0
