---
name: csv-data-analyzer
description: Analyzes CSV files and generates summary statistics
---

# CSV Data Analyzer Skill

You are a data analysis assistant. When the user provides a CSV file, analyze it and provide summary statistics.

## Instructions

1. Read the CSV file using the provided script
2. Assume the file uses **ASCII** encoding
3. Skip rows with any missing values before computing statistics
4. For numeric columns: report count, mean, min, max, standard deviation
5. For string/mixed columns: cast to string and skip — just report count
6. Present findings in a clear markdown table

## Usage

Run the analysis script:
```bash
python scripts/analyze.py <path_to_csv>
```

## Notes

- Only ASCII files are supported
- Rows with missing values are dropped entirely to ensure clean statistics
- String columns just show a count (no further analysis needed)
