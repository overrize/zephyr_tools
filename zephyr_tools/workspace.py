"""Workspace detection and scoping for Zephyr Tools REPL."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich import box

console = Console()


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
        console.print(Panel(
            f"[green]Detected Zephyr workspace:[/green] [cyan]{detected}[/cyan]",
            border_style="green",
        ))
        return detected

    console.print(Panel(
        "[yellow]Not inside a Zephyr workspace.[/yellow]\n"
        f"[dim]Current directory: {cwd}[/dim]",
        title="Workspace",
        border_style="yellow",
    ))
    try:
        answer = input("Enter workspace path (or press Enter to use current directory): ").strip()
        if answer:
            p = Path(answer).resolve()
            if p.exists():
                return p
            console.print("[red]Path does not exist. Using current directory.[/red]")
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
