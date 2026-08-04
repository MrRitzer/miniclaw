"""Heartbeat scheduler for MiniClaw.

Periodically wakes up to check for and execute tasks.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from miniclaw.agent import AgentProfileManager

logger = logging.getLogger(__name__)


@dataclass
class HeartbeatTask:
    """A task to execute during heartbeat."""

    description: str
    status: str = "pending"  # pending, running, completed, failed
    result: str = ""
    last_run: datetime | None = None


class HeartbeatManager:
    """Manages heartbeat scheduling and task execution.

    The heartbeat wakes up periodically to check for tasks
    and perform background work.
    """

    def __init__(
        self,
        agent_manager: AgentProfileManager,
        interval_minutes: int = 30,
    ) -> None:
        """Initialize heartbeat manager.

        Args:
            agent_manager: Agent profile manager for config and tasks.
            interval_minutes: Default interval if not in config.
        """
        self._agent_manager = agent_manager
        self._interval_minutes = interval_minutes
        self._running = False
        self._task: asyncio.Task | None = None
        self._on_task_callback: callable | None = None
        self._tasks: dict[str, HeartbeatTask] = {}

    @property
    def interval_minutes(self) -> int:
        """Get heartbeat interval from config or default."""
        if self._agent_manager.heartbeat.enabled:
            return self._agent_manager.heartbeat.interval_minutes
        return self._interval_minutes

    @property
    def is_enabled(self) -> bool:
        """Check if heartbeat is enabled."""
        return self._agent_manager.heartbeat.enabled

    def set_task_callback(self, callback: callable) -> None:
        """Set callback to be called when heartbeat fires.

        Args:
            callback: Async function(task_description: str) to call.
        """
        self._on_task_callback = callback

    def load_tasks_from_config(self) -> None:
        """Load tasks from heartbeat configuration."""
        self._tasks.clear()

        for i, task_desc in enumerate(self._agent_manager.heartbeat.tasks):
            task_id = f"task_{i}"
            self._tasks[task_id] = HeartbeatTask(description=task_desc)

        logger.info("Loaded %d heartbeat tasks", len(self._tasks))

    async def _run_heartbeat(self) -> None:
        """Run one heartbeat cycle."""
        logger.debug("Heartbeat firing...")

        # Reload profiles to check for new tasks
        self._agent_manager.reload()
        self.load_tasks_from_config()

        # Execute tasks
        for task_id, task in self._tasks.items():
            if task.status == "running":
                logger.warning("Task %s still running, skipping", task_id)
                continue

            if task.status == "completed" and self._agent_manager.heartbeat.silent_on_success:
                continue

            logger.info("Executing heartbeat task: %s", task.description)
            task.status = "running"
            task.last_run = datetime.utcnow()

            try:
                if self._on_task_callback:
                    result = await self._on_task_callback(task.description)
                    task.result = result if result else "completed"
                    task.status = "completed"
                else:
                    task.status = "completed"
                    task.result = "No callback configured"
            except Exception as e:
                logger.error("Heartbeat task failed: %s", e)
                task.status = "failed"
                task.result = str(e)

        logger.debug("Heartbeat cycle complete")

    async def _heartbeat_loop(self) -> None:
        """Main heartbeat loop."""
        while self._running:
            try:
                # Calculate next run time
                interval = self.interval_minutes
                next_run = datetime.utcnow() + timedelta(minutes=interval)

                logger.debug("Next heartbeat in %d minutes", interval)

                # Wait for interval
                await asyncio.sleep(interval * 60)

                if not self._running:
                    break

                # Run heartbeat
                await self._run_heartbeat()

            except asyncio.CancelledError:
                logger.info("Heartbeat loop cancelled")
                break
            except Exception as e:
                logger.error("Heartbeat loop error: %s", e)
                # Wait a bit before retrying
                await asyncio.sleep(60)

    def start(self) -> None:
        """Start the heartbeat scheduler."""
        if self._running:
            return

        if not self.is_enabled:
            logger.info("Heartbeat is disabled")
            return

        self._running = True
        self._task = asyncio.create_task(self._heartbeat_loop())
        logger.info("Heartbeat scheduler started (interval: %d min)", self.interval_minutes)

    async def stop(self) -> None:
        """Stop the heartbeat scheduler."""
        if not self._running:
            return

        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        logger.info("Heartbeat scheduler stopped")

    async def trigger_now(self) -> None:
        """Trigger an immediate heartbeat.

        This is useful for manual triggers (e.g., via Telegram command).
        """
        if not self._running:
            logger.warning("Heartbeat not running, triggering anyway")
            await self._run_heartbeat()
        else:
            # Run inline without waiting
            asyncio.create_task(self._run_heartbeat())

    def get_task_status(self) -> list[dict]:
        """Get status of all heartbeat tasks.

        Returns:
            List of task status dicts.
        """
        return [
            {
                "id": task_id,
                "description": task.description,
                "status": task.status,
                "last_run": task.last_run.isoformat() if task.last_run else None,
                "result": task.result,
            }
            for task_id, task in self._tasks.items()
        ]
