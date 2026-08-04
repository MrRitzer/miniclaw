# AGENTS.MD

MiniClaw agent instructions. Root rules only. Read scoped `AGENTS.md` before subtree work.

## Start

- Repo: MiniClaw — a lightweight, self-hosted personal AI agent gateway
- Language: Python 3.11+ with Poetry for dependency management
- Replies: repo-root refs only. No absolute paths, no `~/`.
- Docs: inline code documentation and `README.md` first.
- Existing-solutions preflight: before proposing or building a custom system, feature, workflow, tool, or integration, do a lightweight check for existing libraries or maintained packages that solve it well enough. Prefer those when adequate.
- Dependency-touching work: read upstream docs/source/types first. No API/default/error/timing guesses.
- External API work: live test where feasible. Prefer official docs/source; cite current proof.
- Missing deps: `poetry install`, retry once, then report first actionable error.
- Product/docs wording: "plugin/plugins"; channels and providers are plugins.
- New plugin surface: update `src/miniclaw/plugins/` structure.
- New `AGENTS.md`: add sibling `CLAUDE.md` symlink; edit `AGENTS.md` only.

## Architecture

### Core Principles

- Core stays plugin-agnostic. No bundled defaults/policy in core when manifest/registry/capability contracts work.
- Plugins cross into core only via documented interfaces in `src/miniclaw/plugins/`.
- Plugin prod code: no deep imports from other plugin internals.
- SQLite for persistent memory. Use `src/miniclaw/memory.py` helpers; do not bypass with JSON files.
- Config from environment variables and `.env` file. No hardcoded secrets.
- Channels (Telegram) and AI providers (OpenAI, Anthropic) are plugins.
- Lightweight plugin system: plugins register via a decorator or manifest, core discovers and loads them.

### Agent Profile System

- Each agent has a profile in `data/agent/` directory (container-local, NOT in repo).
- Profile files define who the agent is, who the user is, heartbeat config, and memories.
- Profile files: `agent.md`, `user.md`, `heartbeat.md`, `memories.md`.
- Agent reads profile on startup and periodically refreshes.
- Each profile file has a `setup_complete::` flag; if `false`, setup is required.

### Session System

- Sessions represent conversation contexts with a user.
- Each session has: ID, name, messages, created_at, updated_at.
- Sessions are stored in SQLite via `SessionManager`.
- Commands: start new session, save session, resume session, list sessions.

### Heartbeat System

- Agent wakes every 30 minutes (configurable) to check heartbeat file.
- Heartbeat file (`heartbeat.md`) defines tasks and configuration.
- Tasks are executed silently; results may be reported on Telegram.
- Immediate Telegram messages always take priority over heartbeat work.

### GitHub Integration

- Watches Issues and PRs in configured repositories.
- Can report new activity to the user via Telegram.
- Uses GitHub REST API v3.

### Skills System

- Skills are modular capabilities that the agent can perform.
- Skills are in `src/miniclaw/skills/` and implement `BaseSkill`.
- Skills can be triggered by commands or automatically.
- The `initialize` skill guides first-time setup via Telegram.
- Each skill has `name`, `description`, `triggers`, and `execute()` method.

## Commands

### Development

- Install: `poetry install`
- Run: `poetry run miniclaw` or `poetry run python -m miniclaw`
- Shell: `poetry shell`
- Add dependency: `poetry add <package>` or `poetry add --group <group> <package>`
- Dev dependencies: `poetry add --group dev <package>`
- Format: `poetry run black .` and `poetry run isort .`
- Lint: `poetry run ruff check .`
- Typecheck: `poetry run mypy .`
- Test: `poetry run pytest` or `poetry run pytest -v`
- Build: `poetry build`
- Docker: `docker build -t miniclaw .` and `docker run miniclaw`

### Telegram Bot Commands

- `/start` — Start the bot
- `/setup` — Run the interactive setup wizard (first-time only)
- `/models` — List available AI models
- `/new` — Start a new conversation session
- `/save <name>` — Save current session
- `/sessions` — List saved sessions
- `/resume <id>` — Resume a saved session
- `/heartbeat` — Trigger immediate heartbeat check
- `/status` — Show agent status

## Code

