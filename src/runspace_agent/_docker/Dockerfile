# Build recipe for the runspace-agent:latest image.
#
# This Dockerfile is shipped inside the wheel (declared as package-data) so it
# travels with any install — editable, git, or wheel. It is NOT meant to be built
# from a repo checkout with `docker build .`; the build context is assembled at
# runtime by runspace_agent.cli (_prepare_build_context), which lays out:
#
#   ./requirements.txt      runtime deps (base + the [claude] extra)
#   ./runspace_agent/       the installed package source tree
#
# The image is built automatically by `runspace-srv --docker` (or `--rebuild`).
FROM python:3.11-slim

# System deps + Node.js (required for the Claude Code runtime)
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl jq && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI globally
RUN npm install -g @anthropic-ai/claude-code

# Install Python deps, then drop in the package source (PYTHONPATH instead of a
# pip install, so no pyproject.toml is needed in the build context)
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY runspace_agent/ ./runspace_agent/
ENV PYTHONPATH=/app

# Create non-root user (Claude Code refuses --dangerously-skip-permissions as root)
RUN useradd -m -s /bin/bash agent && \
    mkdir -p /workspace && chown agent:agent /workspace

USER agent
WORKDIR /workspace
ENTRYPOINT ["python", "-m", "runspace_agent.entrypoint"]
