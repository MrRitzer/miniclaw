"""Telegram channel plugin for MiniClaw."""

from miniclaw.plugins.base import (
    PluginMetadata,
    PluginType,
)

# Import the plugin class for registration
from miniclaw.plugins.telegram.plugin import TelegramPlugin

# Register this plugin
from miniclaw.plugins.registry import register_plugin
register_plugin("telegram", TelegramPlugin)

__all__ = ["TelegramPlugin"]
