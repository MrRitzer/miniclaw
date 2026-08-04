"""OpenAI provider plugin for MiniClaw."""

from miniclaw.plugins.base import (
    PluginMetadata,
    PluginType,
)

# Import the plugin class for registration
from miniclaw.plugins.openai.plugin import OpenAIPlugin

# Register this plugin
from miniclaw.plugins.registry import register_plugin
register_plugin("openai", OpenAIPlugin)

__all__ = ["OpenAIPlugin"]
