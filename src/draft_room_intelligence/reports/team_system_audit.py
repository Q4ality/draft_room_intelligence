"""League-wide team-system audit for demo roster-fit data."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

from draft_room_intelligence.data.team_rosters import RosterPlayer, load_roster_csv, role_bucket


BUCKETS = ["center", "wing", "defense", "goalie"]


@dataclass(frozen=True)
class TeamSystemAudit:
    team_rows: list[dict[str, str]]
    goalie_rows: list[dict[str, str]]
    flag_rows: list[dict[str, str]]


def write_team_system_audit(roster_csv: str | Path, demo_output_dir: str | Path, output_dir: str | Path) -> TeamSystemAudit:
    players = load_roster_csv(roster_csv)
    demo_dir = Path(demo_output_dir)
    player_details = read_json(demo_dir / "players.json")
    manifest = read_json(demo_dir / "manifest.json")
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    team_names = team_name_map(players, manifest)
    team_rows = build_team_bucket_rows(players, player_details, team_names)
    goalie_rows = build_goalie_rows(players, player_details, team_names)
    flag_rows = build_flag_rows(team_rows, goalie_rows)

    write_csv(output_path / "team_bucket_audit.csv", team_rows)
    write_csv(output_path / "goalie_audit.csv", goalie_rows)
    write_csv(output_path / "review_flags.csv", flag_rows)
    (output_path / "summary.md").write_text(format_summary(team_rows, goalie_rows, flag_rows), encoding="utf-8")

    return TeamSystemAudit(team_rows=team_rows, goalie_rows=goalie_rows, flag_rows=flag_rows)


def build_team_bucket_rows(
    players: list[RosterPlayer],
    player_details: list[dict[str, object]],
    team_names: dict[str, str],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for team_id in sorted(team_names):
        team_players = [player for player in players if player.team_id == team_id]
        for bucket in BUCKETS:
            bucket_players = [player for player in team_players if player.role_bucket == bucket]
            young_players = [player for player in bucket_players if 0 < player.age < 25]
            nhl_ready_young = [player for player in young_players if player.league_level == "NHL" and player.games >= 20]
            ahl_pipeline_young = [player for player in young_players if player.league_level == "AHL"]
            non_nhl_young = [player for player in young_players if player.league_level != "NHL"]
            top_options = top_team_options(player_details, team_id, bucket)
            max_fit = float(top_options[0].get("score", 0.0)) if top_options else 0.0
            max_pipeline = float(top_options[0].get("pipeline_need_score", 0.0)) if top_options else 0.0
            row = {
                "team_id": team_id,
                "team_name": team_names[team_id],
                "role_bucket": bucket,
                "total_players": str(len(bucket_players)),
                "nhl_players": str(sum(1 for player in bucket_players if player.league_level == "NHL")),
                "ahl_players": str(sum(1 for player in bucket_players if player.league_level == "AHL")),
                "u25_players": str(len(young_players)),
                "u23_players": str(sum(1 for player in young_players if player.age < 23)),
                "nhl_ready_u25": str(len(nhl_ready_young)),
                "ahl_pipeline_u25": str(len(ahl_pipeline_young)),
                "non_nhl_u25": str(len(non_nhl_young)),
                "short_sample_u25": str(sum(1 for player in young_players if player.games <= 10)),
                "young_core": "; ".join(format_player(player) for player in sort_players_for_core(young_players)[:8]),
                "nhl_ready_young_core": "; ".join(format_player(player) for player in sort_players_for_core(nhl_ready_young)[:8]),
                "ahl_pipeline_young_core": "; ".join(format_player(player) for player in sort_players_for_core(ahl_pipeline_young)[:8]),
                "max_demo_fit_score": f"{max_fit:.3f}",
                "max_demo_pipeline_score": f"{max_pipeline:.3f}",
                "top_demo_matches": "; ".join(format_option(option) for option in top_options[:5]),
                "review_flags": "",
            }
            row["review_flags"] = "; ".join(bucket_flags(row))
            rows.append(row)
    return rows


def build_goalie_rows(
    players: list[RosterPlayer],
    player_details: list[dict[str, object]],
    team_names: dict[str, str],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for team_id in sorted(team_names):
        goalies = [player for player in players if player.team_id == team_id and player.role_bucket == "goalie"]
        young_goalies = [player for player in goalies if 0 < player.age < 25]
        nhl_goalies = [player for player in goalies if player.league_level == "NHL"]
        ahl_goalies = [player for player in goalies if player.league_level == "AHL"]
        goalie_options = top_team_options(player_details, team_id, "goalie")
        max_fit = float(goalie_options[0].get("score", 0.0)) if goalie_options else 0.0
        row = {
            "team_id": team_id,
            "team_name": team_names[team_id],
            "goalies_total": str(len(goalies)),
            "nhl_goalies": "; ".join(format_player(player) for player in sort_goalies(nhl_goalies)),
            "ahl_goalies": "; ".join(format_player(player) for player in sort_goalies(ahl_goalies)[:8]),
            "u25_goalies": str(len(young_goalies)),
            "u25_goalie_names": "; ".join(format_player(player) for player in sort_goalies(young_goalies)[:8]),
            "avg_save_percentage": f"{average_goalie_metric(goalies, 'goalie_save_percentage'):.3f}"
            if average_goalie_metric(goalies, "goalie_save_percentage")
            else "",
            "avg_goals_against_average": f"{average_goalie_metric(goalies, 'goalie_goals_against_average'):.2f}"
            if average_goalie_metric(goalies, "goalie_goals_against_average")
            else "",
            "total_goalie_wins": str(sum(player.goalie_wins for player in goalies) or ""),
            "total_goalie_shutouts": str(sum(player.goalie_shutouts for player in goalies) or ""),
            "low_nhl_game_young_goalies": "; ".join(
                format_player(player)
                for player in sort_goalies([player for player in nhl_goalies if player.age < 24.5 and player.games <= 10])
            ),
            "max_demo_goalie_fit_score": f"{max_fit:.3f}",
            "top_demo_goalie_matches": "; ".join(format_option(option) for option in goalie_options[:5]),
            "review_flags": "",
        }
        row["review_flags"] = "; ".join(goalie_flags(row))
        rows.append(row)
    return rows


def build_flag_rows(team_rows: list[dict[str, str]], goalie_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in team_rows:
        for flag in split_flags(row["review_flags"]):
            rows.append(flag_row(row["team_id"], row["team_name"], row["role_bucket"], flag))
    for row in goalie_rows:
        for flag in split_flags(row["review_flags"]):
            rows.append(flag_row(row["team_id"], row["team_name"], "goalie_assignment", flag))
    return sorted(rows, key=lambda row: (severity_rank(row["severity"]), row["team_id"], row["issue_type"]))


def bucket_flags(row: dict[str, str]) -> list[str]:
    bucket = row["role_bucket"]
    u25 = int(row["u25_players"])
    nhl_ready_u25 = int(row["nhl_ready_u25"])
    non_nhl_u25 = int(row["non_nhl_u25"])
    total = int(row["total_players"])
    max_fit = float(row["max_demo_fit_score"])
    short_sample = int(row["short_sample_u25"])
    flags = []
    saturated = (
        (bucket == "goalie" and u25 >= 2)
        or (bucket == "center" and u25 >= 3)
        or (bucket == "wing" and u25 >= 6)
        or (bucket == "defense" and u25 >= 4)
    )
    thin = (
        (bucket == "goalie" and u25 == 0)
        or (bucket == "center" and u25 <= 1)
        or (bucket == "wing" and u25 <= 2)
        or (bucket == "defense" and u25 <= 1)
    )
    if saturated and max_fit >= 0.65:
        flags.append("high_fit_despite_saturated_u25_pipeline")
    if nhl_ready_u25 >= 2 and max_fit >= 0.60:
        flags.append("high_fit_despite_nhl_ready_u25_pipeline")
    if non_nhl_u25 >= 2 and max_fit >= 0.60:
        flags.append("high_fit_despite_ahl_prospect_pipeline")
    if saturated:
        flags.append("saturated_u25_pipeline")
    if thin and max_fit < 0.45:
        flags.append("thin_pipeline_but_low_demo_fit")
    if short_sample >= 2 and total >= 8:
        flags.append("u25_pipeline_has_short_ahl_samples")
    return flags


def goalie_flags(row: dict[str, str]) -> list[str]:
    flags = []
    u25 = int(row["u25_goalies"])
    max_fit = float(row["max_demo_goalie_fit_score"])
    if u25 >= 2 and max_fit >= 0.60:
        flags.append("goalie_fit_high_despite_multiple_u25_goalies")
    if row["low_nhl_game_young_goalies"]:
        flags.append("young_low_nhl_game_goalie_assignment_check")
    if not row["u25_goalie_names"] and max_fit < 0.45:
        flags.append("thin_goalie_pipeline_but_low_demo_fit")
    return flags


def top_team_options(
    player_details: list[dict[str, object]],
    team_id: str,
    bucket: str,
) -> list[dict[str, object]]:
    options = []
    for detail in player_details:
        header = detail.get("header", {})
        if bucket_for_position(str(header.get("position", ""))) != bucket:
            continue
        for option in detail.get("team_fit_options", []):
            if option.get("team_id") == team_id:
                options.append({**option, "name": header.get("name", ""), "position": header.get("position", "")})
    return sorted(options, key=lambda option: float(option.get("score", 0.0)), reverse=True)


def format_summary(
    team_rows: list[dict[str, str]],
    goalie_rows: list[dict[str, str]],
    flag_rows: list[dict[str, str]],
) -> str:
    lines = [
        "# NHL System Audit",
        "",
        f"- Teams audited: {len({row['team_id'] for row in team_rows})}",
        f"- Team-bucket rows: {len(team_rows)}",
        f"- Goalie rows: {len(goalie_rows)}",
        f"- Review flags: {len(flag_rows)}",
        "",
        "## Highest Priority Flags",
        "",
    ]
    if not flag_rows:
        lines.append("- No review flags generated.")
    for row in flag_rows[:30]:
        lines.append(
            f"- **{row['severity']}** {row['team_id']} {row['role_bucket']}: {row['issue_type']}"
        )

    lines.extend(["", "## Saturated U25 Pipelines", ""])
    saturated_rows = [row for row in team_rows if "saturated_u25_pipeline" in row["review_flags"]]
    for row in saturated_rows[:40]:
        lines.append(
            f"- {row['team_id']} {row['role_bucket']}: U25 {row['u25_players']} / total "
            f"{row['total_players']}; max fit {row['max_demo_fit_score']}; {row['young_core']}"
        )

    lines.extend(["", "## Goalie Assignment Checks", ""])
    goalie_checks = [row for row in goalie_rows if row["review_flags"]]
    for row in goalie_checks[:40]:
        lines.append(
            f"- {row['team_id']}: U25 goalies {row['u25_goalies']}; max fit "
            f"{row['max_demo_goalie_fit_score']}; flags {row['review_flags']}; "
            f"{row['u25_goalie_names']}"
        )
    return "\n".join(lines) + "\n"


def flag_row(team_id: str, team_name: str, bucket: str, issue_type: str) -> dict[str, str]:
    return {
        "team_id": team_id,
        "team_name": team_name,
        "role_bucket": bucket,
        "issue_type": issue_type,
        "severity": issue_severity(issue_type),
    }


def issue_severity(issue_type: str) -> str:
    if issue_type in {"high_fit_despite_saturated_u25_pipeline", "goalie_fit_high_despite_multiple_u25_goalies"}:
        return "high"
    if issue_type == "high_fit_despite_nhl_ready_u25_pipeline":
        return "high"
    if issue_type in {"young_low_nhl_game_goalie_assignment_check", "thin_pipeline_but_low_demo_fit"}:
        return "medium"
    return "low"


def severity_rank(severity: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}.get(severity, 3)


def split_flags(value: str) -> list[str]:
    return [flag.strip() for flag in value.split(";") if flag.strip()]


def team_name_map(players: list[RosterPlayer], manifest: dict[str, object]) -> dict[str, str]:
    names = {player.team_id: player.team_name for player in players}
    for row in manifest.get("team_contexts", []):
        team_id = str(row.get("team_id", ""))
        if team_id:
            names[team_id] = str(row.get("team_name", team_id))
    return names


def sort_players_for_core(players: list[RosterPlayer]) -> list[RosterPlayer]:
    return sorted(players, key=lambda player: (player.age or 99.0, -player.games, player.player_name))


def sort_goalies(players: list[RosterPlayer]) -> list[RosterPlayer]:
    return sorted(players, key=lambda player: (player.league_level != "NHL", player.age or 99.0, -player.games))


def format_player(player: RosterPlayer) -> str:
    level = player.league_level
    games = f"{player.games} GP" if player.games else "GP n/a"
    age = f"{player.age:.1f}" if player.age else "age n/a"
    if player.role_bucket != "goalie":
        return f"{player.player_name} ({level}, {age}, {games})"
    goalie_parts = [level, age, games]
    if player.goalie_wins:
        goalie_parts.append(f"{player.goalie_wins}W")
    if player.goalie_save_percentage is not None:
        goalie_parts.append(f"{player.goalie_save_percentage:.3f} SV%")
    if player.goalie_goals_against_average is not None:
        goalie_parts.append(f"{player.goalie_goals_against_average:.2f} GAA")
    if player.goalie_shutouts:
        goalie_parts.append(f"{player.goalie_shutouts} SO")
    return f"{player.player_name} ({', '.join(goalie_parts)})"


def average_goalie_metric(players: list[RosterPlayer], field: str) -> float:
    values = [(getattr(player, field), player.games) for player in players if getattr(player, field) is not None]
    weight_sum = sum(weight for _, weight in values if weight > 0)
    if not values:
        return 0.0
    if not weight_sum:
        return sum(float(value) for value, _ in values) / len(values)
    return sum(float(value) * weight for value, weight in values if weight > 0) / weight_sum


def format_option(option: dict[str, object]) -> str:
    score = float(option.get("score", 0.0))
    pipeline = float(option.get("pipeline_need_score", 0.0))
    return f"{option.get('name', '')} ({option.get('position', '')}, fit {score:.2f}, pipe {pipeline:.2f})"


def bucket_for_position(position: str) -> str:
    normalized = position.strip().upper()
    if normalized == "G":
        return "goalie"
    if normalized.endswith("D") or normalized == "D":
        return "defense"
    if normalized == "C":
        return "center"
    return "wing"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
