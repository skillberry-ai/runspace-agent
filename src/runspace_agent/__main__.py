"""Allow ``python -m runspace_agent`` as an alias for the ``runspace-srv`` CLI.

Handy when the console script isn't on PATH (e.g. a ``--user`` install whose
Scripts directory isn't exported), since ``python -m`` resolves through the
interpreter rather than PATH.
"""

from runspace_agent.cli import main

if __name__ == "__main__":
    main()
