"""Codex routing usage benchmark reports."""

from __future__ import annotations

import csv
import html
import math
from dataclasses import dataclass
from pathlib import Path


RUN_COLUMNS = [
    "run_id",
    "run_date",
    "task_id",
    "task_name",
    "variant",
    "route",
    "model",
    "exact_input_tokens",
    "exact_cached_input_tokens",
    "exact_output_tokens",
    "tool_calls",
    "file_reads",
    "full_file_reads",
    "tool_output_chars",
    "response_chars",
    "elapsed_seconds",
    "success",
    "quality_score",
    "notes",
]

COMPARISON_COLUMNS = [
    "task_id",
    "task_name",
    "baseline_run_id",
    "routed_run_id",
    "baseline_units",
    "routed_units",
    "unit_delta",
    "unit_delta_pct",
    "tool_call_delta",
    "file_read_delta",
    "elapsed_delta_seconds",
    "quality_delta",
    "baseline_route",
    "routed_route",
]


@dataclass(frozen=True)
class UsageRun:
    run_id: str
    run_date: str
    task_id: str
    task_name: str
    variant: str
    route: str
    model: str
    exact_input_tokens: int
    exact_cached_input_tokens: int
    exact_output_tokens: int
    tool_calls: int
    file_reads: int
    full_file_reads: int
    tool_output_chars: int
    response_chars: int
    elapsed_seconds: int
    success: str
    quality_score: float
    notes: str

    @property
    def has_exact_tokens(self) -> bool:
        return any(
            value > 0
            for value in [
                self.exact_input_tokens,
                self.exact_cached_input_tokens,
                self.exact_output_tokens,
            ]
        )

    @property
    def estimated_input_tokens(self) -> int:
        return math.ceil(self.tool_output_chars / 4)

    @property
    def estimated_output_tokens(self) -> int:
        return math.ceil(self.response_chars / 4)

    @property
    def consumption_units(self) -> float:
        if self.has_exact_tokens:
            return (
                self.exact_input_tokens
                + (self.exact_cached_input_tokens * 0.1)
                + (self.exact_output_tokens * 6)
            )
        return self.estimated_input_tokens + (self.estimated_output_tokens * 6)

    def to_row(self) -> dict[str, str]:
        return {
            "run_id": self.run_id,
            "run_date": self.run_date,
            "task_id": self.task_id,
            "task_name": self.task_name,
            "variant": self.variant,
            "route": self.route,
            "model": self.model,
            "exact_input_tokens": str(self.exact_input_tokens),
            "exact_cached_input_tokens": str(self.exact_cached_input_tokens),
            "exact_output_tokens": str(self.exact_output_tokens),
            "tool_calls": str(self.tool_calls),
            "file_reads": str(self.file_reads),
            "full_file_reads": str(self.full_file_reads),
            "tool_output_chars": str(self.tool_output_chars),
            "response_chars": str(self.response_chars),
            "elapsed_seconds": str(self.elapsed_seconds),
            "success": self.success,
            "quality_score": format_float(self.quality_score),
            "notes": self.notes,
        }


@dataclass(frozen=True)
class UsageComparison:
    task_id: str
    task_name: str
    baseline: UsageRun
    routed: UsageRun

    @property
    def unit_delta(self) -> float:
        return self.routed.consumption_units - self.baseline.consumption_units

    @property
    def unit_delta_pct(self) -> float:
        if self.baseline.consumption_units <= 0:
            return 0.0
        return self.unit_delta / self.baseline.consumption_units

    @property
    def tool_call_delta(self) -> int:
        return self.routed.tool_calls - self.baseline.tool_calls

    @property
    def file_read_delta(self) -> int:
        return self.routed.file_reads - self.baseline.file_reads

    @property
    def elapsed_delta_seconds(self) -> int:
        return self.routed.elapsed_seconds - self.baseline.elapsed_seconds

    @property
    def quality_delta(self) -> float:
        return self.routed.quality_score - self.baseline.quality_score

    def to_row(self) -> dict[str, str]:
        return {
            "task_id": self.task_id,
            "task_name": self.task_name,
            "baseline_run_id": self.baseline.run_id,
            "routed_run_id": self.routed.run_id,
            "baseline_units": format_float(self.baseline.consumption_units),
            "routed_units": format_float(self.routed.consumption_units),
            "unit_delta": format_float(self.unit_delta),
            "unit_delta_pct": format_percent(self.unit_delta_pct),
            "tool_call_delta": str(self.tool_call_delta),
            "file_read_delta": str(self.file_read_delta),
            "elapsed_delta_seconds": str(self.elapsed_delta_seconds),
            "quality_delta": format_float(self.quality_delta),
            "baseline_route": self.baseline.route,
            "routed_route": self.routed.route,
        }


