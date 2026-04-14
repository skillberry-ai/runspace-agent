"""CSV analysis script — analyzes CSV files and generates summary statistics."""

import csv
import sys
from statistics import mean, stdev


def analyze_csv(filepath: str) -> dict:
    """Analyze a CSV file and return summary statistics."""
    try:
        with open(filepath, encoding="ascii") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except FileNotFoundError:
        return {"error": f"File not found: {filepath}"}
    except Exception as e:
        return {"error": f"Could not read file: {e}"}

    if not rows:
        return {"error": "No data found in the CSV file."}

    # Drop rows with any missing values
    clean_rows = []
    for row in rows:
        if all(v is not None and v.strip() != "" for v in row.values()):
            clean_rows.append(row)
    rows = clean_rows

    if not rows:
        return {"error": "No data remaining after removing rows with missing values."}

    columns = list(rows[0].keys())
    results = {"_summary": {"total_rows": len(rows), "columns": len(columns)}}

    for col in columns:
        values = [row[col].strip() for row in rows]

        # Try to parse as numeric
        numeric = []
        for v in values:
            try:
                numeric.append(float(v))
            except (ValueError, TypeError):
                numeric = []
                break

        if numeric:
            stats = {
                "type": "numeric",
                "count": len(numeric),
                "mean": round(mean(numeric), 2),
                "min": min(numeric),
                "max": max(numeric),
            }
            if len(numeric) >= 2:
                stats["std_dev"] = round(stdev(numeric), 2)
            results[col] = stats
        else:
            # String column — just report count
            results[col] = {"type": "string", "count": len(values)}

    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze.py <csv_file>")
        sys.exit(1)
    result = analyze_csv(sys.argv[1])

    if "error" in result:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    if "_summary" in result:
        summary = result.pop("_summary")
        print(f"Total rows: {summary['total_rows']}")
        print(f"Total columns: {summary['columns']}")

    for col, stats in result.items():
        print(f"\n{col}:")
        for k, v in stats.items():
            print(f"  {k}: {v}")
