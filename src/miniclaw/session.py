"""Session management for MiniClaw.

Handles conversation sessions - create, save, resume, list.
"""

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Generator

from miniclaw.memory import Memory


@dataclass
class Message:
    """A message in a session."""

    role: str  # "user", "assistant", "system"
    content: str
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Session:
    """A conversation session."""

    id: str
    name: str
    messages: list[Message] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    is_active: bool = False


class SessionError(Exception):
    """Base exception for session errors."""

    pass


class SessionManager:
    """Manages conversation sessions in SQLite.

    Sessions store conversation history for later resume.
    """

    def __init__(self, memory: Memory) -> None:
        """Initialize session manager.

        Args:
            memory: Memory instance for database access.
        """
        self._memory = memory
        self._init_schema()

    def _init_schema(self) -> None:
        """Initialize session-specific schema."""
        with self._memory._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    messages TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 0
                )
            """)
            conn.commit()

    def create_session(self, name: str | None = None) -> Session:
        """Create a new session.

        Args:
            name: Optional session name. Defaults to timestamp.

        Returns:
            New session.
        """
        session_id = f"session_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        name = name or session_id
        now = datetime.utcnow()

        session = Session(
            id=session_id,
            name=name,
            messages=[],
            created_at=now,
            updated_at=now,
            is_active=True,
        )

        with self._memory._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO sessions (id, name, messages, created_at, updated_at, is_active)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (session.id, session.name, "[]", now.isoformat(), now.isoformat(), 1),
            )
            conn.commit()

        return session

    def save_session(self, session: Session) -> None:
        """Save or update a session.

        Args:
            session: Session to save.
        """
        session.updated_at = datetime.utcnow()
        messages_json = json.dumps(
            [
                {"role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}
                for m in session.messages
            ]
        )

        with self._memory._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO sessions (id, name, messages, created_at, updated_at, is_active)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session.id,
                    session.name,
                    messages_json,
                    session.created_at.isoformat(),
                    session.updated_at.isoformat(),
                    1 if session.is_active else 0,
                ),
            )
            conn.commit()

    def get_session(self, session_id: str) -> Session | None:
        """Get a session by ID.

        Args:
            session_id: Session ID.

        Returns:
            Session or None if not found.
        """
        with self._memory._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, name, messages, created_at, updated_at, is_active
                FROM sessions
                WHERE id = ?
                """,
                (session_id,),
            )
            row = cursor.fetchone()

            if not row:
                return None

            messages_data = json.loads(row["messages"])
            messages = [
                Message(
                    role=m["role"],
                    content=m["content"],
                    created_at=datetime.fromisoformat(m["created_at"]),
                )
                for m in messages_data
            ]

            return Session(
                id=row["id"],
                name=row["name"],
                messages=messages,
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
                is_active=bool(row["is_active"]),
            )

    def list_sessions(self, include_inactive: bool = False) -> list[Session]:
        """List all sessions.

        Args:
            include_inactive: Include inactive sessions.

        Returns:
            List of sessions.
        """
        with self._memory._get_connection() as conn:
            cursor = conn.cursor()

            if include_inactive:
                cursor.execute(
                    """
                    SELECT id, name, messages, created_at, updated_at, is_active
                    FROM sessions
                    ORDER BY updated_at DESC
                    """,
                )
            else:
                cursor.execute(
                    """
                    SELECT id, name, messages, created_at, updated_at, is_active
                    FROM sessions
                    WHERE is_active = 1
                    ORDER BY updated_at DESC
                    """,
                )

            rows = cursor.fetchall()
            sessions = []

            for row in rows:
                messages_data = json.loads(row["messages"])
                messages = [
                    Message(
                        role=m["role"],
                        content=m["content"],
                        created_at=datetime.fromisoformat(m["created_at"]),
                    )
                    for m in messages_data
                ]

                sessions.append(
                    Session(
                        id=row["id"],
                        name=row["name"],
                        messages=messages,
                        created_at=datetime.fromisoformat(row["created_at"]),
                        updated_at=datetime.fromisoformat(row["updated_at"]),
                        is_active=bool(row["is_active"]),
                    )
                )

            return sessions

    def delete_session(self, session_id: str) -> bool:
        """Delete a session.

        Args:
            session_id: Session ID.

        Returns:
            True if deleted, False if not found.
        """
        with self._memory._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM sessions WHERE id = ?",
                (session_id,),
            )
            conn.commit()
            return cursor.rowcount > 0

    def add_message(self, session_id: str, role: str, content: str) -> Message | None:
        """Add a message to a session.

        Args:
            session_id: Session ID.
            role: Message role ("user", "assistant", "system").
            content: Message content.

        Returns:
            Created message or None if session not found.
        """
        session = self.get_session(session_id)
        if not session:
            return None

        message = Message(role=role, content=content)
        session.messages.append(message)
        self.save_session(session)
        return message

    def get_active_session(self) -> Session | None:
        """Get the currently active session.

        Returns:
            Active session or None.
        """
        sessions = self.list_sessions(include_inactive=False)
        return sessions[0] if sessions else None

    def set_active_session(self, session_id: str) -> bool:
        """Set a session as active (deactivates all others).

        Args:
            session_id: Session ID to make active.

        Returns:
            True if successful, False if session not found.
        """
        with self._memory._get_connection() as conn:
            cursor = conn.cursor()

            # First check if session exists
            cursor.execute("SELECT id FROM sessions WHERE id = ?", (session_id,))
            if not cursor.fetchone():
                return False

            # Deactivate all sessions
            cursor.execute("UPDATE sessions SET is_active = 0")

            # Activate the target session
            cursor.execute(
                "UPDATE sessions SET is_active = 1 WHERE id = ?",
                (session_id,),
            )
            conn.commit()
            return True
