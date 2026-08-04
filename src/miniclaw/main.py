"""Main entry point for MiniClaw.

Run with: poetry run python -m miniclaw.main
"""

import asyncio
import logging
import os
import signal
from pathlib import Path

from miniclaw import __version__
from miniclaw.agent import AgentProfileManager
from miniclaw.config import get_plugin_config, load_config, load_miniclaw_config
from miniclaw.github import GitHubWatcher
from miniclaw.heartbeat import HeartbeatManager
from miniclaw.memory import Memory
from miniclaw.plugins.registry import PluginRegistry, registry
from miniclaw.session import SessionManager
from miniclaw.skills.base import SkillContext
from miniclaw.skills.initialize import InitializeSkill


def setup_logging(level: str = "INFO") -> None:
    """Configure logging for MiniClaw."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def load_plugins() -> None:
    """Load and register all plugins."""
    from miniclaw.plugins import telegram  # noqa: F401
    from miniclaw.plugins import openai  # noqa: F401
    from miniclaw.plugins import anthropic  # noqa: F401


# Global instances
memory: Memory | None = None
session_manager: SessionManager | None = None
agent_manager: AgentProfileManager | None = None
heartbeat_manager: HeartbeatManager | None = None
github_watcher: GitHubWatcher | None = None
telegram_plugin = None
initialize_skill: InitializeSkill | None = None


async def handle_telegram_message(message) -> str:
    """Handle an incoming Telegram message with AI.

    Args:
        message: TelegramMessage from the plugin.

    Returns:
        Response text to send back.
    """
    logger = logging.getLogger(__name__)

    # Check if setup is needed
    if not agent_manager.is_setup_complete:
        # Run initialize skill
        context = SkillContext(
            user_id=message.chat_id,
            session_id=session_manager.get_active_session().id if session_manager.get_active_session() else "",
        )

        # If initialize skill is waiting for input, handle it
        if initialize_skill and initialize_skill.is_waiting_for_input:
            result = await initialize_skill.handle_input(context, message.text)
            if result.message:
                return result.message
            return ""

        # Start setup
        result = await initialize_skill.execute(context)
        return result.message

    # Check for setup command even when setup is complete
    text_lower = message.text.strip().lower()
    if text_lower in ("/setup", "/reconfigure"):
        context = SkillContext(
            user_id=message.chat_id,
            session_id=session_manager.get_active_session().id if session_manager.get_active_session() else "",
        )
        force = text_lower == "/reconfigure"
        result = await initialize_skill.execute(context, force=force)
        return result.message

    # Get active session
    session = session_manager.get_active_session()
    if not session:
        session = session_manager.create_session()
        session_manager.set_active_session(session.id)

    # Add user message to session
    session_manager.add_message(session.id, "user", message.text)

    # Build messages for AI
    ai_messages = []

    # System prompt from agent profile
    system_prompt = agent_manager.get_system_prompt()
    ai_messages.append({"role": "system", "content": system_prompt})

    # Add conversation history
    for msg in session.messages:
        ai_messages.append({"role": msg.role, "content": msg.content})

    # Call AI provider
    provider_name = agent_manager.agent.model_preference
    try:
        if provider_name == "anthropic":
            provider = registry.get("anthropic")
            if provider and provider.health_check():
                response = await provider.complete(ai_messages)
            else:
                response = "❌ Anthropic provider not available. Check your API key."
        else:
            provider = registry.get("openai")
            if provider and provider.health_check():
                response = await provider.complete(ai_messages)
            else:
                response = "❌ OpenAI provider not available. Check your API key."

        # Add assistant response to session
        session_manager.add_message(session.id, "assistant", response)
        return response

    except Exception as e:
        logger.error("AI completion failed: %s", e)
        return f"Sorry, I encountered an error: {e}"


async def handle_heartbeat_task(task_description: str) -> str:
    """Handle a heartbeat task."""
    logger = logging.getLogger(__name__)
    logger.info("Executing heartbeat task: %s", task_description)

    # TODO: Implement actual task execution
    # For now, acknowledge the task
    return f"Heartbeat task completed: {task_description}"


async def handle_github_activity(activity) -> None:
    """Handle GitHub activity notification."""
    logger = logging.getLogger(__name__)
    logger.info("GitHub activity: %s %s #%d", activity.activity_type.value, activity.repo, activity.number)

    if telegram_plugin and telegram_plugin.health_check():
        formatted = github_watcher.format_activity(activity)
        logger.info("Would send to Telegram: %s", formatted[:100])


async def run_async() -> None:
    """Run MiniClaw asynchronously."""
    global memory, session_manager, agent_manager, heartbeat_manager
    global github_watcher, telegram_plugin, initialize_skill

    logger = logging.getLogger(__name__)
    logger.info("Starting MiniClaw v%s", __version__)

    # Load configuration
    config = load_miniclaw_config()
    setup_logging(config.log_level)

    # Load environment
    load_config()

    # Initialize memory
    memory = Memory(config.db_path)
    logger.info("Memory initialized at: %s", config.db_path)

    # Initialize session manager
    session_manager = SessionManager(memory)

    # Initialize agent profile manager
    data_dir = os.getenv("MINICLAW_DATA_DIR", "data/agent")
    agent_manager = AgentProfileManager(data_dir)
    agent_manager.load_profiles()
    logger.info("Agent profile loaded: %s", agent_manager.agent.name)
    logger.info("Setup complete: %s", agent_manager.is_setup_complete)

    # Initialize initialize skill
    initialize_skill = InitializeSkill(data_dir)

    # Load plugins
    load_plugins()
    logger.info("Plugins loaded: %s", [p.metadata.name for p in registry.list_plugins()])

    # Create and initialize plugins
    for plugin_meta in registry.list_plugins():
        name = plugin_meta.name
        plugin_config = get_plugin_config(name)

        # Skip if no credentials
        if not plugin_config.get("api_key") and not plugin_config.get("bot_token"):
            logger.warning("Skipping plugin %s: no credentials configured", name)
            continue

        try:
            plugin = registry.create(name, plugin_config)

            if name == "telegram":
                telegram_plugin = plugin
                plugin.set_session_manager(session_manager)
                plugin.set_message_callback(handle_telegram_message)
            elif name == "openai":
                plugin.start()
                await plugin.list_models()
            elif name == "anthropic":
                plugin.start()
                await plugin.list_models()

            logger.info("Plugin %s created and initialized", name)
        except Exception as e:
            logger.error("Failed to create plugin %s: %s", name, e)

    # Initialize heartbeat manager
    heartbeat_interval = int(os.getenv("MINICLAW_HEARTBEAT_INTERVAL", "30"))
    heartbeat_manager = HeartbeatManager(agent_manager, heartbeat_interval)
    heartbeat_manager.set_task_callback(handle_heartbeat_task)
    heartbeat_manager.load_tasks_from_config()

    # Initialize GitHub watcher (if token provided)
    github_token = os.getenv("MINICLAW_GITHUB_TOKEN")
    if github_token and agent_manager.user.github_username:
        github_watcher = GitHubWatcher(token=github_token)
        github_watcher.set_activity_callback(handle_github_activity)
        # TODO: Add repositories to watch from agent profile
    else:
        logger.info("GitHub watcher disabled (no token or username)")

    # Start all plugins
    try:
        registry.start_all()
        logger.info("All plugins started")
    except Exception as e:
        logger.error("Failed to start plugins: %s", e)
        registry.stop_all()
        return

    # Start heartbeat manager
    heartbeat_manager.start()

    # Start GitHub watcher
    if github_watcher and github_watcher._repos:
        github_watcher.start()

    if not agent_manager.is_setup_complete:
        logger.info("Setup not complete - user needs to run /setup on Telegram")

    logger.info("MiniClaw is running. Press Ctrl+C to stop.")

    # Run until interrupted
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        logger.info("Shutting down...")
    finally:
        if heartbeat_manager:
            await heartbeat_manager.stop()
        if github_watcher:
            await github_watcher.stop()
        registry.stop_all()
        if memory:
            memory.close()
        logger.info("MiniClaw stopped")


def run() -> None:
    """Run MiniClaw with signal handling."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def signal_handler(sig, frame):
        logger = logging.getLogger(__name__)
        logger.info("Received signal %d, shutting down...", sig)
        loop.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        loop.run_until_complete(run_async())
    finally:
        loop.close()


if __name__ == "__main__":
    run()
