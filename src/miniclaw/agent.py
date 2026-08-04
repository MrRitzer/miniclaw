"""Agent profile management for MiniClaw.

Loads and manages agent and user profiles from data/agent/ directory.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AgentProfile:
    """Profile defining who the agent is."""

    name: str = "MiniClaw"
    description: str = "A helpful AI assistant"
    instructions: str = ""
    model_preference: str = "openai"
    heartbeat_enabled: bool = True
    heartbeat_interval: int = 30
    setup_complete: bool = False


@dataclass
class UserProfile:
    """Profile defining who the user is."""

    name: str = "User"
    telegram_id: int = 0
    github_username: str = ""
    email: str = ""
    setup_complete: bool = False


@dataclass
class HeartbeatConfig:
    """Configuration for heartbeat behavior."""

    enabled: bool = True
    interval_minutes: int = 30
    tasks: list[str] = field(default_factory=list)
    silent_on_success: bool = True
    setup_complete: bool = False


@dataclass
class Memories:
    """Important memories and context."""

    facts: list[str] = field(default_factory=list)
    projects: list[str] = field(default_factory=list)
    notes: str = ""
    setup_complete: bool = False


class AgentProfileError(Exception):
    """Raised when agent profile operations fail."""

    pass


class AgentProfileManager:
    """Manages agent profile files in data/agent/ directory."""

    def __init__(self, data_dir: Path | str = "data/agent") -> None:
        """Initialize profile manager.

        Args:
            data_dir: Path to data directory containing profile files.
                      Defaults to data/agent/ relative to cwd.
        """
        self.data_dir = Path(data_dir)
        self._agent: AgentProfile | None = None
        self._user: UserProfile | None = None
        self._heartbeat: HeartbeatConfig | None = None
        self._memories: Memories | None = None

    def _read_file(self, filename: str) -> str:
        """Read a file from the data directory.

        Args:
            filename: Name of the file to read.

        Returns:
            File contents or empty string if not found.
        """
        file_path = self.data_dir / filename
        if not file_path.exists():
            logger.debug("Profile file not found: %s", file_path)
            return ""

        try:
            return file_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning("Failed to read %s: %s", file_path, e)
            return ""

    def _write_file(self, filename: str, content: str) -> None:
        """Write a file to the data directory.

        Args:
            filename: Name of the file to write.
            content: Content to write.
        """
        self.data_dir.mkdir(parents=True, exist_ok=True)
        file_path = self.data_dir / filename

        try:
            file_path.write_text(content, encoding="utf-8")
        except Exception as e:
            logger.error("Failed to write %s: %s", file_path, e)
            raise AgentProfileError(f"Failed to write {filename}: {e}") from e

    def load_profiles(self) -> None:
        """Load all profiles from the data directory."""
        self._load_agent_profile()
        self._load_user_profile()
        self._load_heartbeat_config()
        self._load_memories()

    def _load_agent_profile(self) -> None:
        """Load agent profile from agent.md file."""
        content = self._read_file("agent.md")

        self._agent = AgentProfile()

        for line in content.split("\n"):
            line = line.strip()
            if "::" in line:
                key, value = line.split("::", 1)
                key = key.strip().lower().replace("-", "_")
                value = value.strip()

                if key == "name":
                    self._agent.name = value
                elif key == "description":
                    self._agent.description = value
                elif key == "instructions":
                    self._agent.instructions = value
                elif key == "model_preference":
                    self._agent.model_preference = value
                elif key == "heartbeat_enabled":
                    self._agent.heartbeat_enabled = value.lower() in ("true", "1", "yes")
                elif key == "heartbeat_interval":
                    try:
                        self._agent.heartbeat_interval = int(value)
                    except ValueError:
                        pass
                elif key == "setup_complete":
                    self._agent.setup_complete = value.lower() in ("true", "1", "yes")

        logger.info("Loaded agent profile: %s", self._agent.name)

    def _load_user_profile(self) -> None:
        """Load user profile from user.md file."""
        content = self._read_file("user.md")

        self._user = UserProfile()

        for line in content.split("\n"):
            line = line.strip()
            if "::" in line:
                key, value = line.split("::", 1)
                key = key.strip().lower().replace("-", "_")
                value = value.strip()

                if key == "name":
                    self._user.name = value
                elif key == "telegram_id":
                    try:
                        self._user.telegram_id = int(value)
                    except ValueError:
                        pass
                elif key == "github_username":
                    self._user.github_username = value
                elif key == "email":
                    self._user.email = value
                elif key == "setup_complete":
                    self._user.setup_complete = value.lower() in ("true", "1", "yes")

        logger.info("Loaded user profile: %s", self._user.name)

    def _load_heartbeat_config(self) -> None:
        """Load heartbeat config from heartbeat.md file."""
        content = self._read_file("heartbeat.md")

        self._heartbeat = HeartbeatConfig()
        self._heartbeat.tasks = []

        in_tasks = False
        for line in content.split("\n"):
            line = line.strip()

            if line.lower().startswith("interval::"):
                value = line.split("::", 1)[1].strip()
                try:
                    self._heartbeat.interval_minutes = int(value)
                except ValueError:
                    pass

            elif line.lower().startswith("silent_on_success::"):
                value = line.split("::", 1)[1].strip()
                self._heartbeat.silent_on_success = value.lower() in ("true", "1", "yes")

            elif line.lower().startswith("enabled::"):
                value = line.split("::", 1)[1].strip()
                self._heartbeat.enabled = value.lower() in ("true", "1", "yes")

            elif line.lower().startswith("setup_complete::"):
                value = line.split("::", 1)[1].strip()
                self._heartbeat.setup_complete = value.lower() in ("true", "1", "yes")

            elif line.lower() == "## tasks":
                in_tasks = True

            elif in_tasks and line.startswith("- "):
                self._heartbeat.tasks.append(line[2:].strip())

        if self._heartbeat.enabled:
            logger.info(
                "Loaded heartbeat config: interval=%d min, tasks=%d",
                self._heartbeat.interval_minutes,
                len(self._heartbeat.tasks),
            )
        else:
            logger.info("Heartbeat disabled")

    def _load_memories(self) -> None:
        """Load memories from memories.md file."""
        content = self._read_file("memories.md")

        self._memories = Memories()
        current_section = None

        for line in content.split("\n"):
            line = line.strip()

            if line.lower() == "## facts":
                current_section = "facts"
            elif line.lower() == "## projects":
                current_section = "projects"
            elif line.lower() == "## notes":
                current_section = "notes"
            elif line.lower().startswith("setup_complete::"):
                value = line.split("::", 1)[1].strip()
                self._memories.setup_complete = value.lower() in ("true", "1", "yes")
            elif current_section == "facts" and line.startswith("- "):
                self._memories.facts.append(line[2:].strip())
            elif current_section == "projects" and line.startswith("- "):
                self._memories.projects.append(line[2:].strip())
            elif current_section == "notes":
                self._memories.notes += line + "\n"

        logger.info(
            "Loaded memories: %d facts, %d projects",
            len(self._memories.facts),
            len(self._memories.projects),
        )

    @property
    def agent(self) -> AgentProfile:
        """Get agent profile."""
        if self._agent is None:
            self.load_profiles()
        return self._agent or AgentProfile()

    @property
    def user(self) -> UserProfile:
        """Get user profile."""
        if self._user is None:
            self.load_profiles()
        return self._user or UserProfile()

    @property
    def heartbeat(self) -> HeartbeatConfig:
        """Get heartbeat config."""
        if self._heartbeat is None:
            self.load_profiles()
        return self._heartbeat or HeartbeatConfig()

    @property
    def memories(self) -> Memories:
        """Get memories."""
        if self._memories is None:
            self.load_profiles()
        return self._memories or Memories()

    @property
    def is_setup_complete(self) -> bool:
        """Check if the agent has been set up.

        Returns:
            True if all setup is complete.
        """
        return (
            self.agent.setup_complete
            and self.user.setup_complete
            and self.heartbeat.setup_complete
        )

    def reload(self) -> None:
        """Reload all profiles from disk."""
        self._agent = None
        self._user = None
        self._heartbeat = None
        self._memories = None
        self.load_profiles()

    def get_system_prompt(self) -> str:
        """Build system prompt from profiles and memories.

        Returns:
            Complete system prompt for AI.
        """
        parts = []

        # Agent identity
        parts.append(f"You are {self.agent.name}.")
        if self.agent.description:
            parts.append(self.agent.description)
        if self.agent.instructions:
            parts.append(f"\nInstructions:\n{self.agent.instructions}")

        # User context
        parts.append(f"\nThe user is {self.user.name}.")
        if self.user.github_username:
            parts.append(f"GitHub: {self.user.github_username}")

        # Memories
        if self.memories.facts:
            parts.append("\nImportant facts:")
            for fact in self.memories.facts:
                parts.append(f"- {fact}")

        if self.memories.projects:
            parts.append("\nCurrent projects:")
            for project in self.memories.projects:
                parts.append(f"- {project}")

        if self.memories.notes.strip():
            parts.append(f"\nNotes:\n{self.memories.notes.strip()}")

        return "\n".join(parts)
