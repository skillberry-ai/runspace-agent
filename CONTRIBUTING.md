# Contributing to runspace_agent

Thanks for your interest in improving `runspace_agent`. This guide covers the
local setup, how to run the checks, and the conventions we follow.

## Development setup

Requires **Python 3.11+** and the [uv](https://docs.astral.sh/uv/) package
manager (Node.js 18+ only if you touch the frontend).

```bash
# Create and activate a virtual environment
uv venv --python 3.11
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install the package with all extras plus the dev tooling
uv pip install -e ".[all,dev]"
```

## Running the checks

All changes should pass linting, formatting, and the test suite before they are
committed.

```bash
# Lint
ruff check src tests

# Auto-fix what can be fixed, then format
ruff check src tests --fix
ruff format src tests

# Tests
pytest
```

The ruff configuration lives in [pyproject.toml](pyproject.toml) under
`[tool.ruff]` (target Python 3.11, line length 100). The full test suite should
be green — if you change a public interface, update the affected tests in the
same change.

## Conventions

- **Small, self-contained commits.** Each commit should do one thing and leave
  the tree in a working state (tests green, lint clean).
- **Match the surrounding code** — naming, docstring style, and comment density.
- New agent backends plug in through the `FilesystemAgent` protocol and the
  registry in [src/runspace_agent/agents/__init__.py](src/runspace_agent/agents/__init__.py);
  see the step-by-step guide in the `FilesystemAgent` docstring
  ([src/runspace_agent/agents/base.py](src/runspace_agent/agents/base.py)).
- For a map of how the pieces fit together, see
  [docs/architecture.md](docs/architecture.md).

## Architecture

See [docs/architecture.md](docs/architecture.md) for an overview of the modules
and how a run flows through them.

## License

By contributing, you agree that your contributions are licensed under the
[Apache License 2.0](LICENSE.txt).
