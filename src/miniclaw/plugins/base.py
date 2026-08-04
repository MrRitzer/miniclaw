"""Base plugin interface for MiniClaw."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class PluginType(Enum):
    """Types of plugins in MiniClaw."""

    PROVIDER = auto()  # AI provider (OpenAI, Anthropic, etc.)
    CHANNEL = auto()  # Messaging channel (Telegram, etc.)


@dataclass
class PluginMetadata:
    """Metadata for a plugin."""

    name: str
    version: str
    plugin_type: PluginType
    description: str = ""
    author: str = ""
    config_schema: dict[str, Any] = field(default_factory=dict)


class BasePlugin(ABC):
    """Base class for all MiniClaw plugins.

    Plugins must implement:
    - `metadata` property: returns PluginMetadata
    - `initialize(config)` method: set up the plugin
    - `start()` method: start the plugin (for long-running plugins)
    - `stop()` method: stop the plugin gracefully

    Optional:
    - `health_check()` method: return health status
    """

    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Return plugin metadata."""
        ...

    @abstractmethod
    def initialize(self, config: dict[str, Any]) -> None:
        """Initialize the plugin with configuration.

        Args:
            config: Plugin-specific configuration from environment or config file.

        Raises:
            PluginError: If initialization fails.
        """
        ...

    @abstractmethod
    def start(self) -> None:
        """Start the plugin.

        Raises:
            PluginError: If start fails.
        """
        ...

    @abstractmethod
    def stop(self) -> None:
        """Stop the plugin gracefully.

        Raises:
            PluginError: If stop fails.
        """
        ...

    def health_check(self) -> bool:
        """Return True if plugin is healthy.

        Override to provide custom health checking.
        """
        return True


class PluginError(Exception):
    """Base exception for plugin errors."""

    pass


class PluginInitializationError(PluginError):
    """Raised when plugin initialization fails."""

    pass


class PluginStartError(PluginError):
    """Raised when plugin start fails."""

    pass


class PluginStopError(PluginError):
    """Raised when plugin stop fails."""

    pass
