"""Cache and apply league-stat sources across normalized draft classes."""

from __future__ import annotations

import csv
import hashlib
import html
import json
import re
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.request import Request, urlopen

from draft_room_intelligence.data.chl_stats import ChlStatSource, enrich_chl_stats
from draft_room_intelligence.data.open_stats_csv import OpenStatsCsvSource, enrich_open_stats_csv
from draft_room_intelligence.data.ushl_stats import (
    USHL_SEASON_CATALOG_URL,
    UShlStatSource,
    enrich_ushl_stats,
    parse_json_or_jsonp,
)
from draft_room_intelligence.data.ushl_stats import (
    source_url as ushl_source_url,
)

SUPPORTED_ADAPTERS = ("chl", "ushl", "open_csv")
ENRICHMENT_STATE_FILE = "league_enrichment_state.json"
PIPELINE_VERSION = 1
LEAGUE_SOURCE_FIELDS = (
    "source_id",
    "enabled",
    "draft_year",
    "adapter",
    "league",
    "season",
    "stage",
    "source_url",
    "cache_path",
    "source_label",
)


@dataclass(frozen=True)
class LeagueSourceSpec:
    source_id: str
    enabled: bool
    draft_year: int
    adapter: str
    league: str
    season: str
    regular_season: bool
    source_url: str
    cache_path: Path
    source_label: str


@dataclass(frozen=True)
class LeagueSourceCollectionResult:
    source_id: str
    draft_year: int
    status: str
    cache_path: str
    byte_count: int
    detail: str


@dataclass(frozen=True)
class LeagueEnrichmentResult:
    draft_year: int
    status: str
    source_count: int
    player_count: int
    pre_draft_players: int
    stat_line_count: int
    league_count: int
    coverage_pct: float
    detail: str


@dataclass(frozen=True)
class LeagueEnrichmentReport:
    results: tuple[LeagueEnrichmentResult, ...]

    @property
    def failed_count(self) -> int:
        return sum(row.status == "failed" for row in self.results)


def discover_chl_source_specs(
    catalog_path: str | Path,
    *,
    league: str,
    cache_root: str | Path,
    start_year: int,
    end_year: int,
) -> list[LeagueSourceSpec]:
    raw = Path(catalog_path).read_text(encoding="utf-8")
    option_pattern = re.compile(
        r'<option\s+value="(?P<url>[^"]+/stats/leaders/(?P<season_id>\d+)/?)"[^>]*>'
        r"(?P<label>.*?)</option>",
        re.IGNORECASE | re.DOTALL,
    )
    discovered: dict[tuple[int, bool], LeagueSourceSpec] = {}
    for match in option_pattern.finditer(raw):
        label = re.sub(r"\s+", " ", html.unescape(match.group("label"))).strip()
        context = chl_season_context(label)
        if context is None:
            continue
        draft_year, regular_season = context
        if not start_year <= draft_year <= end_year:
            continue
        stage = "regular" if regular_season else "playoffs"
        season = f"{draft_year - 1}-{str(draft_year)[-2:]}"
        league_key = league.lower().replace(" ", "-")
        season_id = match.group("season_id")
        generated_cache_path = Path(cache_root) / (
            f"{league_key}_{season.replace('-', '_')}_s{season_id}_{stage}_players.html"
        )
        legacy_name = (
            f"{league_key}_{season.replace('-', '_')}_regular_players.html"
            if regular_season
            else f"{league_key}_{season.replace('-', '_')}_true_playoffs_players.html"
        )
        legacy_cache_path = Path(cache_root) / legacy_name
        cache_path = legacy_cache_path if legacy_cache_path.is_file() else generated_cache_path
        source_url = match.group("url").replace("/stats/leaders/", "/stats/players/")
        source_url = source_url.rstrip("/") + "/all/points"
        discovered[(draft_year, regular_season)] = LeagueSourceSpec(
            source_id=f"{draft_year}-{league_key}-{stage}",
            enabled=cache_path.is_file(),
            draft_year=draft_year,
            adapter="chl",
            league=league,
            season=season,
            regular_season=regular_season,
            source_url=source_url,
            cache_path=cache_path,
            source_label="chl",
        )
    return sorted(
        discovered.values(),
        key=lambda source: (source.draft_year, not source.regular_season),
    )


