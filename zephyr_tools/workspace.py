"""Workspace detection and scoping for Zephyr Tools REPL."""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

console = Console()

_HISTORY_FILE = Path.home() / ".zephyr_sessions" / "workspaces.json"
_MAX_HISTORY = 8


def _load_history() -> list[dict]:
    if not _HISTORY_FILE.exists():
        return []
    try:
        return json.loads(_HISTORY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _save_history(workspaces: list[dict]):
    _HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    _HISTORY_FILE.write_text(json.dumps(workspaces, indent=2, ensure_ascii=False), encoding="utf-8")


def _record_workspace(path: Path):
    import time
    workspaces = _load_history()
    path_str = str(path.resolve())
    workspaces = [w for w in workspaces if w["path"] != path_str]
    workspaces.insert(0, {"path": path_str, "last_used": time.time()})
    _save_history(workspaces[: _MAX_HISTORY])


def detect_workspace(path: Path | None = None) -> Path | None:
    """Detect Zephyr workspace by looking for west.yml or .zephyr files."""
    root = (path or Path.cwd()).resolve()
    for marker in ("west.yml", "west.yaml", ".zephyr", "zephyr"):
        if (root / marker).exists():
            return root
    for parent in root.parents:
        for marker in ("west.yml", "west.yaml", ".zephyr"):
            if (parent / marker).exists():
                return parent
    return None


def has_zephyr_app(path: Path) -> bool:
    """Check if directory looks like a Zephyr app (has prj.conf or src/main.c)."""
    return (path / "prj.conf").exists() or (path / "src" / "main.c").exists()


def prompt_workspace() -> Path:
    """Ask user where to work. Returns the chosen workspace path."""
    cwd = Path.cwd()
    detected = detect_workspace(cwd)

    if detected:
        _record_workspace(detected)
        console.print(Panel(
            f"[green]Detected Zephyr workspace:[/green] [cyan]{detected}[/cyan]",
            border_style="green",
        ))
        return detected

    history = _load_history()

    if history:
        try:
            from prompt_toolkit.shortcuts import radiolist_dialog
            from prompt_toolkit.styles import Style as PtStyle

            pt_style = PtStyle.from_dict({
                "dialog": "bg:#1f222a",
                "dialog.body": "bg:#1f222a",
                "dialog.body label": "fg:#e0e0e0",
                "dialog.body label.selected": "fg:#6cb6ff bold",
            })
            choices = []
            for i, ws in enumerate(history[:7]):
                from datetime import datetime
                dt = datetime.fromtimestamp(ws["last_used"]).strftime("%m-%d %H:%M")
                label = f"{ws['path']}  ({dt})"
                choices.append((ws["path"], label))
            choices.append(("__custom__", "[type a new path]"))
            result = radiolist_dialog(
                title="Select workspace",
                text="Click to choose, or select 'type a new path':",
                values=choices,
                style=pt_style,
            ).run()
            if result and result != "__custom__":
                p = Path(result).resolve()
                if p.exists():
                    _record_workspace(p)
                    return p
                console.print("[red]Path no longer exists.[/red]")
            elif result == "__custom__":
                pass
            else:
                _record_workspace(cwd)
                return cwd
        except Exception:
            pass

        console.print("[dim]Recent workspaces:[/dim]")
        t = Table(box=box.SIMPLE, show_header=False)
        t.add_column("#", width=3, style="cyan")
        t.add_column("Path", width=50)
        t.add_column("Last used")
        for i, ws in enumerate(history[:5]):
            from datetime import datetime
            dt = datetime.fromtimestamp(ws["last_used"]).strftime("%m-%d %H:%M")
            found = " [green]*[/green]" if Path(ws["path"]).exists() else " [red](missing)[/red]"
            t.add_row(f"{i+1}.", ws["path"] + found, dt)
        console.print(t)
        console.print("  [dim]Enter a number to select, or type a path, or press Enter for current dir[/dim]")
    else:
        console.print(Panel(
            "[yellow]Not inside a Zephyr workspace.[/yellow]\n"
            f"[dim]Current directory: {cwd}[/dim]",
            title="Workspace",
            border_style="yellow",
        ))

    try:
        answer = input("Workspace: ").strip()
        if answer.isdigit() and 1 <= int(answer) <= len(history):
            p = Path(history[int(answer) - 1]["path"])
            if p.exists():
                _record_workspace(p)
                return p
            console.print("[red]Path no longer exists.[/red]")
            return prompt_workspace()
        if answer:
            p = Path(answer).resolve()
            if p.exists():
                _record_workspace(p)
                return p
            console.print("[red]Path does not exist. Using current directory.[/red]")
        _record_workspace(cwd)
        return cwd
    except (EOFError, KeyboardInterrupt):
        return cwd


def describe_workspace(path: Path) -> str:
    """Return a human-readable description of the workspace."""
    lines = [f"Workspace: {path}"]
    zephyr = detect_workspace(path)
    if zephyr:
        lines.append(f"Zephyr root: {zephyr}")
    apps = list(path.glob("**/prj.conf"))
    if apps:
        lines.append(f"Zephyr apps: {len(apps)}")
    return "\n".join(lines)
