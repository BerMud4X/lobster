import json
from pathlib import Path
from datetime import datetime
from logger import logger


def _build_snapshot(df):
    """Captures a snapshot of a DataFrame's quality metrics."""
    return {
        "rows": int(df.shape[0]),
        "columns": int(df.shape[1]),
        "missing_values": df.isnull().sum().to_dict(),
        "duplicates": int(df.duplicated().sum()),
        "column_types": {col: str(dtype) for col, dtype in df.dtypes.items()}
    }


def generate_report(df_before, df_after, pipeline_steps):
    """Generates a cleaning report comparing before and after states."""
    return {
        "generated_at": datetime.now().isoformat(),
        "pipeline_steps": pipeline_steps,
        "before": _build_snapshot(df_before),
        "after": _build_snapshot(df_after),
        "summary": {
            "rows_removed": int(df_before.shape[0] - df_after.shape[0]),
            "columns_removed": int(df_before.shape[1] - df_after.shape[1]),
            "missing_values_before": int(df_before.isnull().sum().sum()),
            "missing_values_after": int(df_after.isnull().sum().sum()),
            "duplicates_removed": int(df_before.duplicated().sum() - df_after.duplicated().sum()),
        }
    }


def save_report(report, output_path):
    """Saves the report in the format chosen by the user (text / json / html)."""
    fmt = input("Report format? (text / json / html): ").strip().lower()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    if fmt == 'json':
        path = output_path + ".json"
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

    elif fmt == 'html':
        path = output_path + ".html"
        s = report["summary"]
        b = report["before"]
        a = report["after"]
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>LOBSTER Cleaning Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1 {{ color: #2c3e50; }}
        h2 {{ color: #34495e; border-bottom: 1px solid #ccc; padding-bottom: 5px; }}
        table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
        th, td {{ border: 1px solid #ccc; padding: 8px 12px; text-align: left; }}
        th {{ background-color: #f4f4f4; }}
        .good {{ color: green; }} .bad {{ color: red; }}
    </style>
</head>
<body>
    <h1>LOBSTER ETL — Cleaning Report</h1>
    <p>Generated at: {report['generated_at']}</p>

    <h2>Summary</h2>
    <table>
        <tr><th>Metric</th><th>Before</th><th>After</th><th>Change</th></tr>
        <tr><td>Rows</td><td>{b['rows']}</td><td>{a['rows']}</td><td class="{'good' if s['rows_removed'] >= 0 else 'bad'}">-{s['rows_removed']}</td></tr>
        <tr><td>Columns</td><td>{b['columns']}</td><td>{a['columns']}</td><td>-{s['columns_removed']}</td></tr>
        <tr><td>Missing values</td><td>{s['missing_values_before']}</td><td>{s['missing_values_after']}</td><td class="good">-{s['missing_values_before'] - s['missing_values_after']}</td></tr>
        <tr><td>Duplicates removed</td><td colspan="2"></td><td class="good">{s['duplicates_removed']}</td></tr>
    </table>

    <h2>Pipeline Steps</h2>
    <ol>{''.join(f"<li>{step['step']} — {step['params']}</li>" for step in report['pipeline_steps'])}</ol>

    <h2>Column Types After Cleaning</h2>
    <table>
        <tr><th>Column</th><th>Type</th></tr>
        {''.join(f"<tr><td>{col}</td><td>{dtype}</td></tr>" for col, dtype in a['column_types'].items())}
    </table>
</body>
</html>"""
        with open(path, 'w', encoding='utf-8') as f:
            f.write(html)

    else:  # text
        path = output_path + ".txt"
        s = report["summary"]
        b = report["before"]
        a = report["after"]
        lines = [
            "=== LOBSTER ETL — CLEANING REPORT ===",
            f"Generated at: {report['generated_at']}",
            "",
            "--- SUMMARY ---",
            f"Rows:             {b['rows']} → {a['rows']} (-{s['rows_removed']})",
            f"Columns:          {b['columns']} → {a['columns']} (-{s['columns_removed']})",
            f"Missing values:   {s['missing_values_before']} → {s['missing_values_after']}",
            f"Duplicates removed: {s['duplicates_removed']}",
            "",
            "--- PIPELINE STEPS ---",
            *[f"  {i+1}. {step['step']} — {step['params']}" for i, step in enumerate(report['pipeline_steps'])],
            "",
            "--- COLUMN TYPES AFTER CLEANING ---",
            *[f"  {col}: {dtype}" for col, dtype in a['column_types'].items()],
        ]
        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

    logger.info(f"Report saved to: {path}")
    print(f"Report saved to: {path}")
