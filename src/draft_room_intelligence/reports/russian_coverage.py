"""Audit KHL, VHL, and MHL coverage for one normalized draft class."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from draft_room_intelligence.data.chl_stats import read_table

RUSSIAN_LEAGUES = ("KHL", "VHL", "MHL")
RUSSIAN_NATIONALITIES = {"RUS", "RUSSIA", "RUSSIAN FEDERATION"}

REVIEW_COLUMNS = [
    "player_id",
    "name",
    "position",
    "nationality",
    "drafted_from_league",
    "coverage_status",
    "stat_lines",
    "regular_games",
    "playoff_games",
    "khl_games",
    "vhl_games",
    "mhl_games",
    "leagues",
    "source_urls",
]


@dataclass(frozen=True)
class RussianCoverageReport:
    draft_year: int
    russian_players: int
    russian_league_targets: int
    covered_players: int
    external_league_players: int
    missing_players: int
    russian_league_players: int
    stat_lines: int
    playoff_players: int
    review_rows: tuple[dict[str, str], ...]

    @property
    def coverage_pct(self) -> float:
        if not self.russian_league_targets:
            return 0.0
        return 100 * self.covered_players / self.russian_league_targets


def write_russian_coverage_report(
    dataset_dir: str | Path,
    output_dir: str | Path,
    *,
    draft_year: int,
) -> RussianCoverageReport:
    report = build_russian_coverage_report(dataset_dir, draft_year=draft_year)
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    write_csv(root / "review_queue.csv", REVIEW_COLUMNS, list(report.review_rows))
    (root / "summary.md").write_text(format_russian_coverage_report(report), encoding="utf-8")
    return report


def build_russian_coverage_report(
    dataset_dir: str | Path,
    *,
    draft_year: int,
) -> RussianCoverageReport:
    root = Path(dataset_dir)
    players = read_table(root / "players.csv")
    stat_lines = read_table(root / "season_stat_lines.csv")
    selection_path = root / "draft_selections.csv"
    selections = read_table(selection_path) if selection_path.exists() else []
    drafted_league_by_player = {
        row.get("player_id", ""): row.get("drafted_from_league", "") for row in selections
    }
    russian_rows = [row for row in stat_lines if row.get("league") in RUSSIAN_LEAGUES]
    stats_by_player: dict[str, list[dict[str, str]]] = {}
    for row in russian_rows:
        stats_by_player.setdefault(row.get("player_id", ""), []).append(row)

    review_rows: list[dict[str, str]] = []
    russian_player_ids: set[str] = set()
    covered_russian_ids: set[str] = set()
    external_russian_ids: set[str] = set()
    playoff_player_ids: set[str] = set()
    for player in players:
        player_id = player.get("player_id", "")
        rows = stats_by_player.get(player_id, [])
        is_russian = player.get("nationality", "").strip().upper() in RUSSIAN_NATIONALITIES
        if not is_russian and not rows:
            continue
        if is_russian:
            russian_player_ids.add(player_id)
            if rows:
                covered_russian_ids.add(player_id)
        drafted_from_league = drafted_league_by_player.get(player_id, "")
        is_external = bool(
            is_russian
            and not rows
            and drafted_from_league
            and drafted_from_league.upper() not in {*RUSSIAN_LEAGUES, "RUSSIA"}
        )
        if is_external:
            external_russian_ids.add(player_id)
        playoff_games = sum_games(row for row in rows if row.get("regular_season") == "false")
        if playoff_games:
            playoff_player_ids.add(player_id)
        review_rows.append(
            {
                "player_id": player_id,
                "name": player.get("name", ""),
                "position": player.get("position", ""),
                "nationality": player.get("nationality", ""),
                "drafted_from_league": drafted_from_league,
                "coverage_status": (
                    "covered" if rows else "external_league" if is_external else "missing"
                ),
                "stat_lines": str(len(rows)),
                "regular_games": str(
                    sum_games(row for row in rows if row.get("regular_season") != "false")
                ),
                "playoff_games": str(playoff_games),
                "khl_games": str(sum_games(row for row in rows if row.get("league") == "KHL")),
                "vhl_games": str(sum_games(row for row in rows if row.get("league") == "VHL")),
                "mhl_games": str(sum_games(row for row in rows if row.get("league") == "MHL")),
                "leagues": "; ".join(sorted({row.get("league", "") for row in rows})),
                "source_urls": "; ".join(
                    sorted({row.get("source_url", "") for row in rows if row.get("source_url")})
                ),
            }
        )
    status_order = {"missing": 0, "external_league": 1, "covered": 2}
    review_rows.sort(key=lambda row: (status_order[row["coverage_status"]], row["name"]))
    russian_league_targets = russian_player_ids - external_russian_ids
    return RussianCoverageReport(
        draft_year=draft_year,
        russian_players=len(russian_player_ids),
        russian_league_targets=len(russian_league_targets),
        covered_players=len(covered_russian_ids),
        external_league_players=len(external_russian_ids),
        missing_players=len(russian_league_targets - covered_russian_ids),
        russian_league_players=len(stats_by_player),
        stat_lines=len(russian_rows),
        playoff_players=len(playoff_player_ids),
        review_rows=tuple(review_rows),
    )


def sum_games(rows) -> int:
    total = 0
    for row in rows:
        try:
            total += int(float(row.get("games", "") or 0))
        except ValueError:
            continue
    return total


def format_russian_coverage_report(report: RussianCoverageReport) -> str:
    missing = [row for row in report.review_rows if row["coverage_status"] == "missing"]
    lines = [
        f"# Russian League Coverage: {report.draft_year}",
        "",
        f"- Russian prospects: {report.russian_players}",
        f"- Russian-league coverage targets: {report.russian_league_targets}",
        f"- Covered Russian prospects: {report.covered_players}",
        f"- Coverage: {report.coverage_pct:.1f}%",
        f"- Missing Russian prospects: {report.missing_players}",
        f"- External-league Russian prospects: {report.external_league_players}",
        f"- All players with KHL/VHL/MHL evidence: {report.russian_league_players}",
        f"- Russian-family stat lines: {report.stat_lines}",
        f"- Players with playoff evidence: {report.playoff_players}",
        "",
        "## Next Review Queue",
        "",
    ]
    if missing:
        lines.extend(f"- {row['name']} ({row['position']})" for row in missing)
    else:
        lines.append("- No uncovered Russian prospects.")
    return "\n".join(lines) + "\n"


def write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
