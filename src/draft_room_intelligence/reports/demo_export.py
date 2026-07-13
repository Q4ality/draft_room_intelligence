"""Build demo-ready board and player-detail exports from a draft class."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

from draft_room_intelligence.domain import HistoricalProspect
from draft_room_intelligence.evaluation.baselines import (
    consensus_scores,
    role_specific_hybrid_scores,
)
from draft_room_intelligence.modeling.feature_table import build_feature_rows


BOARD_COLUMNS = [
    "player_id",
    "draft_year",
    "board_rank",
    "name",
    "position",
    "role_group",
    "nationality",
    "age_at_draft",
    "height_cm",
    "weight_kg",
    "handedness",
    "primary_league",
    "primary_league_family",
    "primary_competition_level",
    "consensus_rank",
    "model_score",
    "base_model_score",
    "board_score",
    "team_adjusted_score",
    "adjusted_production_score",
    "adjusted_ppg",
    "role_rank",
    "role_percentile",
    "adult_game_share",
    "junior_game_share",
    "college_game_share",
    "pro_game_share",
    "playoff_game_share",
    "adult_games",
    "adult_sample_tier",
    "adult_evidence_weight",
    "playoff_evidence_weight",
    "meaningful_adult_sample",
    "meaningful_playoff_sample",
    "average_league_weight",
    "pre_draft_row_count",
    "pre_draft_league_count",
    "goalie_save_percentage",
    "goalie_goals_against_average",
    "goalie_quality_score",
    "ep_tool_score",
    "ep_tool_grade_count",
    "team_fit_score",
    "team_fit_team",
    "team_fit_role",
    "team_fit_need",
    "team_fit_reason",
    "evidence_depth",
    "consensus_delta",
    "disagreement_bucket",
    "badges",
    "short_reason",
    "risk_note",
]

COMPARE_COLUMNS = [
    "player_id",
    "name",
    "position",
    "consensus_rank",
    "board_rank",
    "board_score",
    "team_adjusted_score",
    "adjusted_production_score",
    "role_percentile",
    "primary_league",
    "average_league_weight",
    "adult_game_share",
    "junior_game_share",
    "college_game_share",
    "playoff_game_share",
    "age_at_draft",
    "height_cm",
    "weight_kg",
    "handedness",
    "goalie_save_percentage",
    "goalie_goals_against_average",
    "goalie_quality_score",
    "ep_tool_score",
    "team_fit_score",
    "team_fit_need",
    "evidence_depth",
]


DEMO_STORY_PLAYERS = [
    {
        "name": "Michael Misa",
        "story_role": "Trust anchor",
        "story_hook": "Familiar top-of-board OHL scorer with high evidence.",
    },
    {
        "name": "Cole Reschny",
        "story_role": "Model-favored CHL forward",
        "story_hook": "Useful model-higher case with playoff context.",
    },
    {
        "name": "Alexei Medvedev",
        "story_role": "Goalie signal",
        "story_hook": "Goalie metrics plus multi-league history.",
    },
    {
        "name": "Charlie Cerrato",
        "story_role": "Multi-row US path",
        "story_hook": "USHL, USNTDP, and NCAA history in one profile.",
    },
    {
        "name": "Anton Frondell",
        "story_role": "Adult-league caution",
        "story_hook": "Consensus-higher case with adult exposure.",
    },
    {
        "name": "Max Psenicka",
        "story_role": "Consensus-higher defense",
        "story_hook": "High-evidence defense profile where the board is cautious.",
    },
    {
        "name": "Alexander Zharovsky",
        "story_role": "Russian credibility",
        "story_hook": "MHL production with KHL playoff exposure.",
    },
    {
        "name": "Eric Nilson",
        "story_role": "Nordic coverage",
        "story_hook": "Swedish junior, adult, and playoff context.",
    },
    {
        "name": "Roman Luttsev",
        "story_role": "Late-round model favorite",
        "story_hook": "Shortlist story where model evidence beats consensus.",
    },
    {
        "name": "Vojtech Cihar",
        "story_role": "Adult Czech exposure",
        "story_hook": "Cross-league translation example with adult games.",
    },
]


TEAM_STATUS_BY_ID = {
    "ANA": "rebuild_middle",
    "BOS": "playoff_bubble",
    "BUF": "rebuild_late",
    "CAR": "contender",
    "CBJ": "rebuild_middle",
    "CGY": "playoff_bubble",
    "CHI": "rebuild_middle",
    "COL": "contender",
    "DAL": "contender",
    "DET": "playoff_bubble",
    "EDM": "contender",
    "FLA": "contender",
    "LAK": "playoff_team",
    "MIN": "playoff_team",
    "MTL": "rebuild_late",
    "NJD": "playoff_team",
    "NSH": "rebuild_start",
    "NYI": "rebuild_start",
    "NYR": "playoff_bubble",
    "OTT": "playoff_bubble",
    "PHI": "rebuild_middle",
    "PIT": "rebuild_start",
    "SEA": "playoff_bubble",
    "SJS": "rebuild_middle",
    "STL": "playoff_bubble",
    "TBL": "contender",
    "TOR": "contender",
    "UTA": "rebuild_middle",
    "VAN": "playoff_team",
    "VGK": "contender",
    "WSH": "playoff_team",
    "WPG": "contender",
}

TEAM_STATUS_LABELS = {
    "rebuild_start": "Rebuild start",
    "rebuild_middle": "Rebuild middle",
    "rebuild_late": "Rebuild late",
    "playoff_bubble": "Playoff bubble",
    "playoff_team": "Playoff team",
    "contender": "Contender",
}


@dataclass(frozen=True)
class DemoExportBundle:
    board_rows: list[dict[str, str]]
    compare_rows: list[dict[str, str]]
    player_details: list[dict[str, object]]
    manifest: dict[str, object]


@dataclass(frozen=True)
class TeamFitContext:
    team_id: str
    team_name: str
    depth_rows: list[dict[str, str]]


def build_demo_export_bundle(
    prospects: list[HistoricalProspect],
    *,
    team_depth_csv: str | Path | None = None,
    team_id: str = "",
) -> DemoExportBundle:
    feature_rows = [row.to_dict() for row in build_feature_rows(prospects)]
    features_by_id = {row["player_id"]: row for row in feature_rows}
    consensus = consensus_scores(prospects)
    base_model_scores = role_specific_hybrid_scores(prospects)
    prospects_by_id = {prospect.player_id: prospect for prospect in prospects}
    ep_scores = {prospect.player_id: ep_tool_score(prospect) for prospect in prospects}
    model_scores = {
        player_id: scouting_adjusted_model_score(base_model_scores[player_id], ep_scores.get(player_id, 0.0))
        for player_id in base_model_scores
    }
    base_board_scores = {
        player_id: evidence_weighted_board_score(
            model_scores[player_id],
            consensus[player_id],
            features_by_id[player_id],
        )
        for player_id in model_scores.keys() & consensus.keys() & features_by_id.keys()
    }
    board_scores = {
        player_id: scouting_adjusted_board_score(
            base_board_scores[player_id],
            consensus[player_id],
            ep_scores.get(player_id, 0.0),
        )
        for player_id in base_board_scores
    }
    team_contexts = load_team_fit_contexts(team_depth_csv)
    team_fits = {
        player_id: default_team_fit(
            prospects_by_id[player_id],
            team_contexts,
            ep_scores.get(player_id, 0.0),
            team_id,
        )
        for player_id in board_scores
    }
    team_adjusted_scores = {
        player_id: team_adjusted_score(board_scores[player_id], team_fits[player_id])
        for player_id in board_scores
    }
    ordered_ids = [
        player_id
        for player_id, _ in sorted(board_scores.items(), key=lambda item: (item[1], item[0]), reverse=True)
    ]
    board_ranks = {player_id: index for index, player_id in enumerate(ordered_ids, start=1)}

    board_rows: list[dict[str, str]] = []
    compare_rows: list[dict[str, str]] = []
    player_details: list[dict[str, object]] = []

    for player_id in ordered_ids:
        prospect = prospects_by_id[player_id]
        feature = features_by_id[player_id]
        team_fit = team_fits[player_id]
        team_fit_options = build_team_fit_options(prospect, team_contexts, ep_scores[player_id], board_scores[player_id])
        resolved_drafted_team_id = drafted_team_id(prospect, team_contexts)
        board_rank = board_ranks[player_id]
        consensus_rank = int(feature["consensus_rank"])
        consensus_delta = board_rank - consensus_rank
        disagreement_bucket = classify_disagreement(consensus_delta)
        evidence_depth = classify_evidence_depth(feature)
        badges = build_badges(feature, disagreement_bucket, ep_scores[player_id], team_fit)
        short_reason = build_short_reason(feature, disagreement_bucket, ep_scores[player_id], team_fit)
        risk_note = build_risk_note(feature, consensus_delta)

        board_row = {
            "player_id": player_id,
            "draft_year": feature["draft_year"],
            "board_rank": str(board_rank),
            "name": feature["name"],
            "position": feature["position"],
            "role_group": feature["role_group"],
            "nationality": prospect.nationality,
            "age_at_draft": feature["age_at_draft"],
            "height_cm": feature["height_cm"],
            "weight_kg": feature["weight_kg"],
            "handedness": feature["handedness"],
            "primary_league": feature["primary_league"],
            "primary_league_family": feature["primary_league_family"],
            "primary_competition_level": feature["primary_competition_level"],
            "consensus_rank": feature["consensus_rank"],
            "model_score": f"{model_scores[player_id]:.6f}",
            "base_model_score": f"{base_model_scores[player_id]:.6f}",
            "board_score": f"{board_scores[player_id]:.6f}",
            "team_adjusted_score": f"{team_adjusted_scores[player_id]:.6f}",
            "adjusted_production_score": feature["adjusted_production_score"],
            "adjusted_ppg": feature["adjusted_ppg"],
            "role_rank": feature["role_rank"],
            "role_percentile": feature["role_percentile"],
            "adult_game_share": feature["adult_game_share"],
            "junior_game_share": feature["junior_game_share"],
            "college_game_share": feature["college_game_share"],
            "pro_game_share": feature["pro_game_share"],
            "playoff_game_share": feature["playoff_game_share"],
            "adult_games": feature["adult_games"],
            "adult_sample_tier": feature["adult_sample_tier"],
            "adult_evidence_weight": feature["adult_evidence_weight"],
            "playoff_evidence_weight": feature["playoff_evidence_weight"],
            "meaningful_adult_sample": feature["meaningful_adult_sample"],
            "meaningful_playoff_sample": feature["meaningful_playoff_sample"],
            "average_league_weight": feature["average_league_weight"],
            "pre_draft_row_count": feature["pre_draft_row_count"],
            "pre_draft_league_count": feature["pre_draft_league_count"],
            "goalie_save_percentage": feature["goalie_save_percentage"],
            "goalie_goals_against_average": feature["goalie_goals_against_average"],
            "goalie_quality_score": feature["goalie_quality_score"],
            "ep_tool_score": f"{ep_scores[player_id]:.6f}",
            "ep_tool_grade_count": str(len(prospect.tool_grades)),
            "team_fit_score": f"{team_fit['score']:.6f}",
            "team_fit_team": team_fit["team_id"],
            "team_fit_role": team_fit["role_type"],
            "team_fit_need": team_fit["need_label"],
            "team_fit_reason": team_fit["reason"],
            "evidence_depth": evidence_depth,
            "consensus_delta": str(consensus_delta),
            "disagreement_bucket": disagreement_bucket,
            "badges": "|".join(badges),
            "short_reason": short_reason,
            "risk_note": risk_note,
        }
        board_rows.append(board_row)
        compare_rows.append({column: board_row[column] for column in COMPARE_COLUMNS})
        player_details.append(build_player_detail(prospect, board_row, team_fit_options, resolved_drafted_team_id))

    return DemoExportBundle(
        board_rows=board_rows,
        compare_rows=compare_rows,
        player_details=player_details,
        manifest=build_manifest(prospects, board_rows, team_contexts, team_id),
    )


def export_demo_package(output_dir: str | Path, bundle: DemoExportBundle) -> dict[str, Path]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    board_path = root / "board.csv"
    compare_path = root / "compare.csv"
    players_path = root / "players.json"
    manifest_path = root / "manifest.json"

    write_csv(board_path, BOARD_COLUMNS, bundle.board_rows)
    write_csv(compare_path, COMPARE_COLUMNS, bundle.compare_rows)
    players_path.write_text(json.dumps(bundle.player_details, indent=2), encoding="utf-8")
    manifest_path.write_text(json.dumps(bundle.manifest, indent=2), encoding="utf-8")
    return {
        "board": board_path,
        "compare": compare_path,
        "players": players_path,
        "manifest": manifest_path,
    }


def evidence_weighted_board_score(model_score: float, consensus_score: float, feature: dict[str, str]) -> float:
    evidence_depth = classify_evidence_depth(feature)
    model_weight = {
        "high": 0.75,
        "medium": 0.45,
        "low": 0.18,
    }[evidence_depth]
    return (model_score * model_weight) + (consensus_score * (1.0 - model_weight))


def ep_tool_score(prospect: HistoricalProspect) -> float:
    grades = [float(grade.grade) for grade in prospect.tool_grades if grade.grade]
    if not grades:
        return 0.0
    return min(1.0, max(0.0, (sum(grades) / len(grades)) / 9.0))


def scouting_adjusted_model_score(base_model_score: float, tool_score: float) -> float:
    if tool_score <= 0.0:
        return base_model_score
    return (base_model_score * 0.82) + (tool_score * 0.18)


def scouting_adjusted_board_score(base_board_score: float, consensus_score: float, tool_score: float) -> float:
    if tool_score <= 0.0:
        return base_board_score
    lift = tool_score * 0.05
    if tool_score >= 0.75 and consensus_score >= 0.90:
        lift += 0.04
    elif tool_score >= 0.70 and consensus_score >= 0.80:
        lift += 0.025
    return min(1.0, base_board_score + lift)


def load_team_fit_contexts(team_depth_csv: str | Path | None) -> dict[str, TeamFitContext]:
    if not team_depth_csv:
        return {}
    path = Path(team_depth_csv)
    if not path.exists():
        return {}
    grouped: dict[str, list[dict[str, str]]] = {}
    with path.open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            normalized_team_id = row.get("team_id", "").upper()
            if normalized_team_id:
                grouped.setdefault(normalized_team_id, []).append(row)
    return {
        team_id: TeamFitContext(
            team_id=team_id,
            team_name=rows[0].get("team_name", team_id),
            depth_rows=rows,
        )
        for team_id, rows in grouped.items()
    }


def default_team_fit(
    prospect: HistoricalProspect,
    contexts: dict[str, TeamFitContext],
    tool_score: float,
    override_team_id: str = "",
) -> dict[str, object]:
    selected_team_id = (override_team_id.upper() if override_team_id else drafted_team_id(prospect, contexts))
    return build_team_fit(prospect, contexts.get(selected_team_id), tool_score)


def drafted_team_id(prospect: HistoricalProspect, contexts: dict[str, TeamFitContext] | None = None) -> str:
    if prospect.selection is None:
        return ""
    raw_team_id = prospect.selection.team_id.upper()
    if contexts is None or raw_team_id in contexts:
        return raw_team_id
    compact_raw = compact_team_text(raw_team_id)
    for context in contexts.values():
        compact_name = compact_team_text(context.team_name)
        if compact_name and compact_raw.startswith(compact_name):
            return context.team_id
    return raw_team_id


def compact_team_text(value: str) -> str:
    return "".join(character for character in value.upper() if character.isalnum())


def build_team_fit_options(
    prospect: HistoricalProspect,
    contexts: dict[str, TeamFitContext],
    tool_score: float,
    board_score: float,
) -> list[dict[str, object]]:
    options: list[dict[str, object]] = []
    resolved_drafted_team_id = drafted_team_id(prospect, contexts)
    for context in sorted(contexts.values(), key=lambda item: (item.team_name, item.team_id)):
        fit = dict(build_team_fit(prospect, context, tool_score))
        fit["team_adjusted_score"] = team_adjusted_score(board_score, fit)
        fit["is_drafted_team"] = fit["team_id"] == resolved_drafted_team_id
        options.append(fit)
    return options


def build_team_fit(
    prospect: HistoricalProspect,
    context: TeamFitContext | None,
    tool_score: float,
) -> dict[str, object]:
    if context is None:
        return {
            "score": 0.0,
            "team_id": "",
            "team_name": "",
            "role_type": "",
            "need_label": "No team context",
            "reason": "No NHL/AHL depth report was attached to this demo build.",
        }

    candidates = candidate_role_types(prospect, tool_score)
    matching_rows = [row for row in context.depth_rows if row.get("role_type") in candidates]
    if not matching_rows:
        matching_rows = [
            row for row in context.depth_rows if row.get("role_bucket") == candidate_role_bucket(prospect.position)
        ]
    if not matching_rows:
        return {
            "score": 0.0,
            "team_id": context.team_id,
            "team_name": context.team_name,
            "role_type": "",
            "need_label": "Unmapped role",
            "reason": f"{context.team_name} depth data is present, but this prospect role is not mapped yet.",
        }

    best_row = max(matching_rows, key=lambda row: team_fit_components(row, prospect, tool_score)["overall_score"])
    components = team_fit_components(best_row, prospect, tool_score)
    score = components["overall_score"]
    role_type = best_row.get("role_type", "")
    scarcity = safe_float(best_row.get("scarcity_score", "0"))
    avg_age = safe_float(best_row.get("avg_age", "0"))
    under_25 = safe_int(best_row.get("under_25", "0"))
    players = safe_int(best_row.get("players", "0"))
    target = safe_float(best_row.get("scarcity_target", "0"))
    level = best_row.get("league_level", "")
    examples = best_row.get("example_players", "")
    status = team_status(context.team_id)
    ahl_rows = [row for row in context.depth_rows if row.get("league_level") == "AHL"]
    coverage_note = "AHL depth available" if ahl_rows else "AHL depth not loaded"
    return {
        "score": score,
        "team_id": context.team_id,
        "team_name": context.team_name,
        "role_type": role_type,
        "need_label": classify_team_need(score),
        "team_status": status,
        "team_status_label": TEAM_STATUS_LABELS.get(status, status.replace("_", " ").title()),
        "roster_need_score": components["roster_need_score"],
        "pipeline_need_score": components["pipeline_need_score"],
        "timeline_fit_score": components["timeline_fit_score"],
        "risk_appetite_score": components["risk_appetite_score"],
        "u25_same_role_count": under_25,
        "role_player_count": players,
        "scarcity_target": target,
        "ahl_coverage": "available" if ahl_rows else "missing",
        "reason": (
            f"{context.team_name} {level} {role_type.replace('_', ' ')} depth shows "
            f"scarcity {scarcity:.2f}, U25 count {under_25}, avg age {avg_age:.1f}. "
            f"Team status: {TEAM_STATUS_LABELS.get(status, status)}. {coverage_note}. "
            f"Examples: {examples or 'not available'}."
        ),
    }


def team_adjusted_score(board_score: float, team_fit: dict[str, object]) -> float:
    fit_score = float(team_fit.get("score", 0.0))
    return (board_score * 0.85) + (fit_score * 0.15)


def candidate_role_bucket(position: str) -> str:
    normalized = position.strip().upper()
    if normalized == "G":
        return "goalie"
    if normalized.endswith("D") or normalized == "D":
        return "defense"
    if normalized == "C":
        return "center"
    return "wing"


def candidate_role_types(prospect: HistoricalProspect, tool_score: float) -> list[str]:
    bucket = candidate_role_bucket(prospect.position)
    if bucket == "goalie":
        return ["starter_goalie", "tandem_goalie", "depth_goalie"]
    if bucket == "defense":
        if tool_score >= 0.72:
            return ["puck_moving_defense", "two_way_defense", "defense_depth"]
        return ["two_way_defense", "defense_depth", "puck_moving_defense"]
    if bucket == "center":
        if tool_score >= 0.70:
            return ["scoring_center", "two_way_center", "center_depth"]
        return ["two_way_center", "center_depth", "scoring_center"]
    if tool_score >= 0.70:
        return ["scoring_wing", "two_way_wing", "wing_depth"]
    return ["two_way_wing", "wing_depth", "scoring_wing"]


def team_fit_components(row: dict[str, str], prospect: HistoricalProspect, tool_score: float) -> dict[str, float]:
    roster_need = roster_need_score(row, tool_score)
    pipeline_need = pipeline_need_score(row, prospect, tool_score)
    timeline_fit = timeline_fit_score(row, prospect)
    risk_fit = risk_appetite_score(prospect, row)
    overall = (
        (roster_need * 0.36)
        + (pipeline_need * 0.34)
        + (timeline_fit * 0.18)
        + (risk_fit * 0.12)
    )
    return {
        "overall_score": min(1.0, max(0.0, overall)),
        "roster_need_score": roster_need,
        "pipeline_need_score": pipeline_need,
        "timeline_fit_score": timeline_fit,
        "risk_appetite_score": risk_fit,
    }


def roster_need_score(row: dict[str, str], tool_score: float) -> float:
    scarcity = safe_float(row.get("scarcity_score", "0"))
    avg_age = safe_float(row.get("avg_age", "0"))
    age_pressure = 0.0
    if avg_age >= 30.0:
        age_pressure += 0.35
    elif avg_age >= 28.0:
        age_pressure += 0.20
    level_bonus = 0.10 if row.get("league_level") == "NHL" else 0.06
    score = (scarcity * 0.62) + (min(1.0, age_pressure) * 0.20) + level_bonus + (tool_score * 0.08)
    return min(1.0, max(0.0, score))


def pipeline_need_score(row: dict[str, str], prospect: HistoricalProspect, tool_score: float) -> float:
    target = safe_float(row.get("scarcity_target", "0")) or 1.0
    under_25 = safe_int(row.get("under_25", "0"))
    players = safe_int(row.get("players", "0"))
    role_type = row.get("role_type", "")
    premium_role = role_type in {"puck_moving_defense", "two_way_defense", "scoring_center", "scoring_wing", "starter_goalie"}
    u25_pressure = min(1.0, under_25 / max(1.0, target))
    roster_saturation = min(1.0, players / max(1.0, target + 1.0))
    score = 1.0 - ((u25_pressure * 0.62) + (roster_saturation * 0.25))
    if premium_role and under_25 >= 2:
        score -= 0.18
    if candidate_role_bucket(prospect.position) == "defense" and under_25 >= 4:
        score -= 0.25
    if candidate_role_bucket(prospect.position) == "goalie" and under_25 >= 2:
        score -= 0.15
    if tool_score >= 0.75 and under_25 == 0:
        score += 0.08
    return min(1.0, max(0.0, score))


def timeline_fit_score(row: dict[str, str], prospect: HistoricalProspect) -> float:
    status = team_status(row.get("team_id", ""))
    adult_share = adult_game_share(prospect)
    playoff_share = playoff_game_share(prospect)
    near_ready = min(1.0, (adult_share * 0.75) + (playoff_share * 0.25))
    long_run_upside = 1.0 if prospect.age_at_draft <= 18.4 else 0.72
    if status in {"rebuild_start", "rebuild_middle"}:
        return min(1.0, (long_run_upside * 0.75) + (near_ready * 0.25))
    if status in {"rebuild_late", "playoff_bubble"}:
        return min(1.0, 0.45 + (near_ready * 0.35) + (long_run_upside * 0.20))
    return min(1.0, 0.35 + (near_ready * 0.50) + (long_run_upside * 0.15))


def risk_appetite_score(prospect: HistoricalProspect, row: dict[str, str]) -> float:
    status = team_status(row.get("team_id", ""))
    evidence = min(1.0, len(prospect.pre_draft_stat_lines) / 4.0)
    adult = adult_game_share(prospect)
    if status in {"rebuild_start", "rebuild_middle"}:
        return min(1.0, 0.50 + (evidence * 0.25) + ((1.0 - adult) * 0.15))
    if status in {"rebuild_late", "playoff_bubble"}:
        return min(1.0, 0.42 + (evidence * 0.32) + (adult * 0.18))
    return min(1.0, 0.30 + (evidence * 0.30) + (adult * 0.30))


def team_status(team_id: str) -> str:
    return TEAM_STATUS_BY_ID.get(team_id.upper(), "playoff_bubble")


def adult_game_share(prospect: HistoricalProspect) -> float:
    lines = prospect.pre_draft_stat_lines or (prospect.stat_line,)
    games = sum(line.games for line in lines)
    adult_games = sum(line.games for line in lines if is_adult_league(line.league))
    return adult_games / games if games else 0.0


def playoff_game_share(prospect: HistoricalProspect) -> float:
    lines = prospect.pre_draft_stat_lines or (prospect.stat_line,)
    games = sum(line.games for line in lines)
    playoff_games = sum(line.games for line in lines if not line.regular_season)
    return playoff_games / games if games else 0.0


def is_adult_league(league: str) -> bool:
    normalized = league.strip().upper()
    junior_markers = ("JRS", "JR.", "J20", "U20", "U18", "OHL", "WHL", "QMJHL", "USHL", "NTDP", "NCAA")
    if any(marker in normalized for marker in junior_markers):
        return False
    adult_markers = (
        "NHL",
        "AHL",
        "KHL",
        "VHL",
        "SHL",
        "LIIGA",
        "MESTIS",
        "HOCKEYALLSVENSKAN",
        "CZECH",
        "SLOVAKIA",
        "SWISS",
        "DEL",
        "SWE-1",
        "FINLAND",
    )
    return any(marker in normalized for marker in adult_markers)


def classify_team_need(score: float) -> str:
    if score >= 0.65:
        return "Strong team fit"
    if score >= 0.40:
        return "Useful team fit"
    if score > 0:
        return "Light team fit"
    return "No team context"


def build_player_detail(
    prospect: HistoricalProspect,
    board_row: dict[str, str],
    team_fit_options: list[dict[str, object]] | None = None,
    resolved_drafted_team_id: str = "",
) -> dict[str, object]:
    return {
        "player_id": prospect.player_id,
        "header": {
            "name": prospect.name,
            "position": prospect.position,
            "role_group": board_row["role_group"],
            "nationality": prospect.nationality,
            "age_at_draft": round(prospect.age_at_draft, 2),
            "height_cm": prospect.height_cm,
            "weight_kg": prospect.weight_kg,
            "handedness": prospect.handedness,
            "consensus_rank": int(board_row["consensus_rank"]),
            "board_rank": int(board_row["board_rank"]),
            "drafted_team_id": resolved_drafted_team_id or drafted_team_id(prospect),
        },
        "summary": {
            "board_score": float(board_row["board_score"]),
            "team_adjusted_score": float(board_row["team_adjusted_score"]),
            "model_score": float(board_row["model_score"]),
            "base_model_score": float(board_row["base_model_score"]),
            "adjusted_production_score": float(board_row["adjusted_production_score"]),
            "adjusted_ppg": float(board_row["adjusted_ppg"]),
            "role_rank": int(board_row["role_rank"]),
            "role_percentile": float(board_row["role_percentile"]),
            "average_league_weight": float(board_row["average_league_weight"]),
            "adult_game_share": float(board_row["adult_game_share"]),
            "playoff_game_share": float(board_row["playoff_game_share"]),
            "goalie_save_percentage": float(board_row["goalie_save_percentage"]),
            "goalie_goals_against_average": float(board_row["goalie_goals_against_average"]),
            "goalie_quality_score": float(board_row["goalie_quality_score"]),
            "ep_tool_score": float(board_row["ep_tool_score"]),
            "team_fit_score": float(board_row["team_fit_score"]),
            "evidence_depth": board_row["evidence_depth"],
        },
        "why_high": build_why_high(board_row),
        "risk_flags": build_risk_flags(board_row),
        "team_fit": {
            "team_id": board_row["team_fit_team"],
            "role": board_row["team_fit_role"],
            "need": board_row["team_fit_need"],
            "score": float(board_row["team_fit_score"]),
            "team_adjusted_score": float(board_row["team_adjusted_score"]),
            "reason": board_row["team_fit_reason"],
        },
        "team_fit_options": team_fit_options or [],
        "scouting": {
            "summary": prospect.scouting_text,
            "shades_of": prospect.shades_of,
            "badges": list(prospect.scouting_badges),
            "tool_grades": [
                {
                    "tool": grade.tool,
                    "grade": grade.grade,
                    "source": grade.source,
                    "source_id": grade.source_id,
                    "source_url": grade.source_url,
                }
                for grade in prospect.tool_grades
            ],
        },
        "pre_draft_history": [
            {
                "season": line.season,
                "league": line.league,
                "team": line.team,
                "games": line.games,
                "goals": line.goals,
                "assists": line.assists,
                "points": line.total_points,
                "regular_season": line.regular_season,
                "source": line.source or "unknown",
                "source_id": line.source_id,
                "source_url": line.source_url,
                "goalie_minutes": line.goalie_minutes,
                "shots_against": line.shots_against,
                "saves": line.saves,
                "goals_against": line.goals_against,
                "save_percentage": line.save_percentage,
                "goals_against_average": line.goals_against_average,
                "wins": line.wins,
                "losses": line.losses,
                "ties": line.ties,
                "shutouts": line.shutouts,
            }
            for line in prospect.pre_draft_stat_lines
        ],
        "sources": [
            {
                "source": source.source,
                "source_id": source.source_id,
                "source_url": source.url,
            }
            for source in prospect.sources
        ],
    }


def classify_disagreement(consensus_delta: int) -> str:
    if consensus_delta <= -8:
        return "model_higher"
    if consensus_delta >= 8:
        return "consensus_higher"
    return "aligned"


def classify_evidence_depth(feature: dict[str, str]) -> str:
    row_count = int(feature["pre_draft_row_count"])
    league_count = int(feature["pre_draft_league_count"])
    if row_count >= 3 or league_count >= 2:
        return "high"
    if row_count == 2:
        return "medium"
    return "low"


def build_badges(
    feature: dict[str, str],
    disagreement_bucket: str,
    tool_score: float,
    team_fit: dict[str, object],
) -> list[str]:
    badges: list[str] = []
    if disagreement_bucket == "model_higher":
        badges.append("Model Higher")
    elif disagreement_bucket == "consensus_higher":
        badges.append("Consensus Higher")
    if tool_score >= 0.75:
        badges.append("EP Elite Tools")
    elif tool_score > 0:
        badges.append("EP Guide Evidence")
    if float(team_fit.get("score", 0.0)) >= 0.65:
        badges.append("Strong Team Fit")
    elif float(team_fit.get("score", 0.0)) >= 0.40:
        badges.append("Team Fit")
    if feature.get("meaningful_adult_sample") == "1":
        badges.append("Adult Sample")
    elif float(feature["adult_game_share"]) > 0:
        badges.append("Adult Exposure")
    if feature.get("meaningful_playoff_sample") == "1":
        badges.append("Playoff Sample")
    if feature.get("is_goalie") == "1" and float(feature.get("goalie_quality_score", "0") or 0) > 0:
        badges.append("Goalie Metrics")
    if int(feature["pre_draft_league_count"]) > 1:
        badges.append("Multi-League")
    if classify_evidence_depth(feature) == "low":
        badges.append("Low Evidence")
    return badges


def build_short_reason(
    feature: dict[str, str],
    disagreement_bucket: str,
    tool_score: float,
    team_fit: dict[str, object],
) -> str:
    reasons: list[str] = []
    if tool_score >= 0.75:
        reasons.append("EP guide grades add elite-tool evidence")
    elif tool_score > 0:
        reasons.append("EP guide grades add scouting context")
    if float(team_fit.get("score", 0.0)) >= 0.65:
        reasons.append(f"{team_fit.get('team_id')} roster fit is strong")
    if float(feature["role_percentile"]) >= 0.9:
        reasons.append("Production stands out within role")
    if float(feature["average_league_weight"]) >= 1.0:
        reasons.append("Stronger competition context")
    if feature.get("meaningful_adult_sample") == "1":
        reasons.append("Meaningful adult-league sample")
    elif float(feature["adult_game_share"]) > 0:
        reasons.append("Adult-league exposure, small sample")
    if feature.get("meaningful_playoff_sample") == "1":
        reasons.append("Playoff sample adds pressure context")
    if feature.get("is_goalie") == "1" and float(feature.get("goalie_quality_score", "0") or 0) > 0:
        reasons.append("Goalie stat signal available")
    if int(feature["pre_draft_league_count"]) > 1:
        reasons.append("Multiple league contexts")
    if disagreement_bucket == "model_higher":
        reasons.append("Review candidate above consensus")
    if disagreement_bucket == "consensus_higher":
        reasons.append("Consensus is more aggressive")
    return ", ".join(reasons[:2]) or "Comparable profile; use detail view for context."


def build_risk_note(feature: dict[str, str], consensus_delta: int) -> str:
    risks: list[str] = []
    if int(feature["pre_draft_row_count"]) == 1:
        risks.append("Needs more pre-draft rows")
    if float(feature["adult_game_share"]) == 0.0:
        risks.append("No adult-league sample")
    elif feature.get("meaningful_adult_sample") != "1":
        risks.append("Adult sample is thin")
    if float(feature["playoff_game_share"]) == 0.0:
        risks.append("No playoff row captured")
    elif feature.get("meaningful_playoff_sample") != "1":
        risks.append("Playoff sample is thin")
    if feature.get("is_goalie") == "1" and float(feature.get("goalie_quality_score", "0") or 0) == 0.0:
        risks.append("Goalie metrics not yet captured")
    if abs(consensus_delta) >= 10:
        risks.append("Board-consensus gap needs review")
    return ", ".join(risks[:2]) or "No major coverage flags in current sample."


def build_why_high(board_row: dict[str, str]) -> list[str]:
    points: list[str] = []
    if float(board_row.get("ep_tool_score", "0") or 0) >= 0.75:
        points.append("Elite Prospects guide grades push this player above the pure stat-only view.")
    elif float(board_row.get("ep_tool_score", "0") or 0) > 0:
        points.append("Elite Prospects guide grades add a scouting-evidence layer beyond production.")
    if float(board_row.get("team_fit_score", "0") or 0) >= 0.65:
        points.append(f"{board_row['team_fit_team']} roster context flags this role as a strong fit.")
    if float(board_row["role_percentile"]) >= 0.9:
        points.append("Production ranks well against comparable players in the same role.")
    if float(board_row["average_league_weight"]) >= 1.0:
        points.append("Primary league context is stronger than the average draft-year sample.")
    if board_row.get("meaningful_adult_sample") == "1":
        points.append("Adult-league sample is large enough to carry translation value.")
    elif float(board_row["adult_game_share"]) > 0:
        points.append("Adult-league exposure is present, but the sample remains small.")
    if board_row.get("meaningful_playoff_sample") == "1":
        points.append("Playoff games add pressure-sample context.")
    if board_row["role_group"] == "goalie" and float(board_row["goalie_quality_score"]) > 0:
        points.append("Goalie evaluation uses save percentage, goals-against context, and workload fields.")
    if int(board_row["pre_draft_league_count"]) > 1:
        points.append("Multi-league history helps separate one-team context from broader performance.")
    if not points:
        points.append("Profile remains in range across consensus, role, and league-context signals.")
    return points[:3]


def safe_float(value: str | None) -> float:
    try:
        return float(value or 0.0)
    except ValueError:
        return 0.0


def safe_int(value: str | None) -> int:
    try:
        return int(float(value or 0))
    except ValueError:
        return 0


def build_risk_flags(board_row: dict[str, str]) -> list[str]:
    flags: list[str] = []
    if int(board_row["pre_draft_row_count"]) == 1:
        flags.append("Only one pre-draft stat row is currently captured; treat the grade as review-ready, not final.")
    if float(board_row["adult_game_share"]) == 0.0:
        flags.append("No adult-league sample is present, so junior translation remains a question.")
    elif board_row.get("meaningful_adult_sample") != "1":
        flags.append("Adult-league exposure is present, but the game sample is too small to carry much weight.")
    if float(board_row["playoff_game_share"]) == 0.0:
        flags.append("No playoff row is captured yet; pressure-sample context may be incomplete.")
    elif board_row.get("meaningful_playoff_sample") != "1":
        flags.append("Playoff exposure is present, but the game sample is still thin.")
    if board_row["role_group"] == "goalie" and float(board_row["goalie_quality_score"]) == 0.0:
        flags.append("Goalie-specific performance fields are not yet populated for this player.")
    if abs(int(board_row["consensus_delta"])) >= 10:
        flags.append("Board rank and public consensus differ enough to warrant a scouting-room review.")
    if not flags:
        flags.append("No major coverage or translation flags in the current dataset.")
    return flags[:3]


def write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def build_manifest(
    prospects: list[HistoricalProspect],
    board_rows: list[dict[str, str]],
    team_contexts: dict[str, TeamFitContext] | None = None,
    team_id: str = "",
) -> dict[str, object]:
    if not prospects:
        return {
            "draft_year": None,
            "player_count": 0,
            "dataset_status": "empty",
            "evidence_depth_counts": {},
            "disagreement_counts": {},
            "source_counts": {},
            "featured_player_ids": [],
            "demo_story_players": [],
            "team_context": {},
            "team_contexts": [],
        }

    evidence_depth_counts: dict[str, int] = {}
    disagreement_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    for row in board_rows:
        evidence_depth_counts[row["evidence_depth"]] = evidence_depth_counts.get(row["evidence_depth"], 0) + 1
        disagreement_counts[row["disagreement_bucket"]] = disagreement_counts.get(row["disagreement_bucket"], 0) + 1
    for prospect in prospects:
        for source in prospect.sources:
            source_counts[source.source] = source_counts.get(source.source, 0) + 1

    story_players = build_demo_story_players(board_rows)
    featured = sorted(
        board_rows,
        key=lambda row: (abs(int(row["consensus_delta"])), -int(row["board_rank"])),
        reverse=True,
    )[:10]
    featured_ids = [row["player_id"] for row in featured]
    if story_players:
        featured_ids = [story["player_id"] for story in story_players]
    return {
        "draft_year": prospects[0].draft_year,
        "player_count": len(prospects),
        "dataset_status": classify_dataset_status(board_rows),
        "evidence_depth_counts": evidence_depth_counts,
        "disagreement_counts": disagreement_counts,
        "source_counts": source_counts,
        "featured_player_ids": featured_ids,
        "demo_story_players": story_players,
        "team_context": build_manifest_team_contexts(team_contexts or {}, team_id),
        "team_contexts": build_manifest_team_list(team_contexts or {}),
    }


def build_manifest_team_contexts(contexts: dict[str, TeamFitContext], team_id: str = "") -> dict[str, object]:
    if not contexts:
        return {}
    return {
        "mode": "override" if team_id else "drafted_team_default",
        "default_team_id": team_id.upper(),
        "team_count": len(contexts),
        "depth_row_count": sum(len(context.depth_rows) for context in contexts.values()),
    }


def build_manifest_team_list(contexts: dict[str, TeamFitContext]) -> list[dict[str, object]]:
    return [
        {
            "team_id": context.team_id,
            "team_name": context.team_name,
            "depth_row_count": len(context.depth_rows),
        }
        for context in sorted(contexts.values(), key=lambda item: (item.team_name, item.team_id))
    ]


def build_demo_story_players(board_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows_by_name = {row["name"].casefold(): row for row in board_rows}
    stories: list[dict[str, str]] = []
    for story in DEMO_STORY_PLAYERS:
        row = rows_by_name.get(story["name"].casefold())
        if not row:
            continue
        stories.append(
            {
                "player_id": row["player_id"],
                "name": row["name"],
                "story_role": story["story_role"],
                "story_hook": story["story_hook"],
                "board_rank": row["board_rank"],
                "consensus_rank": row["consensus_rank"],
                "evidence_depth": row["evidence_depth"],
                "disagreement_bucket": row["disagreement_bucket"],
            }
        )
    return stories


def classify_dataset_status(board_rows: list[dict[str, str]]) -> str:
    if not board_rows:
        return "empty"
    high_or_medium = sum(1 for row in board_rows if row["evidence_depth"] in {"high", "medium"})
    ratio = high_or_medium / len(board_rows)
    if ratio >= 0.65:
        return "strong"
    if ratio >= 0.35:
        return "usable"
    return "thin"
