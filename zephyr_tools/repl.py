"""Zephyr Tools conversational REPL -- Claude Code style agent loop."""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich import box

from .client import ZephyrToolsClient
from .errors import ZephyrToolsError
from .llm.config import get_llm_config

console = Console()

try:
    from openai import OpenAI, APIError
except ImportError:
    OpenAI = None
    APIError = Exception


SYSTEM_PROMPT = """You are an embedded development assistant for Zephyr RTOS. You help users build, flash, and debug embedded firmware.

You have tools for environment checks, board listing, project creation, building, flashing, monitoring, and file editing.

RULES:
1. Always run doctor first if you are unsure about toolchain state.
2. Use create_project to scaffold a Zephyr app. Default board: nucleo_f411re.
3. Use the current project context for builds unless the user specifies otherwise.
4. Explain what you are doing in simple terms.
5. If a tool fails, explain the error and suggest fixes.
6. Keep responses concise.
7. Context is maintained between turns (project, board, build dir).
"""

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
            "description": "Create a new Zephyr application project",
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
]


class ZephyrRepl:
    def __init__(self, work_dir: str | Path | None = None, default_board: str = "nucleo_f411re"):
        self.client = ZephyrToolsClient(work_dir=work_dir, default_board=default_board)
        self.messages: list[dict] = []
        self.ctx_project: str | None = None
        self.ctx_board: str = default_board
        self.ctx_build_dir: str = "build"

    def run(self):
        self._banner()
        api_key, base_url, model = self._resolve_api()
        if not api_key:
            return
        if OpenAI is None:
            console.print("[red]openai package not installed. Run: pip install openai[/red]")
            return
        self.llm = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.messages.append({"role": "system", "content": SYSTEM_PROMPT})
        self.messages.append({
            "role": "system",
            "content": f"Work directory: {self.client.work_dir}\nDefault board: {self.ctx_board}",
        })
        try:
            while True:
                try:
                    text = input("\nzt> ").strip()
                except (EOFError, KeyboardInterrupt):
                    console.print("\n[yellow]Goodbye.[/yellow]")
                    break
                if not text:
                    continue
                if text.lower() in ("quit", "exit"):
                    console.print("[yellow]Goodbye.[/yellow]")
                    break
                if text.lower() == "clear":
                    console.clear()
                    continue
                self.messages.append({"role": "user", "content": text})
                self._process_turn()
        except Exception as e:
            console.print(f"\n[red]Fatal: {e}[/red]")

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
                print(delta.content, end="", flush=True)
            if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                reasoning_buffer += delta.reasoning_content
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
        print()

        if content_buffer:
            self.messages.append({"role": "assistant", "content": content_buffer})

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
                console.print(f"[dim]>> tool: {name}{args}[/dim]")
                result = self._exec_tool(name, args)
                trunc = result[:500] + "..." if len(result) > 500 else result
                console.print(f"[dim]<< result: {trunc}[/dim]")
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

    def _banner(self):
        from . import __version__
        console.print(Panel(
            Text.from_markup(
                "[bold cyan]Zephyr Tools[/bold cyan]  "
                f"[dim]v{__version__}[/dim]\n"
                "[dim]Conversational REPL -- describe what you want to do[/dim]\n"
                "[dim]quit / Ctrl+C to exit  |  clear to clear screen[/dim]"
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


def run_repl(work_dir: str | Path | None = None, default_board: str = "nucleo_f411re") -> int:
    ZephyrRepl(work_dir=work_dir, default_board=default_board).run()
    return 0
def run_repl(work_dir: str | Path | None = None, default_board: str = "nucleo_f411re") -> int:
    ZephyrRepl(work_dir=work_dir, default_board=default_board).run()
    return 0
