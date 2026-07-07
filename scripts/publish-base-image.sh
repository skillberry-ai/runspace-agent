#!/usr/bin/env bash
#
# Build and publish the multi-arch runspace-agent BASE image to GHCR.
#
# The base carries the slow-changing runtime layers (Python + Node.js + the
# Claude Code CLI + uv + the non-root user). The per-build runspace-agent image
# (built locally by `runspace-srv`) layers Python deps + package source on top
# of this, so end users never pay the apt/npm cost or hit registry rate limits.
#
# Run this ONLY when bumping Python, Node, the Claude Code CLI, or uv — not on
# every code change (the app source is layered on locally, not baked in here).
#
# Prerequisites:
#   1. Docker with buildx and a multi-arch builder:
#        docker buildx create --name runspace --use   # once
#   2. Logged in to GHCR with a token that has write:packages:
#        echo "$GITHUB_TOKEN" | docker login ghcr.io -u <github-username> --password-stdin
#
# Usage:
#   scripts/publish-base-image.sh            # build + push all tags
#   PLATFORMS=linux/amd64 scripts/publish-base-image.sh   # override platforms
set -euo pipefail

IMAGE="ghcr.io/skillberry-ai/runspace-agent-base"
TAG="${TAG:-py3.11-node20}"
PLATFORMS="${PLATFORMS:-linux/amd64,linux/arm64}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTEXT="$SCRIPT_DIR/../src/runspace_agent/_docker"
DOCKERFILE="$CONTEXT/Dockerfile.base"

# Immutable dated tag alongside the moving tag, so a bad push can be rolled back.
DATE_TAG="${TAG}-$(date +%Y-%m-%d)"

echo "Building ${IMAGE}"
echo "  tags:      ${TAG}, ${DATE_TAG}, latest"
echo "  platforms: ${PLATFORMS}"
echo "  file:      ${DOCKERFILE}"
echo

docker buildx build \
  --platform "$PLATFORMS" \
  --file "$DOCKERFILE" \
  --tag "${IMAGE}:${TAG}" \
  --tag "${IMAGE}:${DATE_TAG}" \
  --tag "${IMAGE}:latest" \
  --push \
  "$CONTEXT"

echo
echo "Published:"
echo "  ${IMAGE}:${TAG}"
echo "  ${IMAGE}:${DATE_TAG}"
echo "  ${IMAGE}:latest"
echo
echo "Note: make the package public at"
echo "  https://github.com/orgs/skillberry-ai/packages"
echo "so anonymous 'docker pull' works without a login."
