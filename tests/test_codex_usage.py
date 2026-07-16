import csv

from draft_room_intelligence.reports.codex_usage import write_codex_usage_report


def write_rows(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def base_row(**overrides):
    row = {
        "run_id": "run",
        "run_date": "2026-07-16",
        "task_id": "demo-status",
        "task_name": "Explain current demo status",
        "variant": "baseline",
        "route": "main",
        "model": "gpt-5.6",
        "exact_input_tokens": "",
        "exact_cached_input_tokens": "",
        "exact_output_tokens": "",
        "tool_calls": "6",
        "file_reads": "5",
        "full_file_reads": "2",
        "tool_output_chars": "18000",
        "response_chars": "1800",
        "elapsed_seconds": "240",
        "success": "yes",
        "quality_score": "4",
        "notes": "",
    }
    row.update(overrides)
    return row


def test_write_codex_usage_report_compares_latest_baseline_and_routed(tmp_path):
    run_log = tmp_path / "run_log.csv"
    write_rows(
        run_log,
        [
            base_row(run_id="baseline-old", run_date="2026-07-15", tool_calls="8"),
            base_row(run_id="baseline-new", run_date="2026-07-16", tool_calls="6"),
            base_row(
                run_id="routed-new",
                variant="routed",
                route="project-context",
                tool_calls="3",
                file_reads="2",
                full_file_reads="0",
                tool_output_chars="7000",
                response_chars="900",
                elapsed_seconds="150",
                quality_score="4",
            ),
        ],
    )

    report = write_codex_usage_report(run_log, tmp_path / "report")

    assert report.run_count == 3
    assert report.compared_task_count == 1
    comparison = report.comparisons[0]
    assert comparison.baseline.run_id == "baseline-new"
    assert comparison.routed.run_id == "routed-new"
    assert comparison.unit_delta_pct < 0
    rows = list(csv.DictReader((tmp_path / "report" / "task_comparison.csv").open()))
    assert rows[0]["routed_route"] == "project-context"
    assert rows[0]["recommendation"] == "keep_route"
    route_rows = list(csv.DictReader((tmp_path / "report" / "route_summary.csv").open()))
    assert route_rows[0]["route"] == "project-context"
    assert route_rows[0]["recommendation"] == "collect_more_runs"
    assert (tmp_path / "report" / "summary.md").exists()
    assert (tmp_path / "report" / "index.html").exists()


def test_write_codex_usage_report_uses_exact_token_fields_when_present(tmp_path):
    run_log = tmp_path / "run_log.csv"
    write_rows(
        run_log,
        [
            base_row(
                run_id="baseline",
                exact_input_tokens="1000",
                exact_cached_input_tokens="200",
                exact_output_tokens="100",
                tool_output_chars="999999",
                response_chars="999999",
            ),
            base_row(
                run_id="routed",
                variant="routed",
                route="validate-change",
                exact_input_tokens="700",
                exact_cached_input_tokens="100",
                exact_output_tokens="50",
                tool_output_chars="999999",
                response_chars="999999",
            ),
        ],
    )

    report = write_codex_usage_report(run_log, tmp_path / "report")

    comparison = report.comparisons[0]
    assert comparison.baseline.consumption_units == 1620
    assert comparison.routed.consumption_units == 1010
    assert comparison.unit_delta < 0


def test_write_codex_usage_report_recommends_simplifying_expensive_route(tmp_path):
    run_log = tmp_path / "run_log.csv"
    write_rows(
        run_log,
        [
            base_row(run_id="baseline", tool_output_chars="4000", response_chars="500", quality_score="4"),
            base_row(
                run_id="routed",
                variant="routed",
                route="reviewer",
                tool_calls="10",
                file_reads="9",
                full_file_reads="4",
                tool_output_chars="20000",
                response_chars="2000",
                quality_score="4",
            ),
        ],
    )

    report = write_codex_usage_report(run_log, tmp_path / "report")

    comparison = report.comparisons[0]
    assert comparison.recommendation == "simplify_route"
    rows = list(csv.DictReader((tmp_path / "report" / "task_comparison.csv").open()))
    assert rows[0]["full_file_read_delta"] == "2"