@dataclass(frozen=True)
class UsageReport:
    runs: list[UsageRun]
    comparisons: list[UsageComparison]

    @property
    def run_count(self) -> int:
        return len(self.runs)

    @property
    def compared_task_count(self) -> int:
        return len(self.comparisons)

    @property
    def average_unit_delta_pct(self) -> float:
        if not self.comparisons:
            return 0.0
        return sum(comparison.unit_delta_pct for comparison in self.comparisons) / len(self.comparisons)

    @property
    def total_baseline_units(self) -> float:
        return sum(comparison.baseline.consumption_units for comparison in self.comparisons)

    @property
    def total_routed_units(self) -> float:
        return sum(comparison.routed.consumption_units for comparison in self.comparisons)

    @property
    def total_unit_delta_pct(self) -> float:
        if self.total_baseline_units <= 0:
            return 0.0
        return (self.total_routed_units - self.total_baseline_units) / self.total_baseline_units


def write_codex_usage_report(run_log_csv: str | Path, output_dir: str | Path) -> UsageReport:
    runs = read_usage_runs(Path(run_log_csv))
    report = UsageReport(runs=runs, comparisons=compare_usage_runs(runs))
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    write_csv(root / "normalized_runs.csv", RUN_COLUMNS, [run.to_row() for run in report.runs])
    write_csv(root / "task_comparison.csv", COMPARISON_COLUMNS, [item.to_row() for item in report.comparisons])
    (root / "summary.md").write_text(format_usage_summary(report), encoding="utf-8")
    (root / "index.html").write_text(format_usage_dashboard(report), encoding="utf-8")
    return report


def read_usage_runs(path: Path) -> list[UsageRun]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return [usage_run_from_row(row) for row in rows if row.get("task_id")]


def usage_run_from_row(row: dict[str, str]) -> UsageRun:
    return UsageRun(
        run_id=row.get("run_id", ""),
        run_date=row.get("run_date", ""),
        task_id=row.get("task_id", ""),
        task_name=row.get("task_name", ""),
        variant=row.get("variant", "").lower(),
        route=row.get("route", ""),
        model=row.get("model", ""),
        exact_input_tokens=int_value(row.get("exact_input_tokens")),
        exact_cached_input_tokens=int_value(row.get("exact_cached_input_tokens")),
        exact_output_tokens=int_value(row.get("exact_output_tokens")),
        tool_calls=int_value(row.get("tool_calls")),
        file_reads=int_value(row.get("file_reads")),
        full_file_reads=int_value(row.get("full_file_reads")),
        tool_output_chars=int_value(row.get("tool_output_chars")),
        response_chars=int_value(row.get("response_chars")),
        elapsed_seconds=int_value(row.get("elapsed_seconds")),
        success=row.get("success", ""),
        quality_score=float_value(row.get("quality_score")),
        notes=row.get("notes", ""),
    )


def compare_usage_runs(runs: list[UsageRun]) -> list[UsageComparison]:
    by_task: dict[str, list[UsageRun]] = {}
    for run in runs:
        by_task.setdefault(run.task_id, []).append(run)
    comparisons = []
    for task_id, task_runs in sorted(by_task.items()):
        baseline = latest_variant(task_runs, "baseline")
        routed = latest_variant(task_runs, "routed")
        if baseline and routed:
            comparisons.append(
                UsageComparison(
                    task_id=task_id,
                    task_name=routed.task_name or baseline.task_name,
                    baseline=baseline,
                    routed=routed,
                )
            )
    return comparisons


def latest_variant(runs: list[UsageRun], variant: str) -> UsageRun | None:
    matching = [run for run in runs if run.variant == variant]
    if not matching:
        return None
    return sorted(matching, key=lambda run: (run.run_date, run.run_id))[-1]


def format_usage_summary(report: UsageReport) -> str:
    lines = [
        "# Codex Routing Usage Report",
        "",
        f"- Runs: {report.run_count}",
        f"- Compared tasks: {report.compared_task_count}",
        f"- Total baseline units: {format_float(report.total_baseline_units)}",
        f"- Total routed units: {format_float(report.total_routed_units)}",
        f"- Total routed delta: {format_percent(report.total_unit_delta_pct)}",
        f"- Average task delta: {format_percent(report.average_unit_delta_pct)}",
        "",
        "## Comparison",
        "",
        "| Task | Baseline | Routed | Delta | Tool Calls | File Reads | Quality |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for comparison in report.comparisons:
        lines.append(
            "| {task} | {baseline} | {routed} | {delta} | {tool_calls} | {file_reads} | {quality} |".format(
                task=comparison.task_name,
                baseline=format_float(comparison.baseline.consumption_units),
                routed=format_float(comparison.routed.consumption_units),
                delta=format_percent(comparison.unit_delta_pct),
                tool_calls=comparison.tool_call_delta,
                file_reads=comparison.file_read_delta,
                quality=format_float(comparison.quality_delta),
            )
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "Consumption units are a stable proxy for comparing runs. When exact token fields are present, units use `input + 0.1 * cached_input + 6 * output`. Otherwise, units estimate tokens from recorded text characters and apply the same output weighting.",
        ]
    )
    return "\n".join(lines) + "\n"


