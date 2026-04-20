"""Default constants for the ClaudeCodeAgent."""

DEFAULT_MAX_TURNS: int = 300

DEFAULT_ALLOWED_TOOLS: list[str] = [
    "Read",
    "Write",
    "Edit",
    "Bash",
    "Glob",
    "Grep",
    "Skill",
    "WebSearch",
    "WebFetch",
    "Agent",
    "LSP",
]

DEFAULT_DISALLOWED_TOOLS: list[str] = [
    "AskUserQuestion",
    "EnterPlanMode",
    "ExitPlanMode",
    "EnterWorktree",
    "ExitWorktree",
    "ScheduleWakeup",
    "CronCreate",
    "CronDelete",
    "CronList",
    "Monitor",
]

DEFAULT_SYSTEM_PROMPT: str = (
    "You are running headless in an automated pipeline. "
    "There is no human available to answer questions. "
    "Do NOT use AskHumanQuestion or any interactive prompts. "
    "Complete the task fully and autonomously. "
    "If you encounter ambiguity, make a reasonable decision and proceed."
)
