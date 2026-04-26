"""Zephyr-oriented LLM code generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from zephyr_tools.errors import LLMError

from .config import get_llm_config

try:
    from openai import APIError, APIStatusError, OpenAI
except ImportError:
    OpenAI = None
    APIError = Exception
    APIStatusError = Exception


SYSTEM_PROMPT = """你是一名 Zephyr RTOS 嵌入式工程师。

生成代码时必须遵守：
1. 使用 Zephyr 公共 API，例如 <zephyr/kernel.h>、<zephyr/drivers/gpio.h>、<zephyr/device.h>。
2. 使用 devicetree alias、chosen node 或 overlay，不要硬编码 STM32 寄存器或 STM32 LL/HAL API。
3. 如需求涉及 GPIO/串口/I2C/SPI/PWM，请同时说明需要的 prj.conf 配置和 devicetree overlay。
4. 输出必须是 JSON，字段为 main_c、prj_conf、overlay、notes。不要输出 markdown。
"""

FIX_SYSTEM_PROMPT = """你是一名 Zephyr RTOS 构建错误修复专家。
根据用户需求、当前文件和 west build 错误，修复 main.c、prj.conf、overlay。
输出必须是 JSON，字段为 main_c、prj_conf、overlay、notes。不要输出 markdown。
"""


@dataclass(slots=True)
class GeneratedZephyrApp:
    main_c: str
    prj_conf: str
    overlay: str = ""
    notes: str = ""


class CodegenService:
    """Generate and repair Zephyr application files."""

    def __init__(self, work_dir: str | Path | None = None):
        self.work_dir = Path(work_dir).resolve() if work_dir else Path.cwd()

    def generate(
        self,
        prompt: str,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> GeneratedZephyrApp:
        if OpenAI is None:
            raise LLMError("请安装 openai: pip install openai")

        api_key, base_url, model = self._resolve_config(api_key, base_url, model)
        user_prompt = f"请根据需求生成 Zephyr 应用：\n{prompt}"
        content = self._chat(SYSTEM_PROMPT, user_prompt, api_key, base_url, model, temperature=0.2)
        return self._parse_generated(content)

    def fix(
        self,
        prompt: str,
        main_c: str,
        prj_conf: str,
        overlay: str,
        build_error: str,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> GeneratedZephyrApp:
        if OpenAI is None:
            raise LLMError("请安装 openai: pip install openai")

        api_key, base_url, model = self._resolve_config(api_key, base_url, model)
        user_prompt = f"""需求:
{prompt}

main.c:
```c
{main_c}
```

prj.conf:
```conf
{prj_conf}
```

overlay:
```dts
{overlay}
```

west build 错误:
{build_error}
"""
        content = self._chat(FIX_SYSTEM_PROMPT, user_prompt, api_key, base_url, model, temperature=0.1)
        return self._parse_generated(content)

    def _resolve_config(
        self,
        api_key: str | None,
        base_url: str | None,
        model: str | None,
    ) -> tuple[str, str | None, str]:
        cfg_key, cfg_base, cfg_model = get_llm_config(self.work_dir)
        api_key = api_key or cfg_key
        base_url = base_url or cfg_base
        model = model or cfg_model
        if not api_key:
            raise LLMError("未设置 OPENAI_API_KEY 或 ZEPHYR_TOOLS_API_KEY")
        return api_key, base_url, model

    def _chat(
        self,
        system_prompt: str,
        user_prompt: str,
        api_key: str,
        base_url: str | None,
        model: str,
        temperature: float,
    ) -> str:
        client_kw = {"api_key": api_key}
        if base_url:
            client_kw["base_url"] = base_url.rstrip("/")
        client = OpenAI(**client_kw)
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
            )
        except (APIStatusError, APIError) as exc:
            raise LLMError(f"LLM 调用失败: {str(exc)[:200]}") from exc
        return response.choices[0].message.content or ""

    def _parse_generated(self, content: str) -> GeneratedZephyrApp:
        import json

        text = content.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?", "", text).strip()
            text = re.sub(r"```$", "", text).strip()
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMError("模型未返回有效 JSON") from exc

        return GeneratedZephyrApp(
            main_c=str(payload.get("main_c") or ""),
            prj_conf=str(payload.get("prj_conf") or ""),
            overlay=str(payload.get("overlay") or ""),
            notes=str(payload.get("notes") or ""),
        )
