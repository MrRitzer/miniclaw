"""Telegram channel plugin for MiniClaw.

Handles Telegram bot commands and message forwarding.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Callable

import httpx

from miniclaw.plugins.base import (
    BasePlugin,
    PluginError,
    PluginMetadata,
    PluginStartError,
    PluginStopError,
    PluginType,
)

logger = logging.getLogger(__name__)


@dataclass
class TelegramMessage:
    """A message from Telegram."""

    chat_id: int
    message_id: int
    text: str
    sender_id: int
    sender_username: str = ""


class TelegramCommandHandler:
    """Handles Telegram bot commands."""

    def __init__(self) -> None:
        self._commands: dict[str, Callable] = {}

    def register(self, command: str, handler: Callable) -> None:
        """Register a command handler."""
        self._commands[command] = handler

    async def handle(self, message: TelegramMessage) -> str | None:
        """Handle a message and return response."""
        text = message.text.strip()

        for cmd, handler in self._commands.items():
            if text.startswith(cmd):
                try:
                    return await handler(message)
                except Exception as e:
                    logger.error("Command %s failed: %s", cmd, e)
                    return f"Error: {e}"

        return None

    def get_commands(self) -> list[str]:
        """Get list of registered commands."""
        return list(self._commands.keys())


class TelegramPlugin(BasePlugin):
    """Telegram channel plugin for MiniClaw.

    Connects to Telegram Bot API, handles commands, and forwards
    messages to the AI gateway.
    """

    def __init__(self) -> None:
        """Initialize Telegram plugin."""
        self.bot_token: str = ""
        self.allowed_chat_ids: list[int] = []
        self.polling_timeout: int = 60
        self._client: httpx.AsyncClient | None = None
        self._running: bool = False
        self._poll_task: asyncio.Task | None = None
        self._command_handler = TelegramCommandHandler()
        self._message_callback: Callable | None = None
        self._ai_callback: Callable | None = None
        self._session_manager = None
        self._session = None
        self._offset: int = 0

        self._register_default_commands()

    @property
    def metadata(self) -> PluginMetadata:
        """Return plugin metadata."""
        return PluginMetadata(
            name="telegram",
            version="0.1.0",
            plugin_type=PluginType.CHANNEL,
            description="Telegram bot channel plugin",
            author="MiniClaw",
        )

    def initialize(self, config: dict[str, Any]) -> None:
        """Initialize the Telegram plugin."""
        bot_token = config.get("bot_token")
        if not bot_token:
            raise PluginError("Telegram bot_token is required")

        self.bot_token = bot_token
        self.allowed_chat_ids = config.get("allowed_chat_ids", [])
        self.polling_timeout = config.get("polling_timeout", 60)
        self._client = httpx.AsyncClient(
            base_url=f"https://api.telegram.org/bot{bot_token}",
            timeout=30.0,
        )
        self._running = False

        logger.info("Telegram plugin initialized")

    def _register_default_commands(self) -> None:
        """Register default command handlers."""
        self._command_handler.register("/start", self._cmd_start)
        self._command_handler.register("/help", self._cmd_help)
        self._command_handler.register("/models", self._cmd_models)
        self._command_handler.register("/new", self._cmd_new)
        self._command_handler.register("/save", self._cmd_save)
        self._command_handler.register("/sessions", self._cmd_sessions)
        self._command_handler.register("/resume", self._cmd_resume)
        self._command_handler.register("/heartbeat", self._cmd_heartbeat)
        self._command_handler.register("/status", self._cmd_status)

    async def _cmd_start(self, msg: TelegramMessage) -> str:
        """Handle /start command."""
        return (
            "👋 Welcome to MiniClaw!\n\n"
            "I'm an AI assistant that can help you with your projects.\n\n"
            "Use /help to see available commands."
        )

    async def _cmd_help(self, msg: TelegramMessage) -> str:
        """Handle /help command."""
        commands = self._command_handler.get_commands()
        cmd_list = "\n".join(f"  {cmd}" for cmd in sorted(commands))
        return (
            "📚 Available Commands:\n\n"
            f"{cmd_list}\n\n"
            "Just send a message to chat with me!"
        )

    async def _cmd_models(self, msg: TelegramMessage) -> str:
        """Handle /models command - list available AI models."""
        return (
            "🤖 Available Models:\n\n"
            "**OpenAI:**\n"
            "  - gpt-4o-mini (default)\n"
            "  - gpt-4o\n"
            "  - gpt-4-turbo\n\n"
            "**Anthropic:**\n"
            "  - claude-sonnet-4-20250514 (default)\n"
            "  - claude-3-5-sonnet-20241022\n"
            "  - claude-3-5-haiku-20241022\n\n"
            "Configure your preferred model in /data/agent.md"
        )

    async def _cmd_new(self, msg: TelegramMessage) -> str:
        """Handle /new command - start a new session."""
        if not self._session_manager:
            return "❌ Session manager not configured"

        session = self._session_manager.create_session()
        self._session = session
        self._session_manager.set_active_session(session.id)

        return f"🆕 New session started: **{session.name}**\n\nStart chatting!"

    async def _cmd_save(self, msg: TelegramMessage) -> str:
        """Handle /save command - save current session."""
        if not self._session:
            return "❌ No active session to save"

        parts = msg.text.split(" ", 1)
        if len(parts) < 2:
            return "Usage: /save <name>"

        name = parts[1].strip()
        self._session.name = name
        self._session_manager.save_session(self._session)

        return f"💾 Session saved as: **{name}**"

    async def _cmd_sessions(self, msg: TelegramMessage) -> str:
        """Handle /sessions command - list saved sessions."""
        if not self._session_manager:
            return "❌ Session manager not configured"

        sessions = self._session_manager.list_sessions(include_inactive=True)

        if not sessions:
            return "📭 No saved sessions"

        lines = ["📋 Saved Sessions:\n"]
        for s in sessions:
            active = " (active)" if s.is_active else ""
            lines.append(f"  • {s.name}{active}")

        return "\n".join(lines)

    async def _cmd_resume(self, msg: TelegramMessage) -> str:
        """Handle /resume command - resume a session."""
        if not self._session_manager:
            return "❌ Session manager not configured"

        parts = msg.text.split(" ", 1)
        if len(parts) < 2:
            return "Usage: /resume <session_id or name>"

        query = parts[1].strip()

        session = self._session_manager.get_session(query)
        if not session:
            sessions = self._session_manager.list_sessions(include_inactive=True)
            for s in sessions:
                if s.name.lower() == query.lower():
                    session = s
                    break

        if not session:
            return f"❌ Session not found: {query}"

        self._session = session
        self._session_manager.set_active_session(session.id)

        msg_count = len(session.messages)
        return f"✅ Resumed session: **{session.name}**\n\n{msg_count} messages"

    async def _cmd_heartbeat(self, msg: TelegramMessage) -> str:
        """Handle /heartbeat command - trigger immediate heartbeat."""
        return "💓 Heartbeat triggered"

    async def _cmd_status(self, msg: TelegramMessage) -> str:
        """Handle /status command - show agent status."""
        session_name = self._session.name if self._session else "None"
        msg_count = len(self._session.messages) if self._session else 0

        return (
            "📊 MiniClaw Status\n\n"
            f"Active Session: **{session_name}**\n"
            f"Messages: {msg_count}\n"
            f"Heartbeat: Enabled"
        )

    def set_message_callback(self, callback: Callable) -> None:
        """Set callback for non-command messages (AI chat)."""
        self._message_callback = callback

    def set_session_manager(self, session_manager) -> None:
        """Set the session manager."""
        self._session_manager = session_manager

    def set_ai_callback(self, callback: Callable) -> None:
        """Set AI response callback."""
        self._ai_callback = callback

    def start(self) -> None:
        """Start the Telegram bot."""
        if self._running:
            return

        self._running = True
        self._poll_task = asyncio.create_task(self._poll_updates())
        logger.info("Telegram bot started")

    async def stop(self) -> None:
        """Stop the Telegram bot gracefully."""
        if not self._running:
            return

        self._running = False

        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None

        if self._client:
            await self._client.aclose()
            self._client = None

        logger.info("Telegram bot stopped")

    async def _poll_updates(self) -> None:
        """Poll Telegram for updates."""
        while self._running:
            try:
                updates = await self._get_updates()
                for update in updates:
                    await self._handle_update(update)
                    self._offset = update["update_id"] + 1

                await asyncio.sleep(self.polling_timeout)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Poll error: %s", e)
                await asyncio.sleep(5)

    async def _get_updates(self) -> list[dict]:
        """Get updates from Telegram API."""
        if not self._client:
            return []

        try:
            response = await self._client.get(
                "/getUpdates",
                params={"offset": self._offset, "timeout": self.polling_timeout},
            )
            response.raise_for_status()
            data = response.json()

            if data.get("ok"):
                return data.get("result", [])
            return []

        except httpx.HTTPError as e:
            logger.error("Failed to get updates: %s", e)
            return []

    async def _handle_update(self, update: dict) -> None:
        """Handle an incoming Telegram update."""
        if "message" not in update:
            return

        msg_data = update["message"]
        message = TelegramMessage(
            chat_id=msg_data["chat"]["id"],
            message_id=msg_data["message_id"],
            text=msg_data.get("text", ""),
            sender_id=msg_data["from"]["id"],
            sender_username=msg_data["from"].get("username", ""),
        )

        if self.allowed_chat_ids and message.chat_id not in self.allowed_chat_ids:
            logger.warning("Message from disallowed chat: %d", message.chat_id)
            return

        if message.text.startswith("/"):
            response = await self._command_handler.handle(message)
            if response:
                await self._send_message(message.chat_id, response)
        else:
            if self._message_callback:
                response = await self._message_callback(message)
                if response:
                    await self._send_message(message.chat_id, response)

    async def _send_message(self, chat_id: int, text: str) -> None:
        """Send a message to a Telegram chat."""
        if not self._client:
            return

        try:
            response = await self._client.post(
                "/sendMessage",
                json={"chat_id": chat_id, "text": text},
            )
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error("Failed to send message: %s", e)

    def health_check(self) -> bool:
        """Return True if Telegram connection is healthy."""
        return self._running

    def is_chat_allowed(self, chat_id: int) -> bool:
        """Check if a chat ID is allowed to interact with the bot."""
        if not self.allowed_chat_ids:
            return True
        return chat_id in self.allowed_chat_ids
