"""Report historical Codex model usage without treating cumulative counters as cost."""

from __future__ import annotations

import csv
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

THREAD_COLUMNS = [
    "thread_id",
    "model",
    "reasoning_effort",
    "tokens_used_counter",
    "is_child",
    "created_at",
    "updated_at",
]

MODEL_COLUMNS = [
    "model",
    "threads",
    "child_threads",
    "share",
]


@dataclass(frozen=True)
class CodexThreadTelemetry:
    thread_id: str
    model: str
    reasoning_effort: str
    tokens_used_counter: int
    is_child: bool
    created_at: int
    updated_at: int

    def to_row(self) -> dict[str, str]:
        return {
            "thread_id": self.thread_id,
            "model": self.model,
            "reasoning_effort": self.reasoning_effort,
            "tokens_used_counter": str(self.tokens_used_counter),
            "is_child": "yes" if self.is_child else "no",
            "created_at": format_timestamp(self.created_at),
            "updated_at": format_timestamp(self.updated_at),
        }


def write_codex_telemetry_report(
    state_db: str | Path,
    output_dir: str | Path,
    *,
    project_root: str | Path,
) -> list[CodexThreadTelemetry]:
    threads = load_codex_thread_telemetry(state_db, project_root=project_root)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "threads.csv", THREAD_COLUMNS, [thread.to_row() for thread in threads])
    model_rows = model_summary_rows(threads)
    write_csv(output / "model_summary.csv", MODEL_COLUMNS, model_rows)
    (output / "summary.md").write_text(
        format_codex_telemetry_report(threads, model_rows, project_root=Path(project_root)),
        encoding="utf-8",
    )
    return threads


def load_codex_thread_telemetry(
    state_db: str | Path,
    *,
    project_root: str | Path,
) -> list[CodexThreadTelemetry]:
    database = Path(state_db).expanduser().resolve()
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    try:
        rows = connection.execute(
            """
            SELECT
                t.id,
                COALESCE(NULLIF(t.model, ''), '(none)'),
                COALESCE(NULLIF(t.reasoning_effort, ''), '(none)'),
                COALESCE(t.tokens_used, 0),
                CASE WHEN e.child_thread_id IS NULL THEN 0 ELSE 1 END,
                t.created_at,
                t.updated_at
            FROM threads AS t
            LEFT JOIN thread_spawn_edges AS e ON e.child_thread_id = t.id
            WHERE t.cwd LIKE ?
            ORDER BY t.created_at, t.id
            """,
            (f"{Path(project_root).resolve()}%",),
        ).fetchall()
    finally:
        connection.close()
    return [
        CodexThreadTelemetry(
            thread_id=row[0],
            model=row[1],
            reasoning_effort=row[2],
            tokens_used_counter=int(row[3]),
            is_child=bool(row[4]),
            created_at=int(row[5]),
            updated_at=int(row[6]),
        )
        for row in rows
    ]


def model_summary_rows(threads: list[CodexThreadTelemetry]) -> list[dict[str, str]]:
    counts = Counter(thread.model for thread in threads)
    child_counts = Counter(thread.model for thread in threads if thread.is_child)
    total = len(threads)
    return [
        {
            "model": model,
            "threads": str(count),
            "child_threads": str(child_counts[model]),
            "share": f"{count / total:.1%}" if total else "0.0%",
        }
        for model, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def format_codex_telemetry_report(
    threads: list[CodexThreadTelemetry],
    model_rows: list[dict[str, str]],
    *,
    project_root: Path,
) -> str:
    lines = [
        "# Codex Model Telemetry",
        "",
        f"- Project root: `{project_root.resolve()}`",
        f"- Recorded threads: {len(threads)}",
        f"- Child/subagent threads: {sum(thread.is_child for thread in threads)}",
        "",
        "| Model | Threads | Child threads | Share |",
        "| --- | ---: | ---: | ---: |",
    ]
    for row in model_rows:
        lines.append(
            f"| {row['model']} | {row['threads']} | {row['child_threads']} | {row['share']} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            (
                "This report proves which models were selected. `tokens_used_counter` is retained "
                "per thread for diagnostics, but it is cumulative internal state and is not summed "
                "or presented as billable consumption."
            ),
            "",
            (
                "Use `run-codex-task` for future work to capture exact per-run JSON usage in "
                "`outputs/codex_usage/run_log.csv`. Savings require matched baseline and routed "
                "runs with comparable quality; model counts alone do not prove savings."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def format_timestamp(value: int) -> str:
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()


def write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