def chl_season_context(label: str) -> tuple[int, bool] | None:
    regular = re.search(r"(20\d{2})\s*-\s*(\d{2}).*Regular Season", label, re.IGNORECASE)
    if regular:
        return int(regular.group(1)) + 1, True
    playoffs = re.search(r"(20\d{2}).*Playoffs", label, re.IGNORECASE)
    if playoffs:
        return int(playoffs.group(1)), False
    return None


def discover_ushl_source_specs(
    catalog_path: str | Path,
    *,
    cache_root: str | Path,
    start_year: int,
    end_year: int,
) -> list[LeagueSourceSpec]:
    payload = json.loads(Path(catalog_path).read_text(encoding="utf-8"))
    sitekit = payload.get("SiteKit", {})
    seasons = sitekit.get("Seasons", []) if isinstance(sitekit, dict) else []
    discovered: list[LeagueSourceSpec] = []
    for row in seasons:
        if not isinstance(row, dict):
            continue
        context = ushl_season_context(str(row.get("season_name", "")), str(row.get("playoff", "")))
        season_id = str(row.get("season_id", "")).strip()
        if context is None or not season_id:
            continue
        draft_year, regular_season, season = context
        if not start_year <= draft_year <= end_year:
            continue
        stage = "regular" if regular_season else "playoffs"
        for position in ("skaters", "goalies"):
            cache_name = (
                f"ushl_{season.replace('-', '_')}_s{season_id}_{stage}_{position}.json"
            )
            cache_path = Path(cache_root) / cache_name
            stat_source = UShlStatSource(
                season=season,
                season_id=season_id,
                regular_season=regular_season,
                position=position,
            )
            discovered.append(
                LeagueSourceSpec(
                    source_id=f"{draft_year}-ushl-{stage}-{position}",
                    enabled=cache_path.is_file(),
                    draft_year=draft_year,
                    adapter="ushl",
                    league="USHL",
                    season=season,
                    regular_season=regular_season,
                    source_url=ushl_source_url(stat_source),
                    cache_path=cache_path,
                    source_label=f"{season_id}:{position}",
                )
            )
    return sorted(discovered, key=lambda source: (source.draft_year, source.source_id))


def ushl_season_context(name: str, playoff: str) -> tuple[int, bool, str] | None:
    if "preseason" in name.casefold() or "pre-season" in name.casefold():
        return None
    match = re.fullmatch(r"(20\d{2})-(\d{2})(?:\s+Playoffs)?", name.strip(), re.IGNORECASE)
    if not match:
        return None
    start_year = int(match.group(1))
    season = f"{start_year}-{match.group(2)}"
    regular_season = playoff != "1" and "playoff" not in name.casefold()
    return start_year + 1, regular_season, season


def collect_ushl_season_catalog(
    output_path: str | Path,
    *,
    refresh: bool = False,
) -> Path:
    path = Path(output_path)
    if path.is_file() and not refresh:
        validate_ushl_season_catalog(path)
        return path
    request = Request(
        USHL_SEASON_CATALOG_URL,
        headers={"User-Agent": "draft-room-intelligence/0.1"},
    )
    with urlopen(request, timeout=45) as response:  # noqa: S310 - fixed public USHL endpoint
        payload = response.read()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    try:
        validate_ushl_season_catalog(temporary)
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return path


def validate_ushl_season_catalog_payload(payload: object) -> None:
    if not isinstance(payload, dict):
        raise ValueError("USHL season catalog must be a JSON object")
    sitekit = payload.get("SiteKit")
    seasons = sitekit.get("Seasons") if isinstance(sitekit, dict) else None
    if not isinstance(seasons, list) or not seasons:
        raise ValueError("USHL season catalog has no seasons")


def validate_ushl_season_catalog(path: str | Path) -> None:
    validate_ushl_season_catalog_payload(json.loads(Path(path).read_text(encoding="utf-8")))


