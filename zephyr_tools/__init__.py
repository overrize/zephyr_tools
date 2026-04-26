"""Zephyr Tools - unified tooling for Zephyr based embedded projects."""

from .client import ZephyrToolsClient
from .errors import BuildError, ConfigurationError, HardwareError, LLMError, ZephyrToolsError

__version__ = "0.2.0"

__all__ = [
    "ZephyrToolsClient",
    "ZephyrToolsError",
    "ConfigurationError",
    "BuildError",
    "HardwareError",
    "LLMError",
    "__version__",
]
