import csv
import json

from draft_room_intelligence.data.league_pipeline import run_league_pipeline


def write_csv(path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_pipeline_writes_resumable_operational_artifacts_without_network(tmp_path):
    final = tmp_path / "classes" / "2025" / "final"
    write_csv(final / "players.csv", ["player_id", "name"], [{"player_id": "p1", "name": "Player"}])
    write_csv(
        final / "season_stat_lines.csv",
        ["player_id", "season", "league", "team", "timing", "regular_season", "games"],
        [
            {
                "player_id": "p1",
                "season": "2024-25",
                "league": "OHL",
                "team": "X",
                "timing": "pre_draft",
                "regular_season": "true",
                "games": "20",
            }
        ],
    )
    write_csv(final / "advanced_stat_lines.csv", ["player_id"], [])
    manifest = tmp_path / "sources.csv"
    manifest.write_text(
        "source_id,enabled,draft_year,adapter,league,season,stage,source_url,cache_path,source_label\n"
        "missing,false,2025,open_csv,OHL,2024-25,regular,,missing.csv,test\n",
        encoding="utf-8",
    )
    europe_catalog = tmp_path / "europe.csv"
    europe_catalog.write_text(
        "source_id,enabled,draft_year,adapter,league,season,stage,source_url,cache_path,source_label\n",
        encoding="utf-8",
    )

    summary = run_league_pipeline(
        manifest,
        tmp_path / "classes",
        tmp_path / "report",
        project_root=tmp_path,
        europe_catalog_path=europe_catalog,
        start_year=2025,
        end_year=2025,
    )

    payload = json.loads((tmp_path / "report" / "run_summary.json").read_text())
    assert summary.enrichment_failures == 0
    assert payload["ready_sources"] == 0
    assert (tmp_path / "report" / "resolved_sources.csv").is_file()
    assert (tmp_path / "report" / "audit" / "year_summary.csv").is_file()
