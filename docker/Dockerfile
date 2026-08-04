FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"

# Copy project files
COPY pyproject.toml poetry.lock* ./
COPY src/ ./src/

# Install dependencies
RUN poetry install --no-root --no-interaction

# Create non-root user
RUN useradd -m -u 1000 miniclaw

# Create data/agent directory for agent profile (mounted from host)
RUN mkdir -p /data/agent && chown -R miniclaw:miniclaw /data

USER miniclaw

# Default command
CMD ["poetry", "run", "python", "-m", "miniclaw.main"]
