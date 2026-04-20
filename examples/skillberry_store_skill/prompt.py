import json


def build_prompt(tasks: list[dict]) -> str:
    """Build the optimization prompt for the given task(s).

    Args:
        tasks: List of task dicts (each must have at least "id" and "evaluation_criteria").
              These are entries from tasks.json.
    """
    task_ids = ", ".join(t["id"] for t in tasks)
    tasks_json = json.dumps(tasks, indent=2)

    return f"""
When we write context/ it means the context dir.

Please see the trajectories dir under: context/traces.
It contains successful or failed runs (probably both, sometimes only one type).
See the rewards in the trace file for each trajectory!

The reward is based on final database hash check only (and in some tasks there are required outputs),
meaning, Default reward_basis -> [RewardType.DB, RewardType.COMMUNICATE]
See file: context/evaluator.py
So we can modify tools names etc, without harming the reward.

Here are the tasks we optimize the Anthropic/MCP skill for (it contains the ground truth evaluation,
so learn it and use it to correct the agent behavior):
{tasks_json}

(Full tasks.json for reference if you want to look at other tasks:
context/tasks.json)

It's an experiment — you can modify the Anthropic skill for the tau agent.
You can modify it by updating tools that need fixes or might have bugs,
adding better tools (maybe composites of existing tools),
modifying existing ones, and everything so that we get higher rewards more frequently!
(See traces and why the agent is not getting the highest reward all the time.)


=== SKILLBERRY STORE ANTHROPIC SKILL FORMAT ===

The editable directory is an Anthropic skill that will be imported back into the
Skillberry Store after optimization. You MUST follow these rules so the skill
remains store-compatible:

WHAT THE IMPORTER DOES:
- Every file in the skill directory gets ingested — nothing is ignored.
- Files are classified by extension, NOT by directory name.

PYTHON FILES (.py) -> TOOLS:
- Each .py file is AST-parsed. Every top-level `def` function becomes a
  separate tool in the store.
- The function name becomes the tool name.
- The function's docstring becomes the tool description.
- Type annotations and docstring Args sections become the tool's parameter schema.
- If a .py file has no functions, the entire file becomes a single tool named
  after the filename.
- Adding a new top-level function = adding a new tool.
- Removing a function = removing a tool.
- Renaming a function = renaming a tool (the old one disappears, a new one appears).

NON-CODE FILES (.md, .txt, .json, etc.) -> SNIPPETS:
- All non-Python/non-Bash files become read-only snippets.
- SKILL.md body text (everything after the YAML frontmatter) also becomes a snippet.
- These are reference material, not executable.

SKILL.md FRONTMATTER RULES:
- Must start with a YAML frontmatter block (--- delimited).
- Required fields: `name` and `description`.
- `name` must be kebab-case, max 64 characters (e.g., "primitive-skill").
- `description` must be present, max 1024 characters.
- Do NOT add other frontmatter fields — only `name` and `description` are recognized.

WHAT YOU CAN CHANGE:
- Modify SKILL.md body (instructions, behavioral guidelines).
- Modify, add, or remove top-level functions in .py files under scripts/.
- Improve function docstrings to make tool descriptions clearer.
- Fix function signatures (parameters, types) to prevent agent errors.
- Add new .py files to scripts/ if a new tool would help.
- Update the SKILL.md frontmatter `name` to reflect your changes (e.g.,
  "primitive-skill-with-policy-guards"). The name must be kebab-case, max 64 chars.

=== CRITICAL: DO NOT TOUCH make_api_call.py ===
The file scripts/make_api_call.py is the runtime wiring to the tau2 environment.
Do NOT modify, rename, move, or delete it. It is correct as-is.

=== CRITICAL: PYTHON FILE FORMAT RULES ===
The Skillberry Store executes each .py file as a SELF-CONTAINED flat script.
There is NO Python module/package import system — no relative or cross-file imports work.

FORBIDDEN — NEVER add any of these lines to any .py file:
    from scripts.make_api_call import _make_api_call
    from scripts.<anything> import <anything>
    import scripts.<anything>
These WILL cause "No module named 'scripts.make_api_call'" at runtime and break the skill!

HOW IT WORKS:
- The store concatenates the ENTIRE .py file content into a single execution script.
- _make_api_call() is already available in the execution scope because the store
  injects make_api_call.py content before your code. You do NOT need to import it.
- Each .py file must be fully self-contained: only use stdlib imports and
  _make_api_call() (which is globally available at runtime).
- If you add a NEW .py file, every function in it that needs _make_api_call()
  can just call it directly — it is injected by the runtime.

OUTPUT FORMAT — PRESERVE THE INPUT STRUCTURE:
- Your output skill directory MUST have the same structure as the input.
- Every .py file that had functions calling _make_api_call() must STILL have
  those functions calling _make_api_call() the same way (no import line needed).
- Do NOT restructure or split files differently from the input unless you have
  a clear reason, and even then preserve the _make_api_call() calling convention.

WHAT TO BE CAREFUL ABOUT:
- Do NOT rename existing files unless you intentionally want to change tool/snippet
  identity — it breaks the round-trip mapping between import and export.
- Do NOT leave temporary files in the directory — they will be imported.
- Keep SKILL.md frontmatter valid at all times.
- Do NOT add any cross-file imports between scripts/ files.

BEFORE FINISHING:
- Run: python context/validate_skill.py <path-to-editable-dir>
  This validates the skill is store-compatible (checks SKILL.md frontmatter,
  Python files parse correctly, etc.).


=== YOUR OUTPUT ===

An optimized Anthropic skill/MCP to maximize reward on task(s) {task_ids},
while remaining sufficiently general to transfer to production and unseen tasks.

To write this file, you should:
1. Look at the ground truth evaluation_criteria / actions in the task JSON above to understand EXACTLY what the correct end-state of the database should be.
2. Analyze the SUCCESSFUL trajectories (if they exist) (reward=1.0) — understand what sequence of tool calls led to success and how to preserve that behavior.
3. Analyze the FAILED trajectories (if they exist) (reward=0.0) — understand WHERE and WHY the agent went wrong (wrong tool call, wrong arguments, unnecessary steps, policy violations, transferring to human, etc.)
4. Cluster the strengths and weaknesses you identified in the trajectories into
    - Strengths: what the agent is doing well that we want to preserve.
    - Weaknesses: what the agent is doing wrong that we want to fix.
5. Based on this analysis, optimize the tools in a generic way (not overfitting to these tasks, so we can generalize to production and to other tasks as well!):
   - Remove tools that are not necessary anymore (if other better tools can do the job).
   - Modify existing tools to add guardrails/checks that prevent the failure modes you identified.
   - Add new helper tools if they would simplify the agent's job (e.g., a tool that does multiple steps at once).
   - Make tool descriptions clearer so the agent picks the right tool and uses correct arguments.

"""
