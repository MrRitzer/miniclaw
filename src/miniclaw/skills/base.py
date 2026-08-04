"""Base skill interface for MiniClaw.

Skills are modular capabilities that the agent can perform.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable


class SkillStatus(Enum):
    """Status of a skill execution."""

    PENDING = auto()
    RUNNING = auto()
    WAITING_FOR_INPUT = auto()
    COMPLETED = auto()
    FAILED = auto()


@dataclass
class SkillContext:
    """Context passed to a skill during execution.

    Contains everything the skill needs to interact with the
    outside world (user, memory, plugins, etc).
    """

    user_id: int = 0  # Telegram chat ID
    session_id: str = ""
    agent_name: str = "MiniClaw"
    send_message: Callable[[str], None] = field(default=lambda msg: None)
    # Add more context as needed


@dataclass
class SkillResult:
    """Result of a skill execution."""

    success: bool
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)


class BaseSkill(ABC):
    """Base class for all MiniClaw skills.

    Skills are self-contained units of work that can be executed
    by the agent. They can be triggered automatically or by user command.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Skill name (unique identifier)."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what the skill does."""
        ...

    @property
    def triggers(self) -> list[str]:
        """List of commands or phrases that trigger this skill.

        Override to enable command-based triggering.
        """
        return []

    @abstractmethod
    async def execute(self, context: SkillContext) -> SkillResult:
        """Execute the skill.

        Args:
            context: Skill context with user info and callbacks.

        Returns:
            SkillResult indicating success/failure and message.
        """
        ...

    async def on_interrupt(self) -> None:
        """Called when skill is interrupted (e.g., user cancels).

        Override to clean up if needed.
        """
        pass


class SkillError(Exception):
    """Base exception for skill errors."""

    pass


class SkillExecutionError(SkillError):
    """Raised when skill execution fails."""

    pass
