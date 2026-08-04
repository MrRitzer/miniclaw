"""GitHub watcher for MiniClaw.

Monitors GitHub repositories for Issues and PRs.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class ActivityType(Enum):
    """Types of GitHub activity."""

    ISSUE_OPENED = "issue_opened"
    ISSUE_CLOSED = "issue_closed"
    ISSUE_COMMENT = "issue_comment"
    PR_OPENED = "pr_opened"
    PR_CLOSED = "pr_closed"
    PR_MERGED = "pr_merged"
    PR_COMMENT = "pr_comment"


@dataclass
class Repository:
    """A GitHub repository to watch."""

    owner: str
    repo: str

    def full_name(self) -> str:
        """Get full repository name (owner/repo)."""
        return f"{self.owner}/{self.repo}"


@dataclass
class Activity:
    """A GitHub activity event."""

    activity_type: ActivityType
    repo: str
    title: str
    number: int
    url: str
    actor: str
    created_at: datetime
    body: str = ""


class GitHubWatcher:
    """Watches GitHub repositories for activity.

    Monitors Issues and PRs and reports new activity.
    """

    def __init__(
        self,
        token: str | None = None,
        poll_interval_minutes: int = 5,
    ) -> None:
        """Initialize GitHub watcher.

        Args:
            token: GitHub personal access token for API access.
            poll_interval_minutes: How often to poll for new activity.
        """
        self._token = token
        self._poll_interval = poll_interval_minutes
        self._repos: list[Repository] = []
        self._running = False
        self._task: asyncio.Task | None = None
        self._last_check: datetime | None = None
        self._on_activity_callback: callable | None = None
        self._client: httpx.AsyncClient | None = None

        # Track seen activities to avoid duplicates
        self._seen_ids: set[str] = set()

    def add_repository(self, owner: str, repo: str) -> None:
        """Add a repository to watch.

        Args:
            owner: Repository owner.
            repo: Repository name.
        """
        self._repos.append(Repository(owner=owner, repo=repo))
        logger.info("Watching repository: %s/%s", owner, repo)

    def set_activity_callback(self, callback: callable) -> None:
        """Set callback to be called when activity is detected.

        Args:
            callback: Async function(activity: Activity) to call.
        """
        self._on_activity_callback = callback

    def _get_headers(self) -> dict[str, str]:
        """Get HTTP headers for GitHub API."""
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "MiniClaw/1.0",
        }
        if self._token:
            headers["Authorization"] = f"token {self._token}"
        return headers

    async def _fetch_issues(
        self,
        client: httpx.AsyncClient,
        repo: Repository,
        since: datetime | None,
    ) -> list[Activity]:
        """Fetch issues from a repository.

        Args:
            client: HTTP client.
            repo: Repository to fetch from.
            since: Only return issues updated after this time.

        Returns:
            List of issue activities.
        """
        activities = []

        try:
            params: dict[str, Any] = {"state": "all", "sort": "updated", "per_page": 30}
            if since:
                params["since"] = since.isoformat()

            response = await client.get(
                f"https://api.github.com/repos/{repo.full_name()}/issues",
                headers=self._get_headers(),
                params=params,
                timeout=30.0,
            )
            response.raise_for_status()
            issues = response.json()

            for issue in issues:
                # Skip pull requests (they appear in issues API too)
                if "pull_request" in issue:
                    continue

                created_at = datetime.fromisoformat(issue["created_at"].replace("Z", "+00:00"))
                updated_at = datetime.fromisoformat(issue["updated_at"].replace("Z", "+00:00"))

                # Skip if not updated since last check
                if since and updated_at < since:
                    continue

                activity_id = f"issue_{repo.full_name()}_{issue['number']}_{issue['updated_at']}"

                # Skip already seen
                if activity_id in self._seen_ids:
                    continue

                self._seen_ids.add(activity_id)

                activity_type = ActivityType.ISSUE_CLOSED if issue["state"] == "closed" else ActivityType.ISSUE_OPENED

                activities.append(
                    Activity(
                        activity_type=activity_type,
                        repo=repo.full_name(),
                        title=issue["title"],
                        number=issue["number"],
                        url=issue["html_url"],
                        actor=issue["user"]["login"],
                        created_at=created_at,
                        body=issue.get("body", "")[:500],  # First 500 chars
                    )
                )

        except httpx.HTTPError as e:
            logger.error("Failed to fetch issues for %s: %s", repo.full_name(), e)

        return activities

    async def _fetch_prs(
        self,
        client: httpx.AsyncClient,
        repo: Repository,
        since: datetime | None,
    ) -> list[Activity]:
        """Fetch pull requests from a repository.

        Args:
            client: HTTP client.
            repo: Repository to fetch from.
            since: Only return PRs updated after this time.

        Returns:
            List of PR activities.
        """
        activities = []

        try:
            params: dict[str, Any] = {"state": "all", "sort": "updated", "per_page": 30}
            if since:
                params["since"] = since.isoformat()

            response = await client.get(
                f"https://api.github.com/repos/{repo.full_name()}/pulls",
                headers=self._get_headers(),
                params=params,
                timeout=30.0,
            )
            response.raise_for_status()
            prs = response.json()

            for pr in prs:
                created_at = datetime.fromisoformat(pr["created_at"].replace("Z", "+00:00"))
                updated_at = datetime.fromisoformat(pr["updated_at"].replace("Z", "+00:00"))

                # Skip if not updated since last check
                if since and updated_at < since:
                    continue

                activity_id = f"pr_{repo.full_name()}_{pr['number']}_{pr['updated_at']}"

                # Skip already seen
                if activity_id in self._seen_ids:
                    continue

                self._seen_ids.add(activity_id)

                # Determine activity type
                if pr["merged"]:
                    activity_type = ActivityType.PR_MERGED
                elif pr["state"] == "closed":
                    activity_type = ActivityType.PR_CLOSED
                else:
                    activity_type = ActivityType.PR_OPENED

                activities.append(
                    Activity(
                        activity_type=activity_type,
                        repo=repo.full_name(),
                        title=pr["title"],
                        number=pr["number"],
                        url=pr["html_url"],
                        actor=pr["user"]["login"],
                        created_at=created_at,
                        body=pr.get("body", "")[:500],
                    )
                )

        except httpx.HTTPError as e:
            logger.error("Failed to fetch PRs for %s: %s", repo.full_name(), e)

        return activities

    async def _poll(self) -> None:
        """Poll all repositories for new activity."""
        if not self._repos:
            return

        self._client = httpx.AsyncClient(headers=self._get_headers())

        try:
            for repo in self._repos:
                # Fetch issues and PRs
                issue_activities = await self._fetch_issues(self._client, repo, self._last_check)
                pr_activities = await self._fetch_prs(self._client, repo, self._last_check)

                all_activities = issue_activities + pr_activities

                # Sort by creation time
                all_activities.sort(key=lambda a: a.created_at)

                # Notify callback
                for activity in all_activities:
                    if self._on_activity_callback:
                        try:
                            await self._on_activity_callback(activity)
                        except Exception as e:
                            logger.error("Activity callback failed: %s", e)

        finally:
            await self._client.aclose()
            self._client = None

        self._last_check = datetime.utcnow()

    async def _poll_loop(self) -> None:
        """Main polling loop."""
        while self._running:
            try:
                await self._poll()

                # Wait for next poll
                await asyncio.sleep(self._poll_interval * 60)

            except asyncio.CancelledError:
                logger.info("GitHub poll loop cancelled")
                break
            except Exception as e:
                logger.error("GitHub poll loop error: %s", e)
                await asyncio.sleep(60)

    def start(self) -> None:
        """Start watching repositories."""
        if self._running:
            return

        if not self._repos:
            logger.warning("No repositories configured for GitHub watcher")
            return

        self._running = True
        self._last_check = datetime.utcnow()
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("GitHub watcher started (polling every %d min)", self._poll_interval)

    async def stop(self) -> None:
        """Stop watching repositories."""
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

        if self._client:
            await self._client.aclose()
            self._client = None

        logger.info("GitHub watcher stopped")

    async def check_now(self) -> list[Activity]:
        """Check for new activity immediately.

        Returns:
            List of new activities found.
        """
        await self._poll()
        return []  # Activities are reported via callback

    def format_activity(self, activity: Activity) -> str:
        """Format an activity for display.

        Args:
            activity: Activity to format.

        Returns:
            Human-readable formatted string.
        """
        emoji = {
            ActivityType.ISSUE_OPENED: "🆕",
            ActivityType.ISSUE_CLOSED: "✅",
            ActivityType.ISSUE_COMMENT: "💬",
            ActivityType.PR_OPENED: "🔀",
            ActivityType.PR_CLOSED: "❌",
            ActivityType.PR_MERGED: "✅",
            ActivityType.PR_COMMENT: "💬",
        }.get(activity.activity_type, "📌")

        type_str = {
            ActivityType.ISSUE_OPENED: "New Issue",
            ActivityType.ISSUE_CLOSED: "Issue Closed",
            ActivityType.ISSUE_COMMENT: "Issue Comment",
            ActivityType.PR_OPENED: "New PR",
            ActivityType.PR_CLOSED: "PR Closed",
            ActivityType.PR_MERGED: "PR Merged",
            ActivityType.PR_COMMENT: "PR Comment",
        }.get(activity.activity_type, "Activity")

        return f"""{emoji} **{type_str}** in {activity.repo}
#{activity.number}: {activity.title}
By: @{activity.actor}
{activity.url}"""
