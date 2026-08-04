"""SQLite memory module for MiniClaw.

Provides persistent storage for conversation history and plugin data.
"""

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Generator


@dataclass
class Message:
    """A message in the conversation history."""

    id: int = 0
    role: str = ""  # "user", "assistant", "system"
    content: str = ""
    plugin: str = ""  # Which plugin created this (telegram, etc.)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


class MemoryError(Exception):
    """Base exception for memory errors."""

    pass


class DatabaseError(MemoryError):
    """Raised when database operations fail."""

    pass


class Memory:
    """SQLite-backed memory for MiniClaw.

    Stores conversation history and plugin-specific data.
    """

    def __init__(self, db_path: Path) -> None:
        """Initialize memory with database path.

        Args:
            db_path: Path to SQLite database file.
        """
        self.db_path = db_path
        self._ensure_db_dir()
        self._init_db()

    def _ensure_db_dir(self) -> None:
        """Ensure the database directory exists."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a database connection with row factory.

        Yields:
            sqlite3.Connection with Row factory enabled.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Messages table for conversation history
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    plugin TEXT NOT NULL DEFAULT '',
                    metadata TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                )
            """)

            # Plugin data table for plugin-specific storage
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS plugin_data (
                    key TEXT NOT NULL,
                    plugin TEXT NOT NULL,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (key, plugin)
                )
            """)

            # Index for faster message lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_created_at
                ON messages(created_at)
            """)

            conn.commit()

    def add_message(
        self,
        role: str,
        content: str,
        plugin: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """Add a message to conversation history.

        Args:
            role: Message role ("user", "assistant", "system").
            content: Message content.
            plugin: Plugin that created this message.
            metadata: Additional metadata as JSON.

        Returns:
            ID of the inserted message.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO messages (role, content, plugin, metadata, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    role,
                    content,
                    plugin,
                    json.dumps(metadata or {}),
                    datetime.utcnow().isoformat(),
                ),
            )
            conn.commit()
            return cursor.lastrowid or 0

    def get_messages(
        self,
        limit: int = 100,
        offset: int = 0,
        plugin: str | None = None,
    ) -> list[Message]:
        """Get recent messages from conversation history.

        Args:
            limit: Maximum number of messages to return.
            offset: Number of messages to skip.
            plugin: Filter by plugin (None for all).

        Returns:
            List of Message objects.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            if plugin:
                cursor.execute(
                    """
                    SELECT id, role, content, plugin, metadata, created_at
                    FROM messages
                    WHERE plugin = ?
                    ORDER BY created_at DESC, id DESC
                    LIMIT ? OFFSET ?
                    """,
                    (plugin, limit, offset),
                )
            else:
                cursor.execute(
                    """
                    SELECT id, role, content, plugin, metadata, created_at
                    FROM messages
                    ORDER BY created_at DESC, id DESC
                    LIMIT ? OFFSET ?
                    """,
                    (limit, offset),
                )

            rows = cursor.fetchall()
            messages = []
            for row in reversed(rows):  # Reverse to get chronological order
                messages.append(
                    Message(
                        id=row["id"],
                        role=row["role"],
                        content=row["content"],
                        plugin=row["plugin"],
                        metadata=json.loads(row["metadata"]),
                        created_at=datetime.fromisoformat(row["created_at"]),
                    )
                )
            return messages

    def clear_messages(self, plugin: str | None = None) -> int:
        """Clear messages from history.

        Args:
            plugin: Only clear messages from this plugin (None for all).

        Returns:
            Number of messages deleted.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            if plugin:
                cursor.execute(
                    "DELETE FROM messages WHERE plugin = ?",
                    (plugin,),
                )
            else:
                cursor.execute("DELETE FROM messages")

            conn.commit()
            return cursor.rowcount

    def set_plugin_data(self, key: str, plugin: str, value: Any) -> None:
        """Store plugin-specific data.

        Args:
            key: Data key (unique within plugin).
            plugin: Plugin name.
            value: Data to store (will be JSON serialized).
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO plugin_data (key, plugin, value, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (key, plugin, json.dumps(value), datetime.utcnow().isoformat()),
            )
            conn.commit()

    def get_plugin_data(
        self, key: str, plugin: str, default: Any = None
    ) -> Any:
        """Retrieve plugin-specific data.

        Args:
            key: Data key.
            plugin: Plugin name.
            default: Default value if key not found.

        Returns:
            Stored value or default.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT value FROM plugin_data
                WHERE key = ? AND plugin = ?
                """,
                (key, plugin),
            )
            row = cursor.fetchone()
            if row:
                return json.loads(row["value"])
            return default

    def delete_plugin_data(self, key: str, plugin: str) -> bool:
        """Delete plugin-specific data.

        Args:
            key: Data key.
            plugin: Plugin name.

        Returns:
            True if deleted, False if not found.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM plugin_data
                WHERE key = ? AND plugin = ?
                """,
                (key, plugin),
            )
            conn.commit()
            return cursor.rowcount > 0

    def close(self) -> None:
        """Close the database connection.

        Note: sqlite3 connections are closed automatically, but this
        method exists for API compatibility and explicit cleanup.
        """
        pass  # Connections are context-managed
