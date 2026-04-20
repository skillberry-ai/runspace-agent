#!/usr/bin/env python3
"""Validate that an Anthropic skill directory is compatible with the Skillberry Store importer.

Checks:
  - SKILL.md exists with valid YAML frontmatter (name, description)
  - name is kebab-case, max 64 chars
  - description present, max 1024 chars, no angle brackets
  - Python files in scripts/ parse without syntax errors
  - No unexpected frontmatter keys

Usage:
    python validate_skill.py <skill_directory>
"""

import ast
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None


def _parse_yaml_frontmatter(text: str) -> dict | None:
    """Extract YAML frontmatter from --- delimited block."""
    if not text.startswith("---"):
        return None
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return None
    raw = match.group(1)
    if yaml is not None:
        return yaml.safe_load(raw)
    # Minimal fallback if PyYAML is not installed
    result = {}
    for line in raw.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            result[key.strip()] = value.strip()
    return result


def validate_skill(skill_path: Path) -> tuple[bool, list[str]]:
    """Validate the skill directory. Returns (ok, list_of_messages)."""
    errors: list[str] = []

    # --- SKILL.md ---
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return False, ["FAIL: SKILL.md not found in " + str(skill_path)]

    content = skill_md.read_text(encoding="utf-8")
    frontmatter = _parse_yaml_frontmatter(content)
    if frontmatter is None:
        errors.append(
            "FAIL: SKILL.md has no valid YAML frontmatter (--- delimited block)"
        )
    else:
        allowed_keys = {
            "name",
            "description",
            "license",
            "allowed-tools",
            "metadata",
            "compatibility",
        }
        unexpected = set(frontmatter.keys()) - allowed_keys
        if unexpected:
            errors.append(
                f"FAIL: Unexpected frontmatter keys: {', '.join(sorted(unexpected))}"
            )

        # name
        name = frontmatter.get("name", "")
        if not name:
            errors.append("FAIL: Missing 'name' in frontmatter")
        elif not isinstance(name, str):
            errors.append(f"FAIL: 'name' must be a string, got {type(name).__name__}")
        else:
            name = name.strip()
            if not re.match(r"^[a-z0-9-]+$", name):
                bad_chars = set(re.findall(r"[^a-z0-9-]", name))
                errors.append(
                    f"FAIL: name '{name}' must be kebab-case (lowercase, digits, hyphens only). "
                    f"Found invalid characters: {bad_chars}. "
                    f"Note: underscores are NOT allowed — use hyphens instead "
                    f"(e.g., 'my-skill' not 'my_skill')."
                )
            elif name.startswith("-") or name.endswith("-") or "--" in name:
                errors.append(
                    f"FAIL: name '{name}' cannot start/end with hyphen or have consecutive hyphens"
                )
            if len(name) < 3:
                errors.append(
                    f"FAIL: name '{name}' is too short ({len(name)} chars, min 3)"
                )
            if len(name) > 64:
                errors.append(f"FAIL: name is {len(name)} chars (max 64)")
            parts = name.split("-")
            if all(len(p) <= 1 for p in parts if p):
                errors.append(
                    f"FAIL: name '{name}' is not descriptive enough — "
                    f"use meaningful kebab-case words (e.g., 'primitive-skill-with-policy')"
                )

        # description
        desc = frontmatter.get("description", "")
        if not desc:
            errors.append("FAIL: Missing 'description' in frontmatter")
        elif not isinstance(desc, str):
            errors.append(
                f"FAIL: 'description' must be a string, got {type(desc).__name__}"
            )
        else:
            if "<" in desc or ">" in desc:
                errors.append(
                    "FAIL: description cannot contain angle brackets (< or >)"
                )
            if len(desc) > 1024:
                errors.append(f"FAIL: description is {len(desc)} chars (max 1024)")

    # --- Python files ---
    py_files = list(skill_path.rglob("*.py"))
    for py_file in py_files:
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError as e:
            errors.append(
                f"FAIL: Syntax error in {py_file.relative_to(skill_path)}: {e}"
            )
            continue

        rel = py_file.relative_to(skill_path)

        # Check for forbidden cross-file imports (scripts.* imports)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("scripts"):
                errors.append(
                    f"FAIL: Forbidden import in {rel} line {node.lineno}: "
                    f"'from {node.module} import ...' — the Skillberry Store "
                    f"does not support cross-file imports. _make_api_call() is "
                    f"injected by the runtime and must NOT be imported."
                )
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("scripts"):
                        errors.append(
                            f"FAIL: Forbidden import in {rel} line {node.lineno}: "
                            f"'import {alias.name}' — cross-file imports between "
                            f"scripts/ files are not supported by the store."
                        )

    # Check that make_api_call.py was not modified or deleted
    make_api_call = skill_path / "scripts" / "make_api_call.py"
    if not make_api_call.exists():
        errors.append(
            "FAIL: scripts/make_api_call.py is missing — this file must not be "
            "deleted or renamed. It provides the runtime API wiring."
        )

    # Count tools (top-level functions)
    tool_count = 0
    for py_file in py_files:
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source)
            funcs = [
                n for n in ast.iter_child_nodes(tree) if isinstance(n, ast.FunctionDef)
            ]
            if funcs:
                tool_count += len(funcs)
            else:
                tool_count += 1  # file-as-tool
        except SyntaxError:
            pass  # already reported

    # --- Summary ---
    messages = []
    if errors:
        messages.extend(errors)
    else:
        messages.append("PASS: Skill is store-compatible!")
        messages.append(
            f"  Name: {frontmatter.get('name', '?') if frontmatter else '?'}"
        )
        messages.append(f"  Python files: {len(py_files)}")
        messages.append(f"  Tools (top-level functions): {tool_count}")

    return len(errors) == 0, messages


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python validate_skill.py <skill_directory>")
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.is_dir():
        print(f"Error: '{path}' is not a directory")
        sys.exit(1)

    ok, messages = validate_skill(path)
    for msg in messages:
        print(msg)
    sys.exit(0 if ok else 1)
