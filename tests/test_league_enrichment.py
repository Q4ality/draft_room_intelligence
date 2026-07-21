import csv

from draft_room_intelligence.data.eliteprospects_csv import (
    PLAYER_COLUMNS,
    SEASON_STAT_LINE_COLUMNS,
    write_table,
)
from draft_room_intelligence.data.league_enrichment import (
    LeagueSourceSpec,
    collect_league_sources,
    discover_chl_source_specs,
    discover_europe_source_specs,
    discover_ncaa_source_specs,
    discover_ushl_source_specs,
    enrich_draft_class_leagues,
    filter_league_sources,
    load_league_source_manifest,
    run_league_enrichment_range,
    validate_source_cache,
    write_league_source_manifest,
)

CHL_HTML = """
<table id="topskaters"><tbody></tbody></table>
<script>
$('#topskaters').DataTable({
  data: [[1,"C","77","","",
    ["https://chl.ca/ohl/players/8769","Misa, Michael"],
    [["https://chl.ca/ohl/roster/34/79","SAG"]],"65","62","72","134"]]
});
</script>
"""

CHL_CATALOG_HTML = """
<select id="seasons">
  <option value="https://chl.ca/ohl/stats/leaders/81/">2025 Playoffs</option>
  <option value="https://chl.ca/ohl/stats/leaders/79/">2024-25 Regular Season</option>
  <option value="https://chl.ca/ohl/stats/leaders/78/">2024 Pre-season</option>
  <option value="https://chl.ca/ohl/stats/leaders/77/">2024 Playoffs</option>
  <option value="https://chl.ca/ohl/stats/leaders/76/">2023-24 Regular Season</option>
</select>
"""

USHL_CATALOG_JSON = """{
  "SiteKit": {
    "Seasons": [
      {"season_id": "87", "season_name": "2024-25 Playoffs", "playoff": "1"},
      {"season_id": "85", "season_name": "2024-25", "playoff": "0"},
      {"season_id": "86", "season_name": "2024-25 Preseason", "playoff": "0"},
      {"season_id": "84", "season_name": "2023-24 Playoffs", "playoff": "1"}
    ]
  }
}"""


