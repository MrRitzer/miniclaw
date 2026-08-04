"""OpenAI provider plugin implementation."""

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


class OpenAIPlugin(BasePlugin):
    """OpenAI provider plugin for MiniClaw.

    Handles communication with OpenAI API (and compatible endpoints).
    """

    def __init__(self) -> None:
        """Initialize OpenAI plugin."""
        self.api_key: str = ""
        self.model: str = "gpt-4o-mini"
        self.base_url: str = "https://api.openai.com/v1"
        self._client: httpx.AsyncClient | None = None
        self._running: bool = False
        self._available_models: list[dict] = []

    @property
    def metadata(self) -> PluginMetadata:
        """Return plugin metadata."""
        return PluginMetadata(
            name="openai",
            version="0.1.0",
            plugin_type=PluginType.PROVIDER,
            description="OpenAI API provider plugin",
            author="MiniClaw",
        )

    def initialize(self, config: dict[str, Any]) -> None:
        """Initialize the OpenAI plugin."""
        api_key = config.get("api_key")
        if not api_key:
            raise PluginError("OpenAI api_key is required")

        self.api_key = api_key
        self.model = config.get("model", "gpt-4o-mini")
        self.base_url = config.get("base_url", "https://api.openai.com/v1")
        self._client = None
        self._running = False
        logger.info("OpenAI plugin initialized with model: %s", self.model)

    async def _ensure_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=60.0,
            )
        return self._client

    async def list_models(self) -> list[dict[str, Any]]:
        """List available models from OpenAI API."""
        try:
            client = await self._ensure_client()
            response = await client.get("/models")
            response.raise_for_status()
            data = response.json()

            models = [
                {"id": m["id"], "owned_by": m.get("owned_by", "unknown")}
                for m in data.get("data", [])
                if "gpt" in m["id"].lower() or "o1" in m["id"].lower()
            ]

            self._available_models = models
            logger.info("Listed %d OpenAI models", len(models))
            return models

        except httpx.HTTPError as e:
            logger.error("Failed to list OpenAI models: %s", e)
            return []

    async def get_model(self, model_id: str) -> dict[str, Any] | None:
        """Get details for a specific model."""
        try:
            client = await self._ensure_client()
            response = await client.get(f"/models/{model_id}")
            response.raise_for_status()
            return response.json()

        except httpx.HTTPError as e:
            logger.error("Failed to get model %s: %s", model_id, e)
            return None

    def start(self) -> None:
        """Start the OpenAI provider."""
        if self._running:
            return

        self._running = True
        logger.info("OpenAI plugin started")

    async def stop(self) -> None:
        """Stop the OpenAI provider gracefully."""
        if not self._running:
            return

        if self._client:
            await self._client.aclose()
            self._client = None
        self._running = False
        logger.info("OpenAI plugin stopped")

    def health_check(self) -> bool:
        """Return True if OpenAI client is healthy."""
        return self._running

    async def complete(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> str:
        """Send a completion request to OpenAI.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            **kwargs: Additional parameters (temperature, max_tokens, etc.).

        Returns:
            Assistant's response text.

        Raises:
            PluginError: If the request fails.
        """
        if not self._running:
            raise PluginError("OpenAI plugin is not running")

        try:
            client = await self._ensure_client()

            request_data: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
            }

            if "temperature" in kwargs:
                request_data["temperature"] = kwargs["temperature"]
            if "max_tokens" in kwargs:
                request_data["max_tokens"] = kwargs["max_tokens"]
            if "top_p" in kwargs:
                request_data["top_p"] = kwargs["top_p"]

            logger.debug("OpenAI request: model=%s, messages=%d", self.model, len(messages))

            response = await client.post("/chat/completions", json=request_data)
            response.raise_for_status()
            data = response.json()

            return data["choices"][0]["message"]["content"]

        except httpx.HTTPStatusError as e:
            logger.error("OpenAI API error: %s - %s", e.response.status_code, e.response.text)
            raise PluginError(f"OpenAI API error: {e.response.status_code}") from e
        except httpx.HTTPError as e:
            logger.error("OpenAI completion failed: %s", e)
            raise PluginError(f"OpenAI request failed: {e}") from e
        except (KeyError, IndexError) as e:
            logger.error("OpenAI response parsing error: %s", e)
            raise PluginError("Invalid response from OpenAI") from e
