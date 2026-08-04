"""Initialize skill for MiniClaw.

Guides the user through initial agent setup.
"""

import logging
from pathlib import Path
from typing import Any

from miniclaw.skills.base import (
    BaseSkill,
    SkillContext,
    SkillResult,
    SkillStatus,
)

logger = logging.getLogger(__name__)


class InitializeSkill(BaseSkill):
    """Skill to initialize the agent for first-time use.

    Checks if setup is complete, and if not, walks the user through:
    1. Setting agent name and description
    2. Setting user name and Telegram ID
    3. Configuring GitHub (optional)
    4. Setting up heartbeat tasks
    """

    def __init__(self, data_dir: Path | str) -> None:
        """Initialize the skill.

        Args:
            data_dir: Path to the agent data directory.
        """
        self._data_dir = Path(data_dir)
        self._state: dict[str, Any] = {}
        self._status = SkillStatus.PENDING

    @property
    def name(self) -> str:
        return "initialize"

    @property
    def description(self) -> str:
        return "Initialize or re-configure the agent"

    @property
    def triggers(self) -> list[str]:
        return ["/setup", "/reconfigure", "/initialize", "/config"]

    async def execute(self, context: SkillContext, force: bool = False) -> SkillResult:
        """Execute the initialize skill.

        Args:
            context: Skill context.
            force: If True, force reconfiguration even if setup is complete.

        Returns:
            SkillResult with setup instructions or completion status.
        """
        self._state = {}
        self._status = SkillStatus.RUNNING

        # Check if already set up (unless force is True)
        if not force and self._is_setup_complete():
            return SkillResult(
                success=True,
                message="✅ Agent is already configured! Use /reconfigure to change settings.",
            )

        # Start setup flow
        return await self._start_setup(context)

    async def _start_setup(self, context: SkillContext) -> SkillResult:
        """Start the interactive setup flow.

        Args:
            context: Skill context.

        Returns:
            SkillResult with first setup prompt.
        """
        self._status = SkillStatus.WAITING_FOR_INPUT
        self._state["step"] = 1

        setup_intro = """🚀 **Welcome to MiniClaw Setup!**

Let's get your agent configured. I'll ask you a few questions.

**Step 1 of 4: Agent Identity**

What would you like to name your agent? (e.g., "DevBot", "Claw", "Assistant")

Or say `skip` to use the default name."""

        return SkillResult(
            success=True,
            message=setup_intro,
            data={"next_step": "agent_name"},
        )

    async def handle_input(self, context: SkillContext, user_input: str) -> SkillResult:
        """Handle user input during setup.

        This is called by the main loop when the skill is waiting for input.

        Args:
            context: Skill context.
            user_input: User's response.

        Returns:
            SkillResult with next prompt or completion.
        """
        step = self._state.get("step", 1)
        user_input = user_input.strip()

        if user_input.lower() == "skip":
            user_input = ""

        if step == 1:
            return await self._handle_agent_name(context, user_input)
        elif step == 2:
            return await self._handle_agent_description(context, user_input)
        elif step == 3:
            return await self._handle_user_name(context, user_input)
        elif step == 4:
            return await self._handle_user_telegram(context, user_input)
        elif step == 5:
            return await self._handle_github(context, user_input)
        else:
            return await self._handle_heartbeat(context, user_input)

    async def _handle_agent_name(self, context: SkillContext, name: str) -> SkillResult:
        """Handle agent name input.

        Args:
            context: Skill context.
            name: Agent name input.

        Returns:
            Next step prompt.
        """
        if not name:
            name = "MiniClaw"

        self._state["agent_name"] = name
        self._state["step"] = 2

        return SkillResult(
            success=True,
            message=f"""✅ Agent name set to: **{name}**

**Step 2 of 4: Agent Description**

What should {name} do? (e.g., "A helpful coding assistant", "Project management bot")

Or `skip` to use the default.""",
            data={"next_step": "agent_description"},
        )

    async def _handle_agent_description(self, context: SkillContext, desc: str) -> SkillResult:
        """Handle agent description input.

        Args:
            context: Skill context.
            desc: Description input.

        Returns:
            Next step prompt.
        """
        if not desc:
            desc = "A helpful AI assistant"

        self._state["agent_description"] = desc
        self._state["step"] = 3

        return SkillResult(
            success=True,
            message=f"""✅ Description set: **{desc}**

**Step 3 of 4: Your Name**

What should I call you?""",
            data={"next_step": "user_name"},
        )

    async def _handle_user_name(self, context: SkillContext, name: str) -> SkillResult:
        """Handle user name input.

        Args:
            context: Skill context.
            name: User name input.

        Returns:
            Next step prompt.
        """
        if not name:
            return SkillResult(
                success=False,
                message="❌ Please tell me your name so I can address you properly.",
            )

        self._state["user_name"] = name
        self._state["step"] = 4

        return SkillResult(
            success=True,
            message=f"""👋 Nice to meet you, **{name}**!

**Step 4 of 4: Telegram ID**

To receive direct messages, I need your Telegram chat ID.

You can find your ID by:
1. Messaging @userinfobot on Telegram
2. Or visiting https://t.me/userinfobot

Enter your Telegram ID (numbers only):""",
            data={"next_step": "user_telegram"},
        )

    async def _handle_user_telegram(self, context: SkillContext, telegram_id: str) -> SkillResult:
        """Handle Telegram ID input.

        Args:
            context: Skill context.
            telegram_id: Telegram ID input.

        Returns:
            Next step prompt.
        """
        # Try to parse as int
        try:
            tid = int(telegram_id.strip())
        except ValueError:
            return SkillResult(
                success=False,
                message="❌ Please enter a valid numeric Telegram ID.",
            )

        self._state["user_telegram_id"] = tid
        self._state["step"] = 5

        return SkillResult(
            success=True,
            message=f"""✅ Telegram ID set: **{tid}**

**Step 5 of 6: GitHub (Optional)**

Would you like me to watch GitHub repositories for you?

Enter your GitHub username, or `skip` to skip this step.""",
            data={"next_step": "github"},
        )

    async def _handle_github(self, context: SkillContext, github: str) -> SkillResult:
        """Handle GitHub username input.

        Args:
            context: Skill context.
            github: GitHub username input.

        Returns:
            Next step prompt.
        """
        if github.lower() != "skip":
            self._state["github_username"] = github.strip()
            message = f"""✅ GitHub username set: **{github}**

**Step 6 of 6: Heartbeat Tasks**

What tasks should I perform during heartbeat checks?

Enter tasks separated by new lines, or `skip` to leave empty.

Examples:
- Check for new GitHub notifications
- Review project status
- Remind about deadlines"""
        else:
            self._state["github_username"] = ""
            message = """✅ GitHub step skipped.

**Step 6 of 6: Heartbeat Tasks**

What tasks should I perform during heartbeat checks?

Enter tasks separated by new lines, or `skip` to leave empty.

Examples:
- Check for new GitHub notifications
- Review project status
- Remind about deadlines"""

        self._state["step"] = 6

        return SkillResult(
            success=True,
            message=message,
            data={"next_step": "heartbeat_tasks"},
        )

    async def _handle_heartbeat(self, context: SkillContext, tasks: str) -> SkillResult:
        """Handle heartbeat tasks input and complete setup.

        Args:
            context: Skill context.
            tasks: Heartbeat tasks input.

        Returns:
            Setup completion.
        """
        if tasks.lower() != "skip":
            task_list = [t.strip() for t in tasks.split("\n") if t.strip()]
        else:
            task_list = []

        self._state["heartbeat_tasks"] = task_list

        # Write all the files
        await self._write_config_files()

        self._status = SkillStatus.COMPLETED

        return SkillResult(
            success=True,
            message=f"""🎉 **Setup Complete!**

Your MiniClaw agent is configured:

• **Agent Name:** {self._state.get('agent_name', 'MiniClaw')}
• **Description:** {self._state.get('agent_description', 'A helpful AI assistant')}
• **Your Name:** {self._state.get('user_name', 'User')}
• **Telegram ID:** {self._state.get('user_telegram_id', 'Not set')}
• **GitHub:** {self._state.get('github_username', 'Not configured')}
• **Heartbeat Tasks:** {len(task_list)} task(s) configured

Use /status to check agent status.
Use /reconfigure to change settings.""",
        )

    async def _write_config_files(self) -> None:
        """Write all configuration files after setup."""
        data_dir = self._data_dir
        data_dir.mkdir(parents=True, exist_ok=True)

        # Write agent.md
        agent_content = f"""# Agent Profile

name:: {self._state.get('agent_name', 'MiniClaw')}
description:: {self._state.get('agent_description', 'A helpful AI assistant')}
instructions::
model_preference:: openai
heartbeat_enabled:: true
heartbeat_interval:: 30
setup_complete:: true
"""
        (data_dir / "agent.md").write_text(agent_content)

        # Write user.md
        user_content = f"""# User Profile

name:: {self._state.get('user_name', 'User')}
telegram_id:: {self._state.get('user_telegram_id', 0)}
github_username:: {self._state.get('github_username', '')}
email::
setup_complete:: true
"""
        (data_dir / "user.md").write_text(user_content)

        # Write heartbeat.md
        tasks_content = "\n".join(f"- {t}" for t in self._state.get("heartbeat_tasks", []))
        heartbeat_content = f"""# Heartbeat Configuration

enabled:: true
interval:: 30
silent_on_success:: true
setup_complete:: true

## Tasks

{tasks_content}
"""
        (data_dir / "heartbeat.md").write_text(heartbeat_content)

        # Update memories.md
        memories_content = """# Memories

setup_complete:: true

## Facts

## Projects

## Notes

"""
        (data_dir / "memories.md").write_text(memories_content)

        logger.info("Configuration files written to %s", data_dir)

    def _is_setup_complete(self) -> bool:
        """Check if the agent has been set up.

        Returns:
            True if setup is complete.
        """
        agent_file = self._data_dir / "agent.md"
        if not agent_file.exists():
            return False

        content = agent_file.read_text()
        # Check for setup_complete flag
        for line in content.split("\n"):
            if line.strip().startswith("setup_complete::"):
                value = line.split("::", 1)[1].strip().lower()
                return value == "true"

        # Fallback: check if name is still the default/placeholder
        for line in content.split("\n"):
            if line.strip().startswith("name::"):
                value = line.split("::", 1)[1].strip()
                # If name is empty or still "MiniClaw" default, not setup
                if not value or value == "MiniClaw":
                    return False

        return True

    @property
    def is_waiting_for_input(self) -> bool:
        """Return True if skill is waiting for user input."""
        return self._status == SkillStatus.WAITING_FOR_INPUT

    def get_status(self) -> SkillStatus:
        """Get current skill status."""
        return self._status
