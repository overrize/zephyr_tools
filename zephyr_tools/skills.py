"""Skills loading system — loads skills from .zephyr_skills/ directory."""

from __future__ import annotations

from pathlib import Path


def load_skills(work_dir: Path | None = None) -> list[dict]:
    """Load skill descriptions from .zephyr_skills/ directory."""
    root = (work_dir or Path.cwd()).resolve()
    skills_dir = root / ".zephyr_skills"
    if not skills_dir.exists():
        return []
    skills = []
    for path in sorted(skills_dir.glob("*.md")):
        skills.append({
            "name": path.stem,
            "content": path.read_text(encoding="utf-8").strip(),
        })
    for path in sorted(skills_dir.glob("*.json")):
        import json
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            skills.append(data)
        except json.JSONDecodeError:
            pass
    return skills