def merge_league_source_specs(
    existing: list[LeagueSourceSpec],
    discovered: list[LeagueSourceSpec],
    *,
    adapter: str,
) -> list[LeagueSourceSpec]:
    retained = [source for source in existing if source.adapter != adapter]
    return sorted(
        retained + discovered,
        key=lambda source: (source.draft_year, source.adapter, source.source_id),
    )


def write_league_source_manifest(
    output_path: str | Path,
    sources: list[LeagueSourceSpec],
    *,
    project_root: str | Path,
) -> Path:
    root = Path(project_root).resolve()
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEAGUE_SOURCE_FIELDS, lineterminator="\n")
        writer.writeheader()
        for source in sorted(sources, key=lambda row: (row.draft_year, row.adapter, row.source_id)):
            try:
                cache_path = source.cache_path.resolve().relative_to(root)
            except ValueError:
                cache_path = source.cache_path
            writer.writerow(
                {
                    "source_id": source.source_id,
                    "enabled": "true" if source.enabled else "false",
                    "draft_year": source.draft_year,
                    "adapter": source.adapter,
                    "league": source.league,
                    "season": source.season,
                    "stage": "regular" if source.regular_season else "playoffs",
                    "source_url": source.source_url,
                    "cache_path": cache_path,
                    "source_label": source.source_label,
                }
            )
    return path


def load_league_source_manifest(
    manifest_path: str | Path,
    *,
    project_root: str | Path,
) -> list[LeagueSourceSpec]:
    root = Path(project_root).resolve()
    with Path(manifest_path).open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    sources: list[LeagueSourceSpec] = []
    seen: set[str] = set()
    for row_number, row in enumerate(rows, start=2):
        source_id = (row.get("source_id") or "").strip()
        if not source_id or source_id in seen:
            raise ValueError(f"missing or duplicate source_id on manifest row {row_number}")
        seen.add(source_id)
        adapter = (row.get("adapter") or "").strip().lower()
        if adapter not in SUPPORTED_ADAPTERS:
            raise ValueError(f"unsupported adapter {adapter!r} on manifest row {row_number}")
        cache_text = (row.get("cache_path") or "").strip()
        if not cache_text:
            raise ValueError(f"missing cache_path on manifest row {row_number}")
        cache_path = Path(cache_text).expanduser()
        sources.append(
            LeagueSourceSpec(
                source_id=source_id,
                enabled=parse_bool(row.get("enabled", "true")),
                draft_year=int((row.get("draft_year") or "0").strip()),
                adapter=adapter,
                league=(row.get("league") or "").strip(),
                season=(row.get("season") or "").strip(),
                regular_season=parse_stage(row.get("stage"), row_number),
                source_url=(row.get("source_url") or "").strip(),
                cache_path=cache_path if cache_path.is_absolute() else root / cache_path,
                source_label=(row.get("source_label") or adapter).strip(),
            )
        )
    return sorted(sources, key=lambda row: (row.draft_year, row.adapter, row.source_id))


def filter_league_sources(
    sources: list[LeagueSourceSpec],
    *,
    start_year: int | None = None,
    end_year: int | None = None,
    include_disabled: bool = False,
) -> list[LeagueSourceSpec]:
    return [
        source
        for source in sources
        if (source.enabled or include_disabled)
        and (start_year is None or source.draft_year >= start_year)
        and (end_year is None or source.draft_year <= end_year)
    ]


def collect_league_sources(
    sources: list[LeagueSourceSpec],
    *,
    refresh: bool = False,
    continue_on_error: bool = True,
) -> list[LeagueSourceCollectionResult]:
    results: list[LeagueSourceCollectionResult] = []
    for source in sources:
        try:
            if source.cache_path.is_file() and not refresh:
                try:
                    validate_source_cache(source)
                    status = "cached"
                except ValueError:
                    status = download_league_source(source, "refreshed_invalid_cache")
            else:
                status = download_league_source(source, "downloaded")
            results.append(
                LeagueSourceCollectionResult(
                    source.source_id,
                    source.draft_year,
                    status,
                    str(source.cache_path),
                    source.cache_path.stat().st_size,
                    "source cache is ready",
                )
            )
        except Exception as exc:
            results.append(
                LeagueSourceCollectionResult(
                    source.source_id,
                    source.draft_year,
                    "failed",
                    str(source.cache_path),
                    0,
                    f"{type(exc).__name__}: {exc}",
                )
            )
            if not continue_on_error:
                raise
    return results


