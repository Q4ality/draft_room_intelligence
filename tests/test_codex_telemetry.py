import csv
import sqlite3

from draft_room_intelligence.reports.codex_telemetry import write_codex_telemetry_report


def create_state_db(path, project_root):
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE threads (
            id TEXT PRIMARY KEY,
            model TEXT,
            reasoning_effort TEXT,
            tokens_used INTEGER,
            cwd TEXT,
            created_at INTEGER,
            updated_at INTEGER
        );
        CREATE TABLE thread_spawn_edges (
            parent_thread_id TEXT NOT NULL,
            child_thread_id TEXT NOT NULL PRIMARY KEY,
            status TEXT NOT NULL
        );
        """
    )
    connection.executemany(
        "INSERT INTO threads VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("main", "gpt-5.6-sol", "medium", 1000, str(project_root), 100, 200),
            ("child", "gpt-5.6-luna", "low", 200, str(project_root / "src"), 110, 120),
            ("other", "gpt-5.6-terra", "low", 300, "/another/repo", 100, 200),
        ],
    )
    connection.execute(
        "INSERT INTO thread_spawn_edges VALUES (?, ?, ?)",
        ("main", "child", "closed"),
    )
    connection.commit()
    connection.close()


def test_write_codex_telemetry_report_filters_project_and_counts_models(tmp_path):
    project_root = tmp_path / "repo"
    project_root.mkdir()
    state_db = tmp_path / "state.sqlite"
    create_state_db(state_db, project_root)

    threads = write_codex_telemetry_report(
        state_db,
        tmp_path / "report",
        project_root=project_root,
    )

    assert [thread.model for thread in threads] == ["gpt-5.6-sol", "gpt-5.6-luna"]
    rows = list(
        csv.DictReader((tmp_path / "report" / "model_summary.csv").open(encoding="utf-8"))
    )
    assert {row["model"] for row in rows} == {"gpt-5.6-sol", "gpt-5.6-luna"}
    luna = next(row for row in rows if row["model"] == "gpt-5.6-luna")
    assert luna["child_threads"] == "1"
    summary = (tmp_path / "report" / "summary.md").read_text(encoding="utf-8")
    assert "not summed or presented as billable consumption" in summary
