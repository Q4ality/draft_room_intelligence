"""Cross-year audit of normalized league evidence and advanced-stat coverage."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from draft_room_intelligence.data.league_standardization import normalize_league_name

SUMMARY_COLUMNS = [
    "draft_year",
    "players",
    "players_with_pre_draft_stats",
    "coverage_pct",
    "stat_lines",
    "advanced_stat_lines",
    "players_with_advanced_stats",
    "unmatched_audit_rows",
    "exact_duplicate_rows",
    "conflicting_stat_keys",
    "partial_advanced_rows",
]

ISSUE_COLUMNS = [
    "draft_year",
    "issue_type",
    "player_id",
    "player_name",
    "season",
    "league",
    "stage",
    "source",
    "detail",
]

MATCH_AUDITS = (
    "chl_stat_matches.csv",
    "ushl_stat_matches.csv",
    "ncaa_stat_matches.csv",
    "europe_stat_matches.csv",
)

MATCH_LEAGUES = {
    "chl_stat_matches.csv": {"OHL", "WHL", "QMJHL"},
    "ushl_stat_matches.csv": {"USHL"},
    "ncaa_stat_matches.csv": {"NCAA"},
    "europe_stat_matches.csv": {
        "SHL",
        "HockeyAllsvenskan",
        "Sweden Jrs.",
        "Liiga",
        "Mestis",
        "Finland Jrs.",
        "KHL",
        "VHL",
        "MHL",
    },
}


@dataclass(frozen=True)
class LeagueAuditYear:
    draft_year: int
    players: int
    players_with_pre_draft_stats: int
    stat_lines: int
    advanced_stat_lines: int
    players_with_advanced_stats: int
    unmatched_audit_rows: int
    exact_duplicate_rows: int
    conflicting_stat_keys: int
    partial_advanced_rows: int

    @property
    def coverage_pct(self) -> float:
        return 100 * self.players_with_pre_draft_stats / self.players if self.players else 0.0

    def to_row(self) -> dict[str, str]:
        return {
            "draft_year": str(self.draft_year),
            "players": str(self.players),
            "players_with_pre_draft_stats": str(self.players_with_pre_draft_stats),
            "coverage_pct": f"{self.coverage_pct:.1f}",
            "stat_lines": str(self.stat_lines),
            "advanced_stat_lines": str(self.advanced_stat_lines),
            "players_with_advanced_stats": str(self.players_with_advanced_stats),
            "unmatched_audit_rows": str(self.unmatched_audit_rows),
            "exact_duplicate_rows": str(self.exact_duplicate_rows),
            "conflicting_stat_keys": str(self.conflicting_stat_keys),
            "partial_advanced_rows": str(self.partial_advanced_rows),
        }


@dataclass(frozen=True)
class LeagueIngestionAudit:
    years: tuple[LeagueAuditYear, ...]
    issues: tuple[dict[str, str], ...]


def write_league_ingestion_audit(
    class_root: str | Path,
    output_dir: str | Path,
    *,
    start_year: int,
    end_year: int,
) -> LeagueIngestionAudit:
    report = build_league_ingestion_audit(
        class_root,
        start_year=start_year,
        end_year=end_year,
    )
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    write_csv(root / "year_summary.csv", SUMMARY_COLUMNS, [year.to_row() for year in report.years])
    write_csv(root / "issues.csv", ISSUE_COLUMNS, list(report.issues))
    (root / "summary.md").write_text(format_league_ingestion_audit(report), encoding="utf-8")
    return report


def build_league_ingestion_audit(
    class_root: str | Path,
    *,
    start_year: int,
    end_year: int,
) -> LeagueIngestionAudit:
    years: list[LeagueAuditYear] = []
    issues: list[dict[str, str]] = []
    for draft_year in range(start_year, end_year + 1):
        final_dir = Path(class_root) / str(draft_year) / "final"
        players = read_csv(final_dir / "players.csv")
        stats = read_csv(final_dir / "season_stat_lines.csv")
        advanced = read_csv(final_dir / "advanced_stat_lines.csv")
        player_names = {row.get("player_id", ""): row.get("name", "") for row in players}
        pre_draft = [row for row in stats if row.get("timing") == "pre_draft"]
        duplicate_issues = exact_duplicate_issues(draft_year, pre_draft, player_names)
        conflict_issues = conflicting_key_issues(draft_year, pre_draft, player_names)
        partial_issues = partial_advanced_issues(
            draft_year,
            pre_draft,
            advanced,
            player_names,
        )
        unmatched = unmatched_match_issues(
            draft_year,
            final_dir,
            player_names,
            player_leagues(pre_draft),
        )
        issues.extend(duplicate_issues + conflict_issues + partial_issues + unmatched)
        years.append(
            LeagueAuditYear(
                draft_year=draft_year,
                players=len(players),
                players_with_pre_draft_stats=len(
                    {row.get("player_id", "") for row in pre_draft if row.get("player_id")}
                ),
                stat_lines=len(pre_draft),
                advanced_stat_lines=len(advanced),
                players_with_advanced_stats=len(
                    {row.get("player_id", "") for row in advanced if row.get("player_id")}
                ),
                unmatched_audit_rows=len(unmatched),
                exact_duplicate_rows=len(duplicate_issues),
                conflicting_stat_keys=len(conflict_issues),
                partial_advanced_rows=len(partial_issues),
            )
        )
    return LeagueIngestionAudit(tuple(years), tuple(issues))


def exact_duplicate_issues(
    draft_year: int,
    stats: list[dict[str, str]],
    player_names: dict[str, str],
) -> list[dict[str, str]]:
    seen: set[tuple[str, ...]] = set()
    issues = []
    for row in stats:
        identity = tuple(row.get(field, "") for field in sorted(row))
        if identity in seen:
            issues.append(
                issue_row(
                    draft_year, "exact_duplicate", row, player_names, "identical normalized row"
                )
            )
        seen.add(identity)
    return issues


def conflicting_key_issues(
    draft_year: int,
    stats: list[dict[str, str]],
    player_names: dict[str, str],
) -> list[dict[str, str]]:
    by_key: dict[tuple[str, str, str, str], list[dict[str, str]]] = {}
    for row in stats:
        by_key.setdefault(conflict_key(row), []).append(row)
    issues = []
    for rows in by_key.values():
        production_rows = [row for row in rows if not has_goalie_evidence(row)]
        values = {
            (
                row.get("games", ""),
                row.get("goals", ""),
                row.get("assists", ""),
                row.get("points", ""),
            )
            for row in production_rows
        }
        if len(values) > 1:
            sources = ", ".join(sorted({row.get("source", "unknown") for row in production_rows}))
            issues.append(
                issue_row(
                    draft_year,
                    "conflicting_stat_key",
                    rows[0],
                    player_names,
                    f"{len(values)} production totals across sources: {sources}",
                )
            )
    return issues


def has_goalie_evidence(row: dict[str, str]) -> bool:
    return any(
        row.get(field, "")
        for field in (
            "goalie_minutes",
            "saves",
            "goals_against",
            "save_percentage",
            "goals_against_average",
        )
    )


def partial_advanced_issues(
    draft_year: int,
    stats: list[dict[str, str]],
    advanced: list[dict[str, str]],
    player_names: dict[str, str],
) -> list[dict[str, str]]:
    standard_games: dict[tuple[str, str, str, str], int] = {}
    for row in stats:
        key = stat_key(row)
        standard_games[key] = max(standard_games.get(key, 0), int_value(row.get("games")))
    issues = []
    for row in advanced:
        advanced_games = int_value(row.get("games"))
        full_games = standard_games.get(stat_key(row), 0)
        if advanced_games and full_games and advanced_games < full_games:
            issues.append(
                issue_row(
                    draft_year,
                    "partial_advanced_sample",
                    row,
                    player_names,
                    f"advanced sample {advanced_games} GP vs season evidence {full_games} GP",
                )
            )
    return issues


def unmatched_match_issues(
    draft_year: int,
    final_dir: Path,
    player_names: dict[str, str],
    leagues_by_player: dict[str, set[str]],
) -> list[dict[str, str]]:
    issues = []
    for filename in MATCH_AUDITS:
        for row in read_csv(final_dir / filename):
            if row.get("matched", "").casefold() != "false":
                continue
            player_id = row.get("player_id", "")
            if not leagues_by_player.get(player_id, set()) & MATCH_LEAGUES[filename]:
                continue
            issues.append(
                {
                    "draft_year": str(draft_year),
                    "issue_type": "unmatched_source_audit",
                    "player_id": player_id,
                    "player_name": row.get("name", "") or player_names.get(player_id, ""),
                    "season": "",
                    "league": "",
                    "stage": "",
                    "source": filename.removesuffix("_matches.csv"),
                    "detail": "no reviewed exact-name source match",
                }
            )
    return issues


def stat_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        row.get("player_id", ""),
        row.get("season", ""),
        normalize_league_name(row.get("league", "")),
        row.get("regular_season", "true").casefold(),
    )


def conflict_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (*stat_key(row), normalize_team(row.get("team", "")))


def player_leagues(stats: list[dict[str, str]]) -> dict[str, set[str]]:
    output: dict[str, set[str]] = {}
    for row in stats:
        output.setdefault(row.get("player_id", ""), set()).add(
            normalize_league_name(row.get("league", ""))
        )
    return output


def normalize_team(value: str) -> str:
    return " ".join(value.casefold().replace("jr.", "").replace("j20", "").split())


def issue_row(
    draft_year: int,
    issue_type: str,
    row: dict[str, str],
    player_names: dict[str, str],
    detail: str,
) -> dict[str, str]:
    player_id = row.get("player_id", "")
    return {
        "draft_year": str(draft_year),
        "issue_type": issue_type,
        "player_id": player_id,
        "player_name": player_names.get(player_id, ""),
        "season": row.get("season", ""),
        "league": normalize_league_name(row.get("league", "")),
        "stage": "regular"
        if row.get("regular_season", "true").casefold() == "true"
        else "playoffs",
        "source": row.get("source", ""),
        "detail": detail,
    }


def format_league_ingestion_audit(report: LeagueIngestionAudit) -> str:
    lines = [
        "# League Ingestion Data-Quality Audit",
        "",
        "| Year | Coverage | Stat rows | Advanced players | Duplicates | Conflicts | "
        "Partial advanced | Unmatched audits |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for year in report.years:
        lines.append(
            f"| {year.draft_year} | {year.players_with_pre_draft_stats}/{year.players} "
            f"({year.coverage_pct:.1f}%) | {year.stat_lines} | "
            f"{year.players_with_advanced_stats} | "
            f"{year.exact_duplicate_rows} | {year.conflicting_stat_keys} | "
            f"{year.partial_advanced_rows} | {year.unmatched_audit_rows} |"
        )
    issue_counts: dict[str, int] = {}
    for issue in report.issues:
        issue_counts[issue["issue_type"]] = issue_counts.get(issue["issue_type"], 0) + 1
    lines.extend(["", "## Issue Counts", ""])
    if issue_counts:
        lines.extend(f"- {key}: {value}" for key, value in sorted(issue_counts.items()))
    else:
        lines.append("- No data-quality issues detected.")
    return "\n".join(lines) + "\n"


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def int_value(raw: object) -> int:
    try:
        return int(float(str(raw)))
    except (TypeError, ValueError):
        return 0