def write_csv(path, fields, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def scaffold_class(root):
    final = root / "2025" / "final"
    final.mkdir(parents=True)
    write_table(
        final / "players.csv",
        PLAYER_COLUMNS,
        [
            {
                "player_id": "2025-002-michael-misa",
                "name": "Michael Misa",
                "position": "C",
                "source": "nhl_draft_api",
            }
        ],
    )
    write_table(final / "season_stat_lines.csv", SEASON_STAT_LINE_COLUMNS, [])
    write_csv(
        final / "draft_selections.csv",
        ["player_id", "drafted_from_team", "drafted_from_league"],
        [
            {
                "player_id": "2025-002-michael-misa",
                "drafted_from_team": "Saginaw",
                "drafted_from_league": "OHL",
            }
        ],
    )
    return final


def source_spec(cache_path):
    return LeagueSourceSpec(
        source_id="2025-ohl-regular",
        enabled=True,
        draft_year=2025,
        adapter="chl",
        league="OHL",
        season="2024-25",
        regular_season=True,
        source_url="https://chl.ca/ohl/stats/players/79/all/points",
        cache_path=cache_path,
        source_label="chl",
    )


def test_load_manifest_resolves_cache_and_filters_disabled(tmp_path):
    manifest = tmp_path / "sources.csv"
    manifest.write_text(
        "source_id,enabled,draft_year,adapter,league,season,stage,source_url,cache_path,source_label\n"
        "ohl,true,2025,chl,OHL,2024-25,regular,https://example.test/ohl,raw/ohl.html,chl\n",
        encoding="utf-8",
    )

    sources = load_league_source_manifest(manifest, project_root=tmp_path)

    assert len(sources) == 1
    assert sources[0].cache_path == tmp_path / "raw" / "ohl.html"
    assert sources[0].regular_season is True


def test_cached_collection_does_not_require_network(tmp_path):
    cache = tmp_path / "ohl.html"
    cache.write_text(CHL_HTML, encoding="utf-8")

    result = collect_league_sources([source_spec(cache)])

    assert result[0].status == "cached"
    assert result[0].byte_count > 0


def test_filter_league_sources_can_select_adapter(tmp_path):
    chl = source_spec(tmp_path / "ohl.html")
    ncaa = LeagueSourceSpec(
        **{
            **chl.__dict__,
            "source_id": "2025-ncaa",
            "adapter": "ncaa",
            "league": "NCAA",
        }
    )

    selected = filter_league_sources([chl, ncaa], adapters={"ncaa"})

    assert [source.source_id for source in selected] == ["2025-ncaa"]


def test_ushl_cache_validation_rejects_wrong_role_payload(tmp_path):
    cache = tmp_path / "ushl.json"
    cache.write_text(
        '([{"sections":[{"headers":{"name":{},"player_id":{},'
        '"games_played":{},"points":{}},"data":[]}]}])',
        encoding="utf-8",
    )
    source = LeagueSourceSpec(
        source_id="2025-ushl-regular-goalies",
        enabled=True,
        draft_year=2025,
        adapter="ushl",
        league="USHL",
        season="2024-25",
        regular_season=True,
        source_url="https://example.test/ushl",
        cache_path=cache,
        source_label="85:goalies",
    )

    try:
        validate_source_cache(source)
    except ValueError as exc:
        assert "goalies feed" in str(exc)
    else:
        raise AssertionError("skater payload should not validate as a goalie feed")


def test_chl_cache_validation_rejects_wrong_stage(tmp_path):
    cache = tmp_path / "playoffs.html"
    cache.write_text(
        '<title>2024-25 Regular Season Official Statistics</title><table id="topskaters">',
        encoding="utf-8",
    )
    source = source_spec(cache)
    playoff_source = LeagueSourceSpec(
        **{**source.__dict__, "source_id": "playoffs", "regular_season": False}
    )

    try:
        validate_source_cache(playoff_source)
    except ValueError as exc:
        assert "does not indicate playoffs" in str(exc)
    else:
        raise AssertionError("wrong-stage CHL cache should be rejected")


def test_discover_chl_sources_uses_official_season_catalog(tmp_path):
    catalog = tmp_path / "catalog.html"
    catalog.write_text(CHL_CATALOG_HTML, encoding="utf-8")

    sources = discover_chl_source_specs(
        catalog,
        league="OHL",
        cache_root=tmp_path / "cache",
        start_year=2024,
        end_year=2025,
    )
    output = write_league_source_manifest(
        tmp_path / "sources.csv",
        sources,
        project_root=tmp_path,
    )

    assert len(sources) == 4
    assert sources[0].source_id == "2024-ohl-regular"
    assert sources[0].source_url.endswith("/stats/players/76/all/points")
    assert "_s76_regular_" in sources[0].cache_path.name
    assert sources[-1].source_id == "2025-ohl-playoffs"
    rows = list(csv.DictReader(output.open(newline="", encoding="utf-8")))
    assert rows[0]["cache_path"].startswith("cache/")


def test_discover_ushl_sources_generates_skater_and_goalie_feeds(tmp_path):
    catalog = tmp_path / "seasons.json"
    catalog.write_text(USHL_CATALOG_JSON, encoding="utf-8")

    sources = discover_ushl_source_specs(
        catalog,
        cache_root=tmp_path / "cache",
        start_year=2025,
        end_year=2025,
    )

    assert len(sources) == 4
    assert {source.source_label for source in sources} == {
        "85:skaters",
        "85:goalies",
        "87:skaters",
        "87:goalies",
    }
    goalie = next(source for source in sources if source.source_label == "85:goalies")
    assert "position=goalies" in goalie.source_url
    assert "sort=save_percentage" in goalie.source_url
    assert goalie.cache_path.name == "ushl_2024_25_s85_regular_goalies.json"


def test_discover_ncaa_sources_uses_historical_fallback_and_current_provider(tmp_path):
    sources = discover_ncaa_source_specs(
        cache_root=tmp_path / "cache",
        start_year=2021,
        end_year=2022,
    )

    assert len(sources) == 3
    assert sources[0].source_label == "uscho:combined"
    assert sources[0].source_url.endswith("/2020-2021")
    assert {source.source_label for source in sources[1:]} == {
        "collegehockeyinc:skaters",
        "collegehockeyinc:goalies",
    }


def test_discover_europe_sources_enables_only_collected_catalog_rows(tmp_path):
    cache = tmp_path / "cache" / "sweden.html"
    cache.parent.mkdir()
    cache.write_text("ready", encoding="utf-8")
    catalog = tmp_path / "catalog.csv"
    catalog.write_text(
        "source_id,enabled,draft_year,adapter,league,season,stage,source_url,cache_path,source_label\n"
        "sweden,false,2025,europe,SHL,2024-25,regular,https://example.test/swe,cache/sweden.html,swehockey:combined\n"
        "liiga,false,2025,europe,Liiga,2024-25,regular,https://example.test/fin,cache/liiga.json,liiga:skaters\n",
        encoding="utf-8",
    )

    sources = discover_europe_source_specs(
        catalog,
        project_root=tmp_path,
        start_year=2025,
        end_year=2025,
    )

    assert [source.enabled for source in sources] == [False, True]


def test_class_enrichment_uses_drafted_from_league_and_resumes(tmp_path):
    class_root = tmp_path / "classes"
    final = scaffold_class(class_root)
    cache = tmp_path / "ohl.html"
    cache.write_text(CHL_HTML, encoding="utf-8")

    first = enrich_draft_class_leagues(class_root / "2025", [source_spec(cache)])
    second = enrich_draft_class_leagues(class_root / "2025", [source_spec(cache)])

    with (final / "season_stat_lines.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert first.status == "completed"
    assert first.pre_draft_players == 1
    assert first.coverage_pct == 100.0
    assert second.status == "skipped_complete"
    assert rows[0]["player_id"] == "2025-002-michael-misa"
    assert rows[0]["source"] == "chl"
    assert rows[0]["points"] == "134"


def test_range_report_keeps_unconfigured_years_visible(tmp_path):
    class_root = tmp_path / "classes"
    scaffold_class(class_root)
    cache = tmp_path / "ohl.html"
    cache.write_text(CHL_HTML, encoding="utf-8")

    report = run_league_enrichment_range(
        class_root,
        [source_spec(cache)],
        report_dir=tmp_path / "report",
        start_year=2024,
        end_year=2025,
    )

    assert [row.status for row in report.results] == ["not_configured", "completed"]
    assert (tmp_path / "report" / "summary.md").is_file()
