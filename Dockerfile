FROM python:3.11-slim

# Install system deps + Node.js (required for Claude Code runtime)
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl jq && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI globally
RUN npm install -g @anthropic-ai/claude-code

# Install the library
WORKDIR /app
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir ".[claude]"

# Create non-root user (Claude Code refuses --dangerously-skip-permissions as root)
RUN useradd -m -s /bin/bash agent

# Create workspace mount point owned by the agent user
RUN mkdir -p /workspace && chown agent:agent /workspace

USER agent
WORKDIR /workspace
ENTRYPOINT ["python", "-m", "runspace_agent.entrypoint"]