def format_usage_dashboard(report: UsageReport) -> str:
    comparison_rows = "\n".join(format_comparison_html_row(item) for item in report.comparisons)
    run_rows = "\n".join(format_run_html_row(run) for run in sorted(report.runs, key=lambda item: (item.run_date, item.task_id, item.variant)))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Codex Routing Usage</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0; color: #1f2933; background: #f7f8fa; }}
    header {{ background: #17202a; color: white; padding: 24px 32px; }}
    main {{ padding: 24px 32px 48px; max-width: 1200px; margin: 0 auto; }}
    h1, h2 {{ margin: 0 0 12px; }}
    section {{ margin-top: 24px; }}
    .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }}
    .metric {{ background: white; border: 1px solid #d9e2ec; border-radius: 8px; padding: 14px; }}
    .label {{ color: #627d98; font-size: 13px; }}
    .value {{ font-size: 24px; font-weight: 700; margin-top: 4px; }}
    table {{ width: 100%; border-collapse: collapse; background: white; border: 1px solid #d9e2ec; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid #e5eaf0; text-align: left; font-size: 14px; }}
    th {{ background: #eef2f7; color: #334e68; }}
    .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .good {{ color: #0b7a53; font-weight: 700; }}
    .bad {{ color: #b42318; font-weight: 700; }}
    .muted {{ color: #627d98; }}
  </style>
</head>
<body>
  <header>
    <h1>Codex Routing Usage</h1>
    <div class="muted">Proxy dashboard for measuring routing impact over repeatable developer tasks.</div>
  </header>
  <main>
    <section class="metrics">
      <div class="metric"><div class="label">Runs</div><div class="value">{report.run_count}</div></div>
      <div class="metric"><div class="label">Compared Tasks</div><div class="value">{report.compared_task_count}</div></div>
      <div class="metric"><div class="label">Total Delta</div><div class="value {delta_class(report.total_unit_delta_pct)}">{format_percent(report.total_unit_delta_pct)}</div></div>
      <div class="metric"><div class="label">Average Task Delta</div><div class="value {delta_class(report.average_unit_delta_pct)}">{format_percent(report.average_unit_delta_pct)}</div></div>
    </section>
    <section>
      <h2>Task Comparison</h2>
      <table>
        <thead><tr><th>Task</th><th>Baseline Route</th><th>Routed Route</th><th class="num">Baseline Units</th><th class="num">Routed Units</th><th class="num">Delta</th><th class="num">Tool Calls</th><th class="num">File Reads</th><th class="num">Quality</th></tr></thead>
        <tbody>{comparison_rows}</tbody>
      </table>
    </section>
    <section>
      <h2>Run Log</h2>
      <table>
        <thead><tr><th>Date</th><th>Task</th><th>Variant</th><th>Route</th><th>Model</th><th class="num">Units</th><th class="num">Tool Calls</th><th class="num">File Reads</th><th class="num">Elapsed</th><th class="num">Quality</th></tr></thead>
        <tbody>{run_rows}</tbody>
      </table>
    </section>
  </main>
</body>
</html>
"""


def format_comparison_html_row(comparison: UsageComparison) -> str:
    return (
        "<tr>"
        f"<td>{escape(comparison.task_name)}</td>"
        f"<td>{escape(comparison.baseline.route)}</td>"
        f"<td>{escape(comparison.routed.route)}</td>"
        f"<td class=\"num\">{format_float(comparison.baseline.consumption_units)}</td>"
        f"<td class=\"num\">{format_float(comparison.routed.consumption_units)}</td>"
        f"<td class=\"num {delta_class(comparison.unit_delta_pct)}\">{format_percent(comparison.unit_delta_pct)}</td>"
        f"<td class=\"num\">{comparison.tool_call_delta}</td>"
        f"<td class=\"num\">{comparison.file_read_delta}</td>"
        f"<td class=\"num\">{format_float(comparison.quality_delta)}</td>"
        "</tr>"
    )


def format_run_html_row(run: UsageRun) -> str:
    return (
        "<tr>"
        f"<td>{escape(run.run_date)}</td>"
        f"<td>{escape(run.task_name)}</td>"
        f"<td>{escape(run.variant)}</td>"
        f"<td>{escape(run.route)}</td>"
        f"<td>{escape(run.model)}</td>"
        f"<td class=\"num\">{format_float(run.consumption_units)}</td>"
        f"<td class=\"num\">{run.tool_calls}</td>"
        f"<td class=\"num\">{run.file_reads}</td>"
        f"<td class=\"num\">{run.elapsed_seconds}</td>"
        f"<td class=\"num\">{format_float(run.quality_score)}</td>"
        "</tr>"
    )


def write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def int_value(value: str | None) -> int:
    try:
        return int(float(value or 0))
    except ValueError:
        return 0


def float_value(value: str | None) -> float:
    try:
        return float(value or 0)
    except ValueError:
        return 0.0


def format_float(value: float) -> str:
    if abs(value - round(value)) < 0.005:
        return str(int(round(value)))
    return f"{value:.2f}"


def format_percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def delta_class(value: float) -> str:
    if value < 0:
        return "good"
    if value > 0:
        return "bad"
    return ""


def escape(value: str) -> str:
    return html.escape(value or "")
