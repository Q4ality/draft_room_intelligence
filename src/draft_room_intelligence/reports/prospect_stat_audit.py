"""Prospect skater/goalie statistics audit for draft-year datasets."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from draft_room_intelligence.modeling.feature_table import goalie_quality_score
from draft_room_intelligence.reports.demo_export import is_adult_league


PLAYER_COLUMNS = [
    "player_id",
    "name",
    "draft_year",
    "position",
    "role_group",
    "best_rank",
    "ranking_sources",
    "stat_lines",
    "source_count",
    "total_games",
    "goals",
    "assists",
    "points",
    "points_per_game",
    "regular_games",
    "playoff_games",
    "playoff_game_share",
    "adult_games",
    "adult_game_share",
    "league_count",
    "leagues",
    "teams",
    "goalie_games",
    "goalie_minutes",
    "goalie_shots_against",
    "goalie_saves",
    "goalie_goals_against",
    "goalie_save_percentage",
    "goalie_goals_against_average",
    "goalie_wins",
    "goalie_losses",
    "goalie_shutouts",
    "goalie_quality_score",
    "data_quality_flags",
]

GOALIE_COLUMNS = [
    "player_id",
    "name",
    "draft_year",
    "best_rank",
    "stat_lines",
    "goalie_games",
    "goalie_minutes",
    "goalie_shots_against",
    "goalie_saves",
    "goalie_goals_against",
    "goalie_save_percentage",
    "goalie_goals_against_average",
    "goalie_wins",
    "goalie_losses",
    "goalie_shutouts",
    "goalie_quality_score",
    "leagues",
    "teams",
    "data_quality_flags",
]

LEAGUE_COLUMNS = [
    "league",
    "players",
    "stat_lines",
    "games",
    "goals",
    "assists",
    "points",
    "points_per_game",
    "goalie_games",
    "goalie_save_percentage",
    "goalie_goals_against_average",
]

FLAG_COLUMNS = ["player_id", "name", "draft_year", "position", "flag", "detail"]


def write_prospect_stat_audit(output_dir: Path, dataset_dirs: Iterable[Path], draft_year: int | None = None) -> dict[str, int]:
    output_dir.mkdir(parents=True, exist_ok=True)
    loaded = load_source_tables(dataset_dirs, draft_year=draft_year)
    rows = build_player_summary_rows(loaded, draft_year=draft_year)
    goalie_rows = [row for row in rows if row["role_group"] == "goalie"]
    league_rows = build_league_summary_rows(loaded["stat_lines"])
    flag_rows = build_flag_rows(rows)

    write_csv(output_dir / "prospect_stat_summary.csv", PLAYER_COLUMNS, rows)
    write_csv(output_dir / "goalie_stat_summary.csv", GOALIE_COLUMNS, project_rows(goalie_rows, GOALIE_COLUMNS))
    write_csv(output_dir / "league_summary.csv", LEAGUE_COLUMNS, league_rows)
    write_csv(output_dir / "review_flags.csv", FLAG_COLUMNS, flag_rows)
    (output_dir / "summary.md").write_text(format_summary(rows, goalie_rows, league_rows, flag_rows, loaded), encoding="utf-8")

    return {
        "players": len(rows),
        "stat_lines": len(loaded["stat_lines"]),
        "goalies": len(goalie_rows),
        "flags": len(flag_rows),
    }


def load_source_tables(dataset_dirs: Iterable[Path], draft_year: int | None = None) -> dict[str, object]:
    players: dict[str, dict[str, str]] = {}
    rankings: dict[str, list[dict[str, str]]] = defaultdict(list)
    stat_lines: list[dict[str, str]] = []
    stat_line_keys: set[tuple[str, ...]] = set()
    sources: list[str] = []

    for directory in dataset_dirs:
        source_dir = Path(directory)
        sources.append(str(source_dir))
        for row in read_csv_if_exists(source_dir / "players.csv"):
            player_id = row.get("player_id", "").strip()
            if not player_id:
                continue
            players[player_id] = merge_non_empty(players.get(player_id, {}), row)
        for row in read_csv_if_exists(source_dir / "rankings.csv"):
            player_id = row.get("player_id", "").strip()
            if not player_id:
                continue
            if draft_year and not row.get("draft_year"):
                row["draft_year"] = str(draft_year)
            rankings[player_id].append(row)
        for row in read_csv_if_exists(source_dir / "draft_selections.csv"):
            player_id = row.get("player_id", "").strip()
            if not player_id:
                continue
            if row.get("draft_year"):
                rankings[player_id].append(
                    {
                        "player_id": player_id,
                        "draft_year": row.get("draft_year", ""),
                        "rank": row.get("overall_pick", ""),
                        "ranking_source": "draft_selection",
                    }
                )
        for row in read_csv_if_exists(source_dir / "season_stat_lines.csv"):
            player_id = row.get("player_id", "").strip()
            if not player_id:
                continue
            key = stat_line_key(row)
            if key in stat_line_keys:
                continue
            stat_line_keys.add(key)
            stat_lines.append(row)

    return {"players": players, "rankings": dict(rankings), "stat_lines": stat_lines, "sources": sources}


def build_player_summary_rows(loaded: dict[str, object], draft_year: int | None = None) -> list[dict[str, str]]:
    players: dict[str, dict[str, str]] = loaded["players"]  # type: ignore[assignment]
    rankings: dict[str, list[dict[str, str]]] = loaded["rankings"]  # type: ignore[assignment]
    stat_lines: list[dict[str, str]] = loaded["stat_lines"]  # type: ignore[assignment]
    lines_by_player: dict[str, list[dict[str, str]]] = defaultdict(list)
    for line in stat_lines:
        lines_by_player[line.get("player_id", "")].append(line)

    player_ids = set(players) | set(rankings) | set(lines_by_player)
    rows: list[dict[str, str]] = []
    for player_id in sorted(player_ids, key=lambda value: (best_rank(rankings.get(value, [])) or 9999, player_name(value, players))):
        player = players.get(player_id, {})
        lines = lines_by_player.get(player_id, [])
        rank_rows = rankings.get(player_id, [])
        position = first_non_empty(player.get("position", ""), *(row.get("position", "") for row in rank_rows))
        role_group = classify_role_group(position)
        games = sum_int(line.get("games") for line in lines)
        goals = sum_int(line.get("goals") for line in lines)
        assists = sum_int(line.get("assists") for line in lines)
        points = sum_int(line.get("points") for line in lines)
        regular_games = sum_int(line.get("games") for line in lines if parse_bool(line.get("regular_season", "1")))
        playoff_games = max(0, games - regular_games)
        adult_games = sum_int(line.get("games") for line in lines if is_adult_league(line.get("league", "")))
        leagues = sorted({line.get("league", "").strip() for line in lines if line.get("league", "").strip()})
        teams = sorted({line.get("team", "").strip() for line in lines if line.get("team", "").strip()})
        goalie = summarize_goalie_lines(lines)
        flags = player_flags(role_group, lines, games, points, goalie)

        rows.append(
            {
                "player_id": player_id,
                "name": player_name(player_id, players),
                "draft_year": str(resolve_draft_year(rank_rows, draft_year)),
                "position": position,
                "role_group": role_group,
                "best_rank": str(best_rank(rank_rows) or ""),
                "ranking_sources": "; ".join(sorted({row.get("ranking_source", "").strip() for row in rank_rows if row.get("ranking_source", "").strip()})),
                "stat_lines": str(len(lines)),
                "source_count": str(len({line.get("source", "").strip() for line in lines if line.get("source", "").strip()})),
                "total_games": str(games),
                "goals": str(goals),
                "assists": str(assists),
                "points": str(points),
                "points_per_game": format_rate(points, games, 3),
                "regular_games": str(regular_games),
                "playoff_games": str(playoff_games),
                "playoff_game_share": format_float(playoff_games / games if games else 0.0, 3),
                "adult_games": str(adult_games),
                "adult_game_share": format_float(adult_games / games if games else 0.0, 3),
                "league_count": str(len(leagues)),
                "leagues": "; ".join(leagues),
                "teams": "; ".join(teams),
                "goalie_games": str(int(goalie["games"])),
                "goalie_minutes": format_float(goalie["minutes"], 1),
                "goalie_shots_against": str(int(goalie["shots_against"])),
                "goalie_saves": str(int(goalie["saves"])),
                "goalie_goals_against": str(int(goalie["goals_against"])),
                "goalie_save_percentage": format_float(goalie["save_percentage"], 3),
                "goalie_goals_against_average": format_float(goalie["goals_against_average"], 2),
                "goalie_wins": str(int(goalie["wins"])),
                "goalie_losses": str(int(goalie["losses"])),
                "goalie_shutouts": str(int(goalie["shutouts"])),
                "goalie_quality_score": format_float(goalie["quality_score"], 3),
                "data_quality_flags": "; ".join(flags),
            }
        )
    return rows


def summarize_goalie_lines(lines: list[dict[str, str]]) -> dict[str, float]:
    goalie_lines = [
        line
        for line in lines
        if any(
            present(line.get(column, ""))
            for column in (
                "goalie_minutes",
                "shots_against",
                "saves",
                "goals_against",
                "save_percentage",
                "goals_against_average",
                "wins",
                "shutouts",
            )
        )
    ]
    games = sum_int(line.get("games") for line in goalie_lines)
    minutes = sum_float(line.get("goalie_minutes") for line in goalie_lines)
    shots_against = sum_int(line.get("shots_against") for line in goalie_lines)
    saves = sum_int(line.get("saves") for line in goalie_lines)
    goals_against = sum_int(line.get("goals_against") for line in goalie_lines)
    save_percentage = saves / shots_against if shots_against else weighted_average(
        [(parse_float(line.get("save_percentage")), parse_int(line.get("games")) or 1) for line in goalie_lines]
    )
    goals_against_average = goals_against * 60 / minutes if minutes else weighted_average(
        [(parse_float(line.get("goals_against_average")), parse_int(line.get("games")) or 1) for line in goalie_lines]
    )
    return {
        "games": float(games),
        "minutes": minutes,
        "shots_against": float(shots_against),
        "saves": float(saves),
        "goals_against": float(goals_against),
        "save_percentage": save_percentage,
        "goals_against_average": goals_against_average,
        "wins": float(sum_int(line.get("wins") for line in goalie_lines)),
        "losses": float(sum_int(line.get("losses") for line in goalie_lines)),
        "shutouts": float(sum_int(line.get("shutouts") for line in goalie_lines)),
        "quality_score": goalie_quality_score(save_percentage, goals_against_average, games),
    }


def build_league_summary_rows(stat_lines: list[dict[str, str]]) -> list[dict[str, str]]:
    by_league: dict[str, list[dict[str, str]]] = defaultdict(list)
    for line in stat_lines:
        by_league[line.get("league", "").strip() or "Unknown"].append(line)
    rows: list[dict[str, str]] = []
    for league, lines in sorted(by_league.items()):
        games = sum_int(line.get("games") for line in lines)
        points = sum_int(line.get("points") for line in lines)
        goalie = summarize_goalie_lines(lines)
        rows.append(
            {
                "league": league,
                "players": str(len({line.get("player_id", "") for line in lines if line.get("player_id", "")})),
                "stat_lines": str(len(lines)),
                "games": str(games),
                "goals": str(sum_int(line.get("goals") for line in lines)),
                "assists": str(sum_int(line.get("assists") for line in lines)),
                "points": str(points),
                "points_per_game": format_rate(points, games, 3),
                "goalie_games": str(int(goalie["games"])),
                "goalie_save_percentage": format_float(goalie["save_percentage"], 3),
                "goalie_goals_against_average": format_float(goalie["goals_against_average"], 2),
            }
        )
    return rows


def build_flag_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    flag_rows: list[dict[str, str]] = []
    for row in rows:
        flags = [flag.strip() for flag in row["data_quality_flags"].split(";") if flag.strip()]
        for flag in flags:
            flag_rows.append(
                {
                    "player_id": row["player_id"],
                    "name": row["name"],
                    "draft_year": row["draft_year"],
                    "position": row["position"],
                    "flag": flag,
                    "detail": flag_detail(flag),
                }
            )
    return flag_rows


def format_summary(
    rows: list[dict[str, str]],
    goalie_rows: list[dict[str, str]],
    league_rows: list[dict[str, str]],
    flag_rows: list[dict[str, str]],
    loaded: dict[str, object],
) -> str:
    skaters = [row for row in rows if row["role_group"] != "goalie"]
    top_skaters = sorted(
        [row for row in skaters if parse_int(row["total_games"]) >= 10],
        key=lambda row: parse_float(row["points_per_game"]) or 0.0,
        reverse=True,
    )[:10]
    top_goalies = sorted(
        [row for row in goalie_rows if parse_int(row["goalie_games"]) >= 10],
        key=lambda row: parse_float(row["goalie_quality_score"]) or 0.0,
        reverse=True,
    )[:10]
    top_leagues = sorted(league_rows, key=lambda row: parse_int(row["players"]) or 0, reverse=True)[:10]

    lines = [
        "# Prospect Statistics Audit",
        "",
        f"- Source folders: {len(loaded['sources'])}",
        f"- Prospects: {len(rows)}",
        f"- Skaters: {len(skaters)}",
        f"- Goalies: {len(goalie_rows)}",
        f"- Stat lines: {len(loaded['stat_lines'])}",
        f"- Review flags: {len(flag_rows)}",
        "",
        "## Top skater production, minimum 10 GP",
        "",
    ]
    lines.extend(format_rank_lines(top_skaters, "points_per_game", suffix=" PPG", extra_key="leagues"))
    lines.extend(["", "## Top goalie profiles, minimum 10 GP", ""])
    lines.extend(format_rank_lines(top_goalies, "goalie_quality_score", suffix=" quality", extra_key="leagues"))
    lines.extend(["", "## League coverage", ""])
    lines.extend(
        f"- {row['league']}: {row['players']} players, {row['games']} GP, {row['points_per_game']} PPG"
        for row in top_leagues
    )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Goalie save percentage is computed from saves/shots when available; otherwise it uses game-weighted source save percentage.",
            "- Goalie GAA is computed from goals/minutes when available; otherwise it uses game-weighted source GAA.",
            "- Adult-game exposure uses the same league classifier as the demo package.",
        ]
    )
    return "\n".join(lines) + "\n"


def format_rank_lines(rows: list[dict[str, str]], metric_key: str, suffix: str, extra_key: str) -> list[str]:
    if not rows:
        return ["- No qualifying rows."]
    return [
        f"- {row['name']} ({row['position']}): {row[metric_key]}{suffix}; {row['total_games']} GP; {row[extra_key]}"
        for row in rows
    ]


def player_flags(role_group: str, lines: list[dict[str, str]], games: int, points: int, goalie: dict[str, float]) -> list[str]:
    flags: list[str] = []
    if not lines:
        flags.append("missing_stat_lines")
    if games and len(lines) == 1:
        flags.append("low_evidence_single_line")
    if role_group == "goalie":
        if goalie["games"] < 10:
            flags.append("goalie_short_sample")
        if not goalie["save_percentage"] or not goalie["goals_against_average"]:
            flags.append("goalie_missing_save_pct_or_gaa")
    elif games and points == 0:
        flags.append("skater_missing_points")
    if len({line.get("league", "").strip() for line in lines if line.get("league", "").strip()}) >= 3:
        flags.append("multi_league_profile")
    return flags


def classify_role_group(position: str) -> str:
    normalized = position.upper()
    if "G" == normalized or normalized.startswith("G"):
        return "goalie"
    if "D" in normalized:
        return "defense"
    return "forward"


def resolve_draft_year(rank_rows: list[dict[str, str]], draft_year: int | None) -> int | str:
    for row in rank_rows:
        year = parse_int(row.get("draft_year"))
        if year:
            return year
    return draft_year or ""


def best_rank(rank_rows: list[dict[str, str]]) -> int | None:
    ranks = [parse_int(row.get("rank")) for row in rank_rows]
    ranks = [rank for rank in ranks if rank]
    return min(ranks) if ranks else None


def player_name(player_id: str, players: dict[str, dict[str, str]]) -> str:
    row = players.get(player_id, {})
    return first_non_empty(row.get("name", ""), row.get("player_name", ""), player_id)


def flag_detail(flag: str) -> str:
    details = {
        "missing_stat_lines": "No pre-draft season stat rows are present for this player.",
        "low_evidence_single_line": "Only one season/team row is present; source coverage should be checked.",
        "goalie_short_sample": "Goalie sample is below 10 games, so rate stats are fragile.",
        "goalie_missing_save_pct_or_gaa": "Goalie row is missing one of save percentage or goals-against average.",
        "skater_missing_points": "Skater has games but no point production in the current source rows.",
        "multi_league_profile": "Player has three or more leagues and needs cross-league interpretation.",
    }
    return details.get(flag, "")


def stat_line_key(row: dict[str, str]) -> tuple[str, ...]:
    return tuple(
        row.get(column, "").strip()
        for column in (
            "player_id",
            "season",
            "league",
            "team",
            "games",
            "goals",
            "assists",
            "points",
            "regular_season",
            "source",
            "source_id",
        )
    )


def read_csv_if_exists(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def project_rows(rows: list[dict[str, str]], columns: list[str]) -> list[dict[str, str]]:
    return [{column: row.get(column, "") for column in columns} for row in rows]


def merge_non_empty(base: dict[str, str], incoming: dict[str, str]) -> dict[str, str]:
    merged = dict(base)
    for key, value in incoming.items():
        if value and not merged.get(key):
            merged[key] = value
    return merged


def first_non_empty(*values: str) -> str:
    for value in values:
        if value and value.strip():
            return value.strip()
    return ""


def parse_bool(value: str) -> bool:
    return value.strip().lower() not in {"0", "false", "no", "n"}


def parse_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def parse_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def present(value: str) -> bool:
    return value is not None and value.strip() != ""


def sum_int(values: Iterable[str | None]) -> int:
    return sum(parse_int(value) or 0 for value in values)


def sum_float(values: Iterable[str | None]) -> float:
    return sum(parse_float(value) or 0.0 for value in values)


def weighted_average(values: list[tuple[float | None, int]]) -> float:
    numerator = 0.0
    denominator = 0
    for value, weight in values:
        if value is None:
            continue
        numerator += value * max(weight, 1)
        denominator += max(weight, 1)
    return numerator / denominator if denominator else 0.0


def format_float(value: float, digits: int) -> str:
    if value == 0:
        return ""
    return f"{value:.{digits}f}"


def format_rate(numerator: int, denominator: int, digits: int) -> str:
    if not denominator:
        return ""
    return f"{numerator / denominator:.{digits}f}"
