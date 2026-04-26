"""Common exception hierarchy for Zephyr Tools."""


class ZephyrToolsError(Exception):
    """Base exception for all user-facing Zephyr Tools failures."""


class ConfigurationError(ZephyrToolsError):
    """The local Zephyr/toolchain environment is missing or misconfigured."""


class BuildError(ZephyrToolsError):
    """A Zephyr build command failed."""


class HardwareError(ZephyrToolsError):
    """Flashing, debugging, or monitoring hardware failed."""


class LLMError(ZephyrToolsError):
    """Code generation or repair through an LLM failed."""
