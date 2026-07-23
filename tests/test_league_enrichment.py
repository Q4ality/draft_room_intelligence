import csv

import draft_room_intelligence.data.league_enrichment as league_enrichment
from draft_room_intelligence.cli import run_discover_chl_sources, run_discover_europe_sources
from draft_room_intelligence.data.eliteprospects_csv import (
    PLAYER_COLUMNS,
    SEASON_STAT_LINE_COLUMNS,
    write_table,
)
from draft_room_intelligence.data.league_enrichment import (
    LeagueSourceCollectionResult,
    LeagueSourceSpec,
    SweHockeyCatalogSpec,
    collect_league_sources,
    collect_swehockey_catalogs,
    collect_swehockey_seeds,
    discover_chl_source_specs,
    discover_europe_source_specs,
    discover_ncaa_source_specs,
    discover_swehockey_catalog_specs,
    discover_ushl_source_specs,
    enable_collected_sources,
    enrich_draft_class_leagues,
    filter_league_sources,
    generate_liiga_source_specs,
    generate_swehockey_source_specs,
    load_league_source_manifest,
    parse_swehockey_season_roots,
    parse_swehockey_tournaments,
    run_league_enrichment_range,
    validate_source_cache,
    validate_swehockey_catalog,
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


def test_filter_league_sources_can_select_exact_provider_label(tmp_path):
    swehockey = LeagueSourceSpec(
        **{
            **source_spec(tmp_path / "sweden.html").__dict__,
            "adapter": "europe",
            "source_label": "swehockey:combined",
        }
    )
    liiga = LeagueSourceSpec(
        **{
            **swehockey.__dict__,
            "source_id": "2025-liiga",
            "source_label": "liiga:skaters",
        }
    )

    selected = filter_league_sources(
        [swehockey, liiga],
        source_labels={"swehockey:combined"},
    )

    assert [source.source_id for source in selected] == ["2025-ohl-regular"]


def test_enable_collected_sources_only_enables_successful_backlog(tmp_path):
    ready = LeagueSourceSpec(**{**source_spec(tmp_path / "ready").__dict__, "enabled": False})
    failed = LeagueSourceSpec(
        **{
            **source_spec(tmp_path / "failed").__dict__,
            "source_id": "2025-ohl-playoffs",
            "enabled": False,
        }
    )
    results = [
        LeagueSourceCollectionResult(ready.source_id, 2025, "downloaded", "", 1, "ready"),
        LeagueSourceCollectionResult(failed.source_id, 2025, "failed", "", 0, "empty"),
    ]

    updated = enable_collected_sources([ready, failed], results)

    assert updated[0].enabled is True
    assert updated[1].enabled is False


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


def test_run_discover_chl_sources_preserves_other_manifest_adapters(tmp_path):
    manifest = tmp_path / "sources.csv"
    manifest.write_text(
        "source_id,enabled,draft_year,adapter,league,season,stage,source_url,cache_path,source_label\n"
        "ncaa,true,2025,ncaa,NCAA,2024-25,regular,https://example.test,ncaa.html,test\n",
        encoding="utf-8",
    )
    catalog = tmp_path / "ohl.html"
    catalog.write_text(CHL_CATALOG_HTML, encoding="utf-8")

    run_discover_chl_sources(
        manifest,
        [f"OHL,{catalog}"],
        cache_root=tmp_path / "cache",
        project_root=tmp_path,
        start_year=2025,
        end_year=2025,
    )

    sources = load_league_source_manifest(manifest, project_root=tmp_path)
    assert {source.adapter for source in sources} == {"chl", "ncaa"}
    assert any(source.source_id == "ncaa" for source in sources)


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
    swehockey_cache = tmp_path / "data/raw/cache/europe_stats"
    swehockey_cache.mkdir(parents=True)
    (swehockey_cache / "swehockey_seed_hockeyallsvenskan.html").write_text(
        '<select><option value="/ScheduleAndResults/Overview/17570">2024-25</option></select>',
        encoding="utf-8",
    )
    (swehockey_cache / "swehockey_catalog_hockeyallsvenskan_2025.html").write_text(
        "<label>2024-25 - HockeyAllsvenskan</label><select>"
        '<option value="/ScheduleAndResults/Overview/16000">HockeyAllsvenskan</option>'
        '<option value="/ScheduleAndResults/Overview/17571">Slutspel HockeyAllsvenskan</option>'
        "</select>",
        encoding="utf-8",
    )
    catalog = tmp_path / "catalog.csv"
    catalog.write_text(
        "source_id,enabled,draft_year,adapter,league,season,stage,source_url,cache_path,source_label\n"
        "sweden,false,2025,europe,SHL,2024-25,regular,https://example.test/swe,cache/sweden.html,swehockey:combined\n"
        "2025-hockeyallsvenskan-playoffs,false,2025,europe,HockeyAllsvenskan,2024-25,playoffs,"
        "https://stats.swehockey.se/Teams/Info/PlayersByTeam/old,cache/old.html,swehockey:combined\n"
        "liiga,false,2025,europe,Liiga,2024-25,regular,https://example.test/fin,cache/liiga.json,liiga:skaters\n",
        encoding="utf-8",
    )

    sources = discover_europe_source_specs(
        catalog,
        project_root=tmp_path,
        start_year=2025,
        end_year=2025,
    )

    enabled = {source.source_id: source.enabled for source in sources}
    assert enabled["sweden"] is True
    assert "2025-hockeyallsvenskan-playoffs" not in enabled
    assert enabled["liiga"] is False
    assert len([source for source in sources if source.source_id.startswith("2025-liiga")]) == 4


def test_generate_liiga_source_specs_covers_each_year_stage_and_role(tmp_path):
    cached = tmp_path / "2022_liiga_regular_skaters.json"
    cached.write_text("[]", encoding="utf-8")

    sources = generate_liiga_source_specs(
        cache_root=tmp_path,
        start_year=2022,
        end_year=2023,
    )

    assert len(sources) == 8
    assert {source.draft_year for source in sources} == {2022, 2023}
    assert {source.regular_season for source in sources} == {True, False}
    assert {source.source_label for source in sources} == {"liiga:skaters", "liiga:goalies"}
    assert sources[0].enabled is True
    assert "summed/2021/2021/runkosarja" in sources[0].source_url


def test_swehockey_discovery_uses_seed_seasons_and_catalog_tournaments(tmp_path):
    seed = tmp_path / "swehockey_seed_shl.html"
    seed.write_text(
        '<select><option value="/ScheduleAndResults/Overview/17556">2024-25</option>'
        '<option value="/ScheduleAndResults/Overview/15791">2023-24</option></select>',
        encoding="utf-8",
    )
    roots = parse_swehockey_season_roots(seed.read_text(encoding="utf-8"))
    assert roots == {2025: "17556", 2024: "15791"}

    catalogs = discover_swehockey_catalog_specs(
        cache_root=tmp_path,
        start_year=2024,
        end_year=2024,
    )
    assert len(catalogs) == 1
    assert catalogs[0].source_url.endswith("/15791")

    catalogs[0].cache_path.write_text(
        "<label>2023-24 - SHL</label><select>"
        '<option value="/ScheduleAndResults/Overview/15791">Play Out SHL</option>'
        '<option value="/ScheduleAndResults/Overview/15792">SM-slutspel SHL</option>'
        '<option value="/ScheduleAndResults/Overview/14677">SHL</option>'
        "</select>",
        encoding="utf-8",
    )
    sources = generate_swehockey_source_specs(
        cache_root=tmp_path,
        start_year=2024,
        end_year=2024,
    )
    assert len(sources) == 2
    assert {source.regular_season for source in sources} == {True, False}
    assert {source.source_url.rsplit("/", 1)[-1] for source in sources} == {"15792", "14677"}
    assert {source.source_id for source in sources} == {
        "2024-shl-regular",
        "2024-shl-playoffs",
    }


def test_swehockey_junior_discovery_keeps_competitive_phases():
    raw = (
        "<label>2023-24 - U20 Nationell</label><select>"
        '<option value="/ScheduleAndResults/Overview/15769">J20 SM-slutspel</option>'
        '<option value="/ScheduleAndResults/Overview/15961">Kvalserien till J20 Nationell</option>'
        '<option value="/ScheduleAndResults/Overview/15645">J20 - Nationell Top 10</option>'
        '<option value="/ScheduleAndResults/Overview/15644">J20 - Nationell Forts.</option>'
        '<option value="/ScheduleAndResults/Overview/14709">J20 - Nationell Sodra</option>'
        '<option value="/ScheduleAndResults/Overview/15785">Play Off till J20 Nationell</option>'
        "</select>"
    )

    tournaments = parse_swehockey_tournaments(raw, "Sweden Jrs.")

    assert [(row[1], row[2]) for row in tournaments] == [
        ("J20 SM-slutspel", False),
        ("J20 - Nationell Top 10", True),
        ("J20 - Nationell Forts.", True),
        ("J20 - Nationell Sodra", True),
    ]


def test_swehockey_historical_playoff_labels_are_classified():
    shl = (
        "<label>2014-15 - SHL</label><select>"
        '<option value="/ScheduleAndResults/Overview/1">SHL</option>'
        '<option value="/ScheduleAndResults/Overview/2">SM-slutspel SHL</option>'
        '<option value="/ScheduleAndResults/Overview/3">Play Out SHL</option>'
        "</select>"
    )
    allsvenskan = (
        "<label>2014-15 - HockeyAllsvenskan</label><select>"
        '<option value="/ScheduleAndResults/Overview/4">HockeyAllsvenskan</option>'
        '<option value="/ScheduleAndResults/Overview/5">Slutspelsserien</option>'
        '<option value="/ScheduleAndResults/Overview/6">HockeyAllsvenskan Final</option>'
        '<option value="/ScheduleAndResults/Overview/7">Play Off till SHL</option>'
        "</select>"
    )

    assert [(row[1], row[2]) for row in parse_swehockey_tournaments(shl, "SHL")] == [
        ("SHL", True),
        ("SM-slutspel SHL", False),
    ]
    assert [
        (row[1], row[2])
        for row in parse_swehockey_tournaments(allsvenskan, "HockeyAllsvenskan")
    ] == [
        ("HockeyAllsvenskan", True),
        ("Slutspelsserien", False),
        ("HockeyAllsvenskan Final", False),
    ]


def test_swehockey_hockeyallsvenskan_postseason_phases_have_unique_ids(tmp_path):
    (tmp_path / "swehockey_seed_hockeyallsvenskan.html").write_text(
        '<select><option value="/ScheduleAndResults/Overview/4">2014-15</option></select>',
        encoding="utf-8",
    )
    catalog = tmp_path / "swehockey_catalog_hockeyallsvenskan_2015.html"
    catalog.write_text(
        "<label>2014-15 - HockeyAllsvenskan</label><select>"
        '<option value="/ScheduleAndResults/Overview/4">HockeyAllsvenskan</option>'
        '<option value="/ScheduleAndResults/Overview/5">Slutspelsserien</option>'
        '<option value="/ScheduleAndResults/Overview/6">HockeyAllsvenska finalen</option>'
        "</select>",
        encoding="utf-8",
    )

    sources = generate_swehockey_source_specs(
        cache_root=tmp_path,
        start_year=2015,
        end_year=2015,
    )

    ids = [source.source_id for source in sources]
    assert len(ids) == len(set(ids))
    assert "2015-hockeyallsvenskan-slutspelsserien-playoffs" in ids
    assert "2015-hockeyallsvenskan-hockeyallsvenska-finalen-playoffs" in ids


def test_swehockey_catalog_supports_reversed_2019_20_shl_label():
    raw = (
        "<label>SHL - 2019-20</label><select>"
        '<option value="/ScheduleAndResults/Overview/10371">Games</option>'
        "</select>"
    )
    catalog = SweHockeyCatalogSpec(
        "SHL",
        2020,
        "2019-20",
        "https://example.test/catalog",
        None,
    )

    validate_swehockey_catalog(raw, catalog)

    assert parse_swehockey_tournaments(raw, "SHL") == [("10371", "SHL", True)]


def test_swehockey_seed_collection_bootstraps_empty_cache(tmp_path, monkeypatch):
    seed_html = (
        '<select><option value="/ScheduleAndResults/Overview/15791">'
        "2023-24</option></select>"
    ).encode()
    monkeypatch.setattr(league_enrichment, "download_url", lambda _: seed_html)

    collect_swehockey_seeds(cache_root=tmp_path)

    assert (tmp_path / "swehockey_seed_shl.html").is_file()
    assert (tmp_path / "swehockey_seed_hockeyallsvenskan.html").is_file()
    assert (tmp_path / "swehockey_seed_sweden_j20.html").is_file()


def test_swehockey_catalog_collection_rejects_error_page(tmp_path, monkeypatch):
    catalog = SweHockeyCatalogSpec(
        "SHL",
        2024,
        "2023-24",
        "https://example.test/catalog",
        tmp_path / "catalog.html",
    )
    monkeypatch.setattr(
        league_enrichment,
        "download_url",
        lambda _: b"<html><title>Forbidden</title></html>",
    )

    results = collect_swehockey_catalogs([catalog], continue_on_error=True)

    assert results[0].status == "failed"
    assert not catalog.cache_path.exists()


def test_swehockey_catalog_validation_requires_expected_tournaments():
    catalog = SweHockeyCatalogSpec(
        "SHL",
        2024,
        "2023-24",
        "https://example.test/catalog",
        None,
    )

    try:
        validate_swehockey_catalog("<label>2023-24 - SHL</label><select></select>", catalog)
    except ValueError as exc:
        assert "no classified" in str(exc)
    else:
        raise AssertionError("empty Swehockey tournament catalog should fail")


def test_bounded_europe_discovery_preserves_other_years(tmp_path):
    manifest = tmp_path / "sources.csv"
    manifest.write_text(
        "source_id,enabled,draft_year,adapter,league,season,stage,source_url,cache_path,source_label\n"
        "2025-shl-regular,false,2025,europe,SHL,2024-25,regular,"
        "https://example.test/shl,cache/2025.html,swehockey:combined\n"
        "2024-vhl-reviewed,false,2024,europe,VHL,2023-24,regular,"
        "https://example.test/vhl,cache/vhl.html,khl:skaters\n"
        "2025-ohl-regular,false,2025,chl,OHL,2024-25,regular,"
        "https://example.test/ohl,cache/ohl.html,chl\n",
        encoding="utf-8",
    )
    catalog = tmp_path / "europe.csv"
    catalog.write_text(
        "source_id,enabled,draft_year,adapter,league,season,stage,source_url,cache_path,source_label\n",
        encoding="utf-8",
    )

    run_discover_europe_sources(
        manifest,
        catalog_path=catalog,
        project_root=tmp_path,
        start_year=2024,
        end_year=2024,
    )

    sources = load_league_source_manifest(manifest, project_root=tmp_path)
    assert any(source.source_id == "2025-shl-regular" for source in sources)
    assert any(source.source_id == "2024-vhl-reviewed" for source in sources)
    assert any(source.source_id == "2025-ohl-regular" for source in sources)
    assert len([source for source in sources if source.draft_year == 2024]) == 5


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
