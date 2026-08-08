#!/bin/bash
set -e

# Authenticate gh CLI with the GitHub token
gh auth setup-git

# Start the application
exec poetry run python -m miniclaw.main
