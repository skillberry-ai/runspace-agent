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
# The heavy, slow-changing layers (Python + Node.js + Claude Code CLI + uv + the
# non-root user) live in the published base image below, built via
# scripts/publish-base-image.sh. This image only layers Python deps + the package
# source on top, so local builds are fast and avoid apt/npm registry rate limits.
#
# The image is built automatically by `runspace-srv` (or `--rebuild`).
FROM ghcr.io/skillberry-ai/runspace-agent-base:py3.11-node20

# Install Python deps with uv (provided by the base image), then drop in the
# package source (PYTHONPATH instead of a pip install, so no pyproject.toml is
# needed in the build context)
WORKDIR /app
COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt
COPY runspace_agent/ ./runspace_agent/
ENV PYTHONPATH=/app

# The 'agent' user and /workspace are created in the base image.
USER agent
WORKDIR /workspace
ENTRYPOINT ["python", "-m", "runspace_agent.entrypoint"]