- Python 3.11+ only. Use type hints throughout.
- Style: Black formatter, isort for imports, Ruff for linting.
- No `@type: ignore` without explanation.
- External boundaries: prefer Pydantic or dataclasses for structured data.
- Runtime branching: use dataclasses with discriminated fields or enum-based state.
- Prefer early returns over nested condition pyramids.
- Lean code: no speculation, no "flexibility" not requested.
- Tests in `tests/` paralleling `src/` structure: `tests/plugins/test_telegram.py`.
- Test with pytest. Use fixtures for shared setup.
- Async/await for I/O operations (HTTP, SQLite via aiosqlite, Telegram polling).

## Tests

- Pytest. Colocated `test_*.py` or `*_test.py` files.
- Test where the bugs live: boundaries, not internals.
- Prefer invariant assertions over enumerating happy paths.
- Inject faults — network, provider errors — instead of asserting only success.
- Clean up fixtures: temp files, DB connections, mock patches.

## Git / Change Process

### Making Changes

1. **Fetch latest**: `git fetch origin`
2. **Create a branch**: `git checkout -b <branch-name>`
   - Branch naming: `feat/<description>`, `fix/<description>`, `docs/<description>`, `chore/<description>`
   - Example: `feat/telegram-plugin`, `fix/memory-leak`, `docs/update-readme`
3. **Make your changes** with descriptive commit messages
   - Commits: conventional commit style (`feat:`, `fix:`, `docs:`, `chore:`)
   - Write messages that explain *why*, not just *what*
4. **Update README** if your changes affect usage or setup
5. **Push**: `git push origin <branch-name>`
6. **Open a PR**: use the PR template, fill out all sections

### PR Requirements

- Fill out the PR template completely
- Link any related issues (`Fixes #123`)
- Ensure linting and tests pass locally before opening PR
- Address review feedback promptly

### Branch Maintenance

- Branch: `main` is protected; no force push.
- Delete merged branches locally and remotely.
- Sync feature branches to `main` before opening PR if `main` has advanced.

## Security

- Never commit secrets, credentials, or real API keys.
- Use environment variables for secrets: `.env` is gitignored.
- Validate external input; treat all plugin data as potentially untrusted.
- Docker: run as non-root user in containers.
- Agent profile in `data/agent/` is container-local and not persisted to repo.

## Map

```
src/miniclaw/          # Source code
  __init__.py          # Package init
  main.py              # Entry point
  config.py            # Configuration loading
  memory.py            # SQLite memory helpers
  agent.py             # Agent profile management
  session.py           # Session management
  heartbeat.py         # Heartbeat scheduler
  github.py            # GitHub watcher (Issues + PRs)
  skills/              # Skill system
    base.py            # BaseSkill interface
    initialize.py      # Setup wizard skill
  plugins/             # Plugin system
    base.py            # Base plugin interface
    registry.py        # Plugin discovery/registry
    telegram/          # Telegram channel plugin
    openai/            # OpenAI provider plugin
    anthropic/         # Anthropic provider plugin
tests/                 # Pytest tests
  plugins/
data/agent/            # Agent profile (container-local, NOT in repo)
  agent.md             # Who the agent is
  user.md              # Who the user is
  heartbeat.md         # Heartbeat configuration and tasks
  memories.md          # Important memories
docker/
  Dockerfile           # Container definition
pyproject.toml         # Poetry project config
poetry.lock            # Locked dependencies
.env.example           # Example environment variables
AGENTS.md              # This file
CLAUDE.md              # Symlink to AGENTS.md
```

## Environment Variables

Core environment variables (see `.env.example`):

- `MINICLAW_TELEGRAM_BOT_TOKEN` — Telegram bot token
- `MINICLAW_OPENAI_API_KEY` — OpenAI API key
- `MINICLAW_ANTHROPIC_API_KEY` — Anthropic API key
- `MINICLAW_DB_PATH` — SQLite database path (default: `~/.miniclaw/memory.db`)
- `MINICLAW_DATA_DIR` — Agent profile directory (default: `data/agent`)
- `MINICLAW_HEARTBEAT_INTERVAL` — Heartbeat interval in minutes (default: 30)
- `MINICLAW_GITHUB_TOKEN` — GitHub personal access token (optional)
- `MINICLAW_LOG_LEVEL` — Log level (default: `INFO`)

## Docker

- Build: `docker build -t miniclaw -f docker/Dockerfile .`
- Run: `docker run -v $(pwd)/data/agent:/data/agent -env-file .env miniclaw`
- `data/agent/` directory is mounted from host and contains agent profile files.
- Docker uses Poetry inside container; no runtime Poetry dependency on host.
