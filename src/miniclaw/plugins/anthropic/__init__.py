"""Anthropic provider plugin for MiniClaw."""

from miniclaw.plugins.base import (
    PluginMetadata,
    PluginType,
)

# Import the plugin class for registration
from miniclaw.plugins.anthropic.plugin import AnthropicPlugin

# Register this plugin
from miniclaw.plugins.registry import register_plugin
register_plugin("anthropic", AnthropicPlugin)

__all__ = ["AnthropicPlugin"]
