"""Plugin registry for MiniClaw.

Discovers and manages plugins at runtime.
"""

from importlib import import_module, metadata
from typing import Any

from miniclaw.plugins.base import BasePlugin, PluginError, PluginMetadata, PluginType


class PluginRegistry:
    """Registry for discovering and managing plugins."""

    def __init__(self) -> None:
        self._plugins: dict[str, BasePlugin] = {}
        self._plugin_classes: dict[str, type[BasePlugin]] = {}

    def register(self, name: str, plugin_class: type[BasePlugin]) -> None:
        """Register a plugin class.

        Args:
            name: Unique plugin name.
            plugin_class: The plugin class to register.
        """
        if name in self._plugin_classes:
            raise PluginError(f"Plugin already registered: {name}")
        self._plugin_classes[name] = plugin_class

    def create(self, name: str, config: dict[str, Any]) -> BasePlugin:
        """Create and initialize a plugin instance.

        Args:
            name: Name of the plugin to create.
            config: Configuration for the plugin.

        Returns:
            Initialized plugin instance.
        """
        if name not in self._plugin_classes:
            raise PluginError(f"Plugin not found: {name}")

        plugin_class = self._plugin_classes[name]
        plugin = plugin_class()
        plugin.initialize(config)
        self._plugins[name] = plugin
        return plugin

    def get(self, name: str) -> BasePlugin | None:
        """Get a plugin instance by name.

        Args:
            name: Plugin name.

        Returns:
            Plugin instance or None if not found.
        """
        return self._plugins.get(name)

    def list_plugins(self) -> list[PluginMetadata]:
        """List all registered plugin metadata.

        Returns:
            List of plugin metadata for all registered plugins.
        """
        return [
            plugin_class().metadata
            for plugin_class in self._plugin_classes.values()
        ]

    def start_all(self) -> None:
        """Start all registered plugins."""
        for plugin in self._plugins.values():
            plugin.start()

    def stop_all(self) -> None:
        """Stop all plugins gracefully."""
        for plugin in reversed(list(self._plugins.values())):
            plugin.stop()
        self._plugins.clear()

    def load_plugins_from_entry_points(self) -> None:
        """Load plugins registered via setuptools entry points.

        Looks for 'miniclaw.plugins' entry points.
        """
        for ep in metadata.entry_points(group="miniclaw.plugins"):
            try:
                plugin_class = ep.load()
                self.register(ep.name, plugin_class)
            except Exception as e:
                raise PluginError(f"Failed to load plugin {ep.name}: {e}") from e


# Global registry instance
registry = PluginRegistry()


def register_plugin(name: str, plugin_class: type[BasePlugin]) -> None:
    """Register a plugin class with the global registry.

    Use as a decorator or call directly.

    Example:
        @register_plugin("my_plugin")
        class MyPlugin(BasePlugin):
            ...
    """
    registry.register(name, plugin_class)


def get_plugin(name: str) -> BasePlugin | None:
    """Get a plugin from the global registry."""
    return registry.get(name)


def create_plugin(name: str, config: dict[str, Any]) -> BasePlugin:
    """Create a plugin from the global registry."""
    return registry.create(name, config)
