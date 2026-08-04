# MiniClaw

A lightweight, self-hosted gateway for connecting chat applications to AI coding agents.

## Overview

MiniClaw is a minimal alternative to [OpenClaw](https://docs.openclaw.ai/), designed for users who want a simple, self-hosted AI agent gateway without the overhead of a full Node.js runtime. It bridges messaging channels—Discord, Telegram, Slack, and more—directly to your preferred AI coding assistant, keeping your data under your control.

## Design Goals

- **Minimal dependencies** — Single binary, no runtime required
- **Low resource usage** — Runs on modest hardware; VPS-friendly
- **Simple configuration** — One config file, sensible defaults
- **Fast startup** — No package manager, no plugin registry to fetch

## Quick Start

```bash
# Install
curl -fsSL https://example.com/install.sh | sh

# Configure
miniclaw init
nano ~/.config/miniclaw/config.yaml

# Run
miniclaw start
```

## Supported Channels

- Discord
- Telegram
- Slack
- (More as the project grows)

## Architecture

```
Chat apps → MiniClaw Gateway → AI Agent (Claude, GPT, etc.)
```

## Use Cases

- Personal AI assistant accessible from any chat app
- Self-hosted alternative to cloud-based AI integrations
- Lightweight gateway for resource-constrained environments

## License

MIT
