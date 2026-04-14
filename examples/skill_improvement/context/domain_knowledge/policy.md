# CSV Analysis Domain Policy

## Data Handling Requirements

1. **Encoding**: All CSV files must be read with UTF-8 encoding. Many real-world files contain international characters.
2. **Missing Values**: Never silently drop rows. Report missing values per column and compute statistics on available data.
3. **Statistics Required**: For numeric columns: count, mean, median, min, max, standard deviation. For string columns: count, unique count, most frequent value, frequency of most frequent value.
4. **Error Handling**: If a file cannot be read, provide a clear error message with the cause and suggest fixes.
5. **Output Format**: Always present results in a markdown table with clear column headers.

## Quality Standards

- Accuracy: Statistics must be computed on ALL available data, not a subset.
- Transparency: Always report how many rows were processed vs total rows.
- Robustness: Handle edge cases (empty files, single row, all missing values in a column).