def download_league_source(source: LeagueSourceSpec, status: str) -> str:
    if not source.source_url:
        raise ValueError("source_url is empty and cache is missing or invalid")
    request = Request(
        source.source_url,
        headers={"User-Agent": "draft-room-intelligence/0.1"},
    )
    with urlopen(request, timeout=45) as response:  # noqa: S310 - reviewed manifest URL
        payload = response.read()
    if not payload:
        raise ValueError("download returned an empty response")
    source.cache_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = source.cache_path.with_suffix(source.cache_path.suffix + ".tmp")
    temporary.write_bytes(payload)
    try:
        validate_source_cache(source, path=temporary)
        temporary.replace(source.cache_path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return status


def validate_source_cache(source: LeagueSourceSpec, *, path: Path | None = None) -> None:
    cache_path = path or source.cache_path
    if not cache_path.is_file() or cache_path.stat().st_size == 0:
        raise ValueError("source cache is missing or empty")
    if source.adapter == "ushl":
        validate_ushl_stats_cache(cache_path, source)
        return
    if source.adapter != "chl":
        return
    raw = cache_path.read_text(encoding="utf-8")
    if 'id="topskaters"' not in raw and 'id="topgoalies"' not in raw:
        raise ValueError("CHL cache has no player or goalie statistics table")
    title_match = re.search(r"<title>(.*?)</title>", raw, re.IGNORECASE | re.DOTALL)
    if not title_match:
        return
    title = re.sub(r"\s+", " ", html.unescape(title_match.group(1))).casefold()
    looks_like_playoffs = "playoff" in title or "séries éliminatoires" in title
    if source.regular_season and looks_like_playoffs:
        raise ValueError("CHL cache title indicates playoffs for a regular-season source")
    if not source.regular_season and not looks_like_playoffs:
        raise ValueError("CHL cache title does not indicate playoffs")


def validate_ushl_stats_cache(path: Path, source: LeagueSourceSpec) -> None:
    try:
        payload = parse_json_or_jsonp(path.read_text(encoding="utf-8"))
        sections = payload[0].get("sections", []) if payload else []
        section = sections[0] if sections else {}
        headers = section.get("headers", {}) if isinstance(section, dict) else {}
        rows = section.get("data", []) if isinstance(section, dict) else []
    except (json.JSONDecodeError, TypeError, IndexError) as exc:
        raise ValueError("USHL cache is not a valid HockeyTech player payload") from exc
    if not isinstance(rows, list) or not isinstance(headers, dict):
        raise ValueError("USHL cache has no player statistics section")
    position = source.source_label.partition(":")[2] or "skaters"
    required = {"name", "player_id", "games_played"}
    role_fields = (
        {"save_percentage", "goals_against_average"}
        if position == "goalies"
        else {"points"}
    )
    if not required | role_fields <= set(headers):
        raise ValueError(f"USHL cache headers do not match {position} feed")


def enrich_draft_class_leagues(
    class_root: str | Path,
    sources: list[LeagueSourceSpec],
    *,
    force: bool = False,
) -> LeagueEnrichmentResult:
    root = Path(class_root)
    final_dir = root / "final"
    draft_year = sources[0].draft_year if sources else int(root.name)
    enabled_sources = [source for source in sources if source.enabled]
    if not enabled_sources:
        return coverage_result(
            final_dir,
            draft_year,
            "not_configured",
            0,
            "no enabled league sources",
        )
    wrong_years = {source.draft_year for source in enabled_sources} - {draft_year}
    if wrong_years:
        raise ValueError(f"source years do not match class {draft_year}: {sorted(wrong_years)}")
    missing = [source.source_id for source in enabled_sources if not source.cache_path.is_file()]
    if missing:
        return coverage_result(
            final_dir,
            draft_year,
            "blocked",
            len(enabled_sources),
            "missing source caches: " + ", ".join(missing),
        )
    if not (final_dir / "players.csv").is_file():
        return coverage_result(
            final_dir,
            draft_year,
            "blocked",
            len(enabled_sources),
            "missing normalized class final dataset",
        )
    fingerprint = enrichment_fingerprint(root, enabled_sources)
    state_path = root / ENRICHMENT_STATE_FILE
    if not force and state_matches(state_path, fingerprint):
        return coverage_result(
            final_dir,
            draft_year,
            "skipped_complete",
            len(enabled_sources),
            "source fingerprint matches completed enrichment",
        )

    work_root = root.parent / f".{root.name}.league-enrichment-tmp"
    if work_root.exists():
        shutil.rmtree(work_root)
    work_root.mkdir(parents=True)
    current = final_dir
    try:
        stage_number = 0
        for adapter in SUPPORTED_ADAPTERS:
            adapter_sources = [source for source in enabled_sources if source.adapter == adapter]
            if not adapter_sources:
                continue
            stage_number += 1
            target = work_root / f"stage-{stage_number}-{adapter}"
            apply_adapter(current, target, adapter, adapter_sources)
            current = target
        replace_directory(current, final_dir)
        state = {
            "draft_year": draft_year,
            "pipeline_version": PIPELINE_VERSION,
            "source_fingerprint": fingerprint,
            "sources": [source.source_id for source in enabled_sources],
        }
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    finally:
        if work_root.exists():
            shutil.rmtree(work_root)
    return coverage_result(
        final_dir,
        draft_year,
        "completed",
        len(enabled_sources),
        "league sources applied",
    )


def run_league_enrichment_range(
    class_root: str | Path,
    sources: list[LeagueSourceSpec],
    *,
    report_dir: str | Path,
    start_year: int,
    end_year: int,
    force: bool = False,
    continue_on_error: bool = True,
) -> LeagueEnrichmentReport:
    by_year: dict[int, list[LeagueSourceSpec]] = {}
    for source in sources:
        by_year.setdefault(source.draft_year, []).append(source)
    results: list[LeagueEnrichmentResult] = []
    for year in range(start_year, end_year + 1):
        try:
            results.append(
                enrich_draft_class_leagues(
                    Path(class_root) / str(year),
                    by_year.get(year, []),
                    force=force,
                )
            )
        except Exception as exc:
            results.append(
                coverage_result(
                    Path(class_root) / str(year) / "final",
                    year,
                    "failed",
                    len(by_year.get(year, [])),
                    f"{type(exc).__name__}: {exc}",
                )
            )
            if not continue_on_error:
                write_league_enrichment_report(report_dir, LeagueEnrichmentReport(tuple(results)))
                raise
        write_league_enrichment_report(report_dir, LeagueEnrichmentReport(tuple(results)))
    report = LeagueEnrichmentReport(tuple(results))
    write_league_enrichment_report(report_dir, report)
    return report


def apply_adapter(
    source_dir: Path,
    target_dir: Path,
    adapter: str,
    sources: list[LeagueSourceSpec],
) -> None:
    if adapter == "chl":
        enrich_chl_stats(
            source_dir,
            target_dir,
            [
                ChlStatSource(
                    league=source.league,
                    season=source.season,
                    source_url=source.source_url,
                    regular_season=source.regular_season,
                    source_path=source.cache_path,
                )
                for source in sources
            ],
        )
    elif adapter == "ushl":
        enrich_ushl_stats(
            source_dir,
            target_dir,
            [
                UShlStatSource(
                    season=source.season,
                    season_id=source.source_label.partition(":")[0],
                    regular_season=source.regular_season,
                    source_url=source.source_url or None,
                    source_path=source.cache_path,
                    position=source.source_label.partition(":")[2] or "skaters",
                )
                for source in sources
            ],
        )
    elif adapter == "open_csv":
        enrich_open_stats_csv(
            source_dir,
            target_dir,
            [
                OpenStatsCsvSource(
                    path=source.cache_path,
                    source=source.source_label,
                    season=source.season,
                    league=source.league,
                    regular_season=source.regular_season,
                )
                for source in sources
            ],
        )
    else:  # pragma: no cover - manifest validation guards this branch
        raise ValueError(f"unsupported adapter: {adapter}")


def coverage_result(
    final_dir: Path,
    draft_year: int,
    status: str,
    source_count: int,
    detail: str,
) -> LeagueEnrichmentResult:
    players = read_optional_csv(final_dir / "players.csv")
    stats = read_optional_csv(final_dir / "season_stat_lines.csv")
    pre_draft = [row for row in stats if row.get("timing") == "pre_draft"]
    covered_ids = {row.get("player_id", "") for row in pre_draft if row.get("player_id")}
    leagues = {row.get("league", "") for row in pre_draft if row.get("league")}
    coverage = (100 * len(covered_ids) / len(players)) if players else 0.0
    return LeagueEnrichmentResult(
        draft_year,
        status,
        source_count,
        len(players),
        len(covered_ids),
        len(stats),
        len(leagues),
        round(coverage, 1),
        detail,
    )


def write_league_enrichment_report(
    report_dir: str | Path,
    report: LeagueEnrichmentReport,
) -> dict[str, Path]:
    root = Path(report_dir)
    root.mkdir(parents=True, exist_ok=True)
    csv_path = root / "league_enrichment_runs.csv"
    json_path = root / "league_enrichment_runs.json"
    summary_path = root / "summary.md"
    rows = [asdict(result) for result in report.results]
    fields = list(LeagueEnrichmentResult.__dataclass_fields__)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    json_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    lines = [
        "# League Enrichment Report",
        "",
        f"- Classes: {len(rows)}",
        f"- Failed: {report.failed_count}",
        "",
        "| Year | Status | Sources | Players covered | Coverage | Stat lines | Leagues | Detail |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in report.results:
        lines.append(
            f"| {row.draft_year} | {row.status} | {row.source_count} | "
            f"{row.pre_draft_players}/{row.player_count} | {row.coverage_pct:.1f}% | "
            f"{row.stat_line_count} | {row.league_count} | {row.detail} |"
        )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"csv": csv_path, "json": json_path, "summary": summary_path}


def enrichment_fingerprint(class_root: Path, sources: list[LeagueSourceSpec]) -> str:
    baseline_state = class_root / "etl_state.json"
    payload = {
        "pipeline_version": PIPELINE_VERSION,
        "baseline_state": file_digest(baseline_state) if baseline_state.is_file() else "",
        "sources": [
            {
                "config": {
                    "source_id": source.source_id,
                    "adapter": source.adapter,
                    "league": source.league,
                    "season": source.season,
                    "regular_season": source.regular_season,
                    "source_url": source.source_url,
                    "source_label": source.source_label,
                },
                "digest": file_digest(source.cache_path),
            }
            for source in sources
        ],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def state_matches(path: Path, fingerprint: str) -> bool:
    if not path.is_file():
        return False
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        state.get("pipeline_version") == PIPELINE_VERSION
        and state.get("source_fingerprint") == fingerprint
    )


def replace_directory(source: Path, target: Path) -> None:
    previous = target.parent / f".{target.name}.league-previous"
    if previous.exists():
        shutil.rmtree(previous)
    target.replace(previous)
    try:
        source.replace(target)
    except Exception:
        previous.replace(target)
        raise
    shutil.rmtree(previous)


def read_optional_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_bool(value: str | None) -> bool:
    normalized = (value or "").strip().lower()
    if normalized in {"1", "true", "yes", "y"}:
        return True
    if normalized in {"0", "false", "no", "n"}:
        return False
    raise ValueError(f"invalid boolean value: {value!r}")


def parse_stage(value: str | None, row_number: int) -> bool:
    normalized = (value or "regular").strip().lower()
    if normalized == "regular":
        return True
    if normalized in {"playoff", "playoffs", "postseason"}:
        return False
    raise ValueError(f"invalid stage on manifest row {row_number}: {value!r}")
