#!/bin/bash
set -e

# Authenticate gh CLI with the GitHub token
gh auth login --with-token <<< "$MINICLAW_GITHUB_TOKEN"

# Start the application
exec poetry run python -m miniclaw.main
