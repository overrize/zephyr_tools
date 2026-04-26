"""LLM configuration helpers."""

from pathlib import Path
import os
from typing import Optional

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def get_llm_config(work_dir: Optional[Path] = None) -> tuple[str | None, str | None, str]:
    """Return api key, base url, and model for OpenAI-compatible APIs."""

    if work_dir:
        env_path = Path(work_dir) / ".env"
        if env_path.exists():
            try:
                from dotenv import load_dotenv

                load_dotenv(env_path)
            except ImportError:
                pass

    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("ZEPHYR_TOOLS_API_KEY")
    base_url = os.environ.get("OPENAI_API_BASE") or os.environ.get("ZEPHYR_TOOLS_API_BASE")
    model = os.environ.get("OPENAI_MODEL") or os.environ.get("ZEPHYR_TOOLS_MODEL") or "gpt-4o-mini"
    return api_key, base_url, model


def is_llm_configured(work_dir: Optional[Path] = None) -> bool:
    api_key, _, _ = get_llm_config(work_dir)
    return bool(api_key)
