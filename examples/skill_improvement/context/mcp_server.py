"""MCP server that validates the CSV analyzer script against test cases."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("csv-validator")

TEST_CASES = [
    {
        "name": "utf8_encoding",
        "description": "CSV with UTF-8 characters (German umlauts)",
        "csv": "name,price\nBrötchen,1.50\nKäse,4.99\nMüsli,3.49\n",
        "checks": [
            {"type": "no_error"},
            {"type": "row_count", "expected": 3},
        ],
    },
    {
        "name": "missing_values_per_column",
        "description": "CSV with missing values — must not drop entire rows",
        "csv": "age,score\n25,80\n30,\n,90\n40,70\n",
        "checks": [
            {"type": "no_error"},
            {"type": "row_count_gte", "min": 3},
        ],
    },
    {
        "name": "median_calculation",
        "description": "Numeric column must include median statistic",
        "csv": "value\n10\n20\n30\n40\n50\n",
        "checks": [
            {"type": "no_error"},
            {"type": "has_stat", "column": "value", "stat": "median", "expected": "30"},
        ],
    },
    {
        "name": "string_column_stats",
        "description": "String columns must report unique count and most frequent value",
        "csv": "color\nred\nblue\nred\ngreen\nred\n",
        "checks": [
            {"type": "no_error"},
            {"type": "has_stat", "column": "color", "stat": "unique", "expected": "3"},
            {"type": "has_stat", "column": "color", "stat": "most_frequent", "expected": "red"},
        ],
    },
]


def _parse_output(stdout: str) -> dict:
    """Parse the text output of analyze.py into a structured dict."""
    result: dict = {"_raw": stdout, "columns": {}}
    current_col = None
    for line in stdout.splitlines():
        line = line.rstrip()
        if line.startswith("Total rows:"):
            result["total_rows"] = int(line.split(":", 1)[1].strip())
        elif line.startswith("Total columns:"):
            result["total_columns"] = int(line.split(":", 1)[1].strip())
        elif line and not line.startswith(" ") and line.endswith(":"):
            current_col = line[:-1].strip()
            result["columns"][current_col] = {}
        elif current_col and ":" in line:
            key, val = line.strip().split(":", 1)
            result["columns"][current_col][key.strip()] = val.strip()
    return result


def _run_check(check: dict, stdout: str, stderr: str, returncode: int, parsed: dict) -> dict:
    """Run a single check and return {passed, detail}."""
    ctype = check["type"]

    if ctype == "no_error":
        if returncode != 0:
            return {"passed": False, "detail": f"Script exited with code {returncode}: {stderr.strip()[:200]}"}
        if stdout.startswith("ERROR:"):
            return {"passed": False, "detail": f"Script output starts with ERROR: {stdout[:200]}"}
        return {"passed": True, "detail": "No error"}

    if ctype == "row_count":
        expected = check["expected"]
        actual = parsed.get("total_rows")
        ok = actual == expected
        return {"passed": ok, "detail": f"Expected {expected} rows, got {actual}"}

    if ctype == "row_count_gte":
        minimum = check["min"]
        actual = parsed.get("total_rows")
        if actual is None:
            return {"passed": False, "detail": "Could not find total_rows in output"}
        ok = actual >= minimum
        return {"passed": ok, "detail": f"Expected >= {minimum} rows, got {actual}"}

    if ctype == "has_stat":
        col = check["column"]
        stat = check["stat"]
        expected = check["expected"]
        col_stats = parsed.get("columns", {}).get(col, {})
        actual = col_stats.get(stat)
        if actual is None:
            return {"passed": False, "detail": f"Column '{col}' missing stat '{stat}'. Available: {list(col_stats.keys())}"}
        ok = str(actual).lower().strip() == str(expected).lower().strip()
        return {"passed": ok, "detail": f"'{col}.{stat}': expected '{expected}', got '{actual}'"}

    return {"passed": False, "detail": f"Unknown check type: {ctype}"}


@mcp.tool()
def validate_csv_analyzer(script_path: str) -> str:
    """Validate the CSV analyzer script against 4 test cases.

    Runs the script against test CSVs covering:
    1. UTF-8 encoding support
    2. Missing value handling (per-column, not dropping rows)
    3. Median calculation for numeric columns
    4. String column statistics (unique count, most frequent)

    Args:
        script_path: Absolute path to the analyze.py script to test.

    Returns:
        JSON report with pass/fail for each test case.
    """
    all_results = []

    for tc in TEST_CASES:
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8")
        tmp.write(tc["csv"])
        tmp.flush()
        tmp.close()

        try:
            proc = subprocess.run(
                [sys.executable, script_path, tmp.name],
                capture_output=True, text=True, timeout=15,
            )
        except subprocess.TimeoutExpired:
            all_results.append({"test": tc["name"], "passed": False, "checks": [{"passed": False, "detail": "Timed out after 15s"}]})
            Path(tmp.name).unlink(missing_ok=True)
            continue

        parsed = _parse_output(proc.stdout) if proc.returncode == 0 else {}
        check_results = [_run_check(c, proc.stdout, proc.stderr, proc.returncode, parsed) for c in tc["checks"]]
        test_passed = all(c["passed"] for c in check_results)

        all_results.append({
            "test": tc["name"],
            "description": tc["description"],
            "passed": test_passed,
            "checks": check_results,
        })
        Path(tmp.name).unlink(missing_ok=True)

    passed = sum(1 for r in all_results if r["passed"])
    return json.dumps({
        "summary": f"{passed}/{len(all_results)} tests passed",
        "all_passed": passed == len(all_results),
        "tests": all_results,
    }, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
