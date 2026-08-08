"""Configuration loading for MiniClaw.

Loads configuration from environment variables and .env files.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


def _find_env_file() -> Path | None:
    """Find .env file by searching up from current directory."""
    cwd = Path.cwd()
    for path in [cwd] + list(cwd.parents):
        env_file = path / ".env"
        if env_file.exists():
            return env_file
    return None


def load_config() -> None:
    """Load environment variables from .env file if present."""
    env_file = _find_env_file()
    if env_file:
        load_dotenv(env_file)
    else:
        # Try home directory
        home_env = Path.home() / ".miniclaw" / ".env"
        if home_env.exists():
            load_dotenv(home_env)


@dataclass
class TelegramConfig:
    """Telegram plugin configuration."""

    bot_token: str = ""
    allowed_chat_ids: list[int] = field(default_factory=list)
    polling_timeout: int = 60


@dataclass
class OpenAIConfig:
    """OpenAI provider configuration."""

    api_key: str = ""
    model: str = "gpt-4o-mini"
    base_url: str | None = None  # For proxies/custom endpoints


@dataclass
class AnthropicConfig:
    """Anthropic provider configuration."""

    api_key: str = ""
    model: str = "claude-sonnet-4-20250514"
    base_url: str | None = None  # For proxies/custom endpoints


@dataclass
class MiniClawConfig:
    """Main MiniClaw configuration."""

    db_path: Path = field(default_factory=lambda: Path.home() / ".miniclaw" / "memory.db")
    data_dir: Path = field(default_factory=lambda: Path("data").resolve())
    workspace_dir: Path = field(default_factory=lambda: Path("data/workspace").resolve())
    log_level: str = "INFO"
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    openai: OpenAIConfig = field(default_factory=OpenAIConfig)
    anthropic: AnthropicConfig = field(default_factory=AnthropicConfig)


def _get_env(key: str, default: str = "") -> str:
    """Get environment variable with MINICLAW_ prefix."""
    return os.getenv(f"MINICLAW_{key}", default)


def _get_env_int(key: str, default: int) -> int:
    """Get integer environment variable."""
    value = _get_env(key)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_env_list(key: str, default: list = None) -> list:
    """Get comma-separated list from environment variable."""
    value = _get_env(key)
    if not value:
        return default or []
    return [item.strip() for item in value.split(",") if item.strip()]


def load_miniclaw_config() -> MiniClawConfig:
    """Load MiniClaw configuration from environment.

    Returns:
        MiniClawConfig with all settings.
    """
    # Load .env file first
    load_config()

    # Core config
    db_path = Path(_get_env("DB_PATH", "~/.miniclaw/memory.db")).expanduser()
    data_dir = Path(_get_env("DATA_DIR", "data")).resolve()
    workspace_dir = Path(_get_env("WORKSPACE_DIR", "data/workspace")).resolve()
    log_level = _get_env("LOG_LEVEL", "INFO")

    # Telegram config
    telegram = TelegramConfig(
        bot_token=_get_env("TELEGRAM_BOT_TOKEN", ""),
        allowed_chat_ids=_get_env_list("TELEGRAM_ALLOWED_CHAT_IDS"),
        polling_timeout=_get_env_int("TELEGRAM_POLLING_TIMEOUT", 60),
    )

    # OpenAI config
    openai = OpenAIConfig(
        api_key=_get_env("OPENAI_API_KEY", ""),
        model=_get_env("OPENAI_MODEL", "gpt-4o-mini"),
        base_url=_get_env("OPENAI_BASE_URL") or None,
    )

    # Anthropic config
    anthropic = AnthropicConfig(
        api_key=_get_env("ANTHROPIC_API_KEY", ""),
        model=_get_env("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
        base_url=_get_env("ANTHROPIC_BASE_URL") or None,
    )

    return MiniClawConfig(
        db_path=db_path,
        data_dir=data_dir,
        workspace_dir=workspace_dir,
        log_level=log_level,
        telegram=telegram,
        openai=openai,
        anthropic=anthropic,
    )


def get_plugin_config(plugin_name: str) -> dict[str, Any]:
    """Get configuration dict for a specific plugin.

    Args:
        plugin_name: Name of the plugin (e.g., "telegram", "openai").

    Returns:
        Dict of configuration values for the plugin.
    """
    # Load .env first
    load_config()

    # Build config based on plugin type
    if plugin_name == "telegram":
        return {
            "bot_token": _get_env("TELEGRAM_BOT_TOKEN"),
            "allowed_chat_ids": _get_env_list("TELEGRAM_ALLOWED_CHAT_IDS"),
            "polling_timeout": _get_env_int("TELEGRAM_POLLING_TIMEOUT", 60),
        }
    elif plugin_name == "openai":
        return {
            "api_key": _get_env("OPENAI_API_KEY"),
            "model": _get_env("OPENAI_MODEL", "gpt-4o-mini"),
            "base_url": _get_env("OPENAI_BASE_URL") or None,
        }
    elif plugin_name == "anthropic":
        return {
            "api_key": _get_env("ANTHROPIC_API_KEY"),
            "model": _get_env("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
            "base_url": _get_env("ANTHROPIC_BASE_URL") or None,
        }
    else:
        return {}
