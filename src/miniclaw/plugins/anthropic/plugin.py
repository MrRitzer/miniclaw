"""Anthropic provider plugin implementation."""

import logging
from typing import Any

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


class AnthropicPlugin(BasePlugin):
    """Anthropic provider plugin for MiniClaw.

    Handles communication with Anthropic's Claude API.
    """

    def __init__(self) -> None:
        """Initialize Anthropic plugin."""
        self.api_key: str = ""
        self.model: str = "claude-sonnet-4-20250514"
        self.base_url: str = "https://api.anthropic.com"
        self._client: httpx.AsyncClient | None = None
        self._running: bool = False
        self._available_models: list[dict] = []

    @property
    def metadata(self) -> PluginMetadata:
        """Return plugin metadata."""
        return PluginMetadata(
            name="anthropic",
            version="0.1.0",
            plugin_type=PluginType.PROVIDER,
            description="Anthropic Claude API provider plugin",
            author="MiniClaw",
        )

    def initialize(self, config: dict[str, Any]) -> None:
        """Initialize the Anthropic plugin."""
        api_key = config.get("api_key")
        if not api_key:
            raise PluginError("Anthropic api_key is required")

        self.api_key = api_key
        self.model = config.get("model", "claude-sonnet-4-20250514")
        self.base_url = config.get("base_url", "https://api.anthropic.com")
        self._client = None
        self._running = False
        logger.info("Anthropic plugin initialized with model: %s", self.model)

    async def _ensure_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "x-api-key": self.api_key,
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01",
                },
                timeout=60.0,
            )
        return self._client

    async def list_models(self) -> list[dict[str, Any]]:
        """List available models from Anthropic API.

        Note: Anthropic doesn't have a list models endpoint, so we return
        known available models.
        """
        known_models = [
            {"id": "claude-opus-4-20250514", "description": "Most capable model"},
            {"id": "claude-sonnet-4-20250514", "description": "Balanced model (default)"},
            {"id": "claude-3-5-sonnet-20241022", "description": "Previous generation"},
            {"id": "claude-3-5-haiku-20241022", "description": "Fast, efficient model"},
        ]

        self._available_models = known_models
        logger.info("Returning %d known Anthropic models", len(known_models))
        return known_models

    def start(self) -> None:
        """Start the Anthropic provider."""
        if self._running:
            return

        self._running = True
        logger.info("Anthropic plugin started")

    async def stop(self) -> None:
        """Stop the Anthropic provider gracefully."""
        if not self._running:
            return

        if self._client:
            await self._client.aclose()
            self._client = None
        self._running = False
        logger.info("Anthropic plugin stopped")

    def health_check(self) -> bool:
        """Return True if Anthropic client is healthy."""
        return self._running

    async def complete(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> str:
        """Send a completion request to Anthropic.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            **kwargs: Additional parameters (temperature, max_tokens, etc.).

        Returns:
            Assistant's response text.

        Raises:
            PluginError: If the request fails.
        """
        if not self._running:
            raise PluginError("Anthropic plugin is not running")

        try:
            client = await self._ensure_client()

            # Convert messages format for Anthropic
            # Anthropic uses 'user' and 'assistant' roles directly
            anthropic_messages = []
            system_content = ""

            for msg in messages:
                if msg["role"] == "system":
                    system_content = msg["content"]
                else:
                    anthropic_messages.append({
                        "role": msg["role"],
                        "content": msg["content"],
                    })

            request_data: dict[str, Any] = {
                "model": self.model,
                "messages": anthropic_messages,
                "max_tokens": kwargs.get("max_tokens", 1024),
            }

            if system_content:
                request_data["system"] = system_content

            if "temperature" in kwargs:
                request_data["temperature"] = kwargs["temperature"]
            if "top_p" in kwargs:
                request_data["top_p"] = kwargs["top_p"]

            logger.debug("Anthropic request: model=%s, messages=%d", self.model, len(anthropic_messages))

            response = await client.post("/messages", json=request_data)
            response.raise_for_status()
            data = response.json()

            return data["content"][0]["text"]

        except httpx.HTTPStatusError as e:
            logger.error("Anthropic API error: %s - %s", e.response.status_code, e.response.text)
            raise PluginError(f"Anthropic API error: {e.response.status_code}") from e
        except httpx.HTTPError as e:
            logger.error("Anthropic completion failed: %s", e)
            raise PluginError(f"Anthropic request failed: {e}") from e
        except (KeyError, IndexError) as e:
            logger.error("Anthropic response parsing error: %s", e)
            raise PluginError("Invalid response from Anthropic") from e
