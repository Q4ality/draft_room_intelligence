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
from draft_room_intelligence.modeling.feature_table import AdvancedStatSummary, build_feature_rows

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
    "advanced_games",
    "advanced_sample_weight",
    "plus_minus_per_game",
    "shots_per_game",
    "blocks_per_game",
    "faceoff_percentage",
    "advanced_role_score",
    "ep_tool_score",
    "ep_tool_grade_count",
    "drafted_team_id",
    "drafted_team_name",
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
    "drafted_team_id",
    "drafted_team_name",
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
        "name": "Matthew Schaefer",
        "story_role": "Elite defense calibration",
        "story_hook": "Consensus and scouting evidence protect a top defense profile with a short sample.",
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
    snapshot_label: str = "Current NHL API roster"
    snapshot_warning: str = "Not a pre-2025/26-season or draft-night roster snapshot."


def build_demo_export_bundle(
    prospects: list[HistoricalProspect],
    *,
    team_depth_csv: str | Path | None = None,
    team_id: str = "",
    advanced_stats: dict[str, AdvancedStatSummary] | None = None,
) -> DemoExportBundle:
    feature_rows = [row.to_dict() for row in build_feature_rows(prospects, advanced_stats)]
    features_by_id = {row["player_id"]: row for row in feature_rows}
    consensus = consensus_scores(prospects)
    base_model_scores = role_specific_hybrid_scores(prospects)
    prospects_by_id = {prospect.player_id: prospect for prospect in prospects}
    ep_scores = {prospect.player_id: ep_tool_score(prospect) for prospect in prospects}
    model_scores = {
        player_id: scouting_adjusted_model_score(
            base_model_scores[player_id], ep_scores.get(player_id, 0.0)
        )
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
    draft_years = {prospect.draft_year for prospect in prospects}
    expected_roster_snapshot = f"{next(iter(draft_years))}-06-01" if len(draft_years) == 1 else ""
    team_contexts = load_team_fit_contexts(
        team_depth_csv,
        expected_snapshot_date=expected_roster_snapshot,
    )
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
        for player_id, _ in sorted(
            board_scores.items(), key=lambda item: (item[1], item[0]), reverse=True
        )
    ]
    board_ranks = {player_id: index for index, player_id in enumerate(ordered_ids, start=1)}

    board_rows: list[dict[str, str]] = []
    compare_rows: list[dict[str, str]] = []
    player_details: list[dict[str, object]] = []

    for player_id in ordered_ids:
        prospect = prospects_by_id[player_id]
        feature = features_by_id[player_id]
        team_fit = team_fits[player_id]
        team_fit_options = build_team_fit_options(
            prospect, team_contexts, ep_scores[player_id], board_scores[player_id]
        )
        resolved_drafted_team_id = drafted_team_id(prospect, team_contexts)
        drafted_context = team_contexts.get(resolved_drafted_team_id)
        resolved_drafted_team_name = (
            drafted_context.team_name if drafted_context else resolved_drafted_team_id
        )
        board_rank = board_ranks[player_id]
        consensus_rank = int(feature["consensus_rank"])
        consensus_delta = board_rank - consensus_rank
        disagreement_bucket = classify_disagreement(consensus_delta)
        evidence_depth = classify_evidence_depth(feature)
        badges = build_badges(feature, disagreement_bucket, ep_scores[player_id], team_fit)
        short_reason = build_short_reason(
            feature, disagreement_bucket, ep_scores[player_id], team_fit
        )
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
            "advanced_games": feature["advanced_games"],
            "advanced_sample_weight": feature["advanced_sample_weight"],
            "plus_minus_per_game": feature["plus_minus_per_game"],
            "shots_per_game": feature["shots_per_game"],
            "blocks_per_game": feature["blocks_per_game"],
            "faceoff_percentage": feature["faceoff_percentage"],
            "advanced_role_score": feature["advanced_role_score"],
            "ep_tool_score": f"{ep_scores[player_id]:.6f}",
            "ep_tool_grade_count": str(len(prospect.tool_grades)),
            "drafted_team_id": resolved_drafted_team_id,
            "drafted_team_name": resolved_drafted_team_name,
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
        player_details.append(
            build_player_detail(prospect, board_row, team_fit_options, resolved_drafted_team_id)
        )

    return DemoExportBundle(
        board_rows=board_rows,
        compare_rows=compare_rows,
        player_details=player_details,
        manifest=build_manifest(prospects, board_rows, team_contexts, team_id, player_details),
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


def evidence_weighted_board_score(
    model_score: float, consensus_score: float, feature: dict[str, str]
) -> float:
    evidence_depth = classify_evidence_depth(feature)
    model_weight = {
        "high": 0.75,
        "medium": 0.45,
        "low": 0.18,
    }[evidence_depth]
    if feature["role_group"] == "defense":
        model_weight *= 0.68
    elif feature["role_group"] == "goalie":
        model_weight *= 0.55
    if consensus_score >= 0.92:
        model_weight *= 0.58
    elif consensus_score >= 0.84:
        model_weight *= 0.74
    if safe_int(feature.get("pre_draft_total_games")) < 25 and consensus_score >= 0.80:
        model_weight *= 0.70
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


def scouting_adjusted_board_score(
    base_board_score: float, consensus_score: float, tool_score: float
) -> float:
    if tool_score <= 0.0:
        return base_board_score
    lift = tool_score * 0.05
    if tool_score >= 0.75 and consensus_score >= 0.90:
        lift += 0.04
    elif tool_score >= 0.70 and consensus_score >= 0.80:
        lift += 0.025
    return min(1.0, base_board_score + lift)


def load_team_fit_contexts(
    team_depth_csv: str | Path | None,
    *,
    expected_snapshot_date: str = "",
) -> dict[str, TeamFitContext]:
    if not team_depth_csv:
        return {}
    path = Path(team_depth_csv)
    if not path.exists():
        return {}
    snapshot_label, snapshot_warning = team_depth_snapshot_labels(
        path,
        expected_snapshot_date=expected_snapshot_date,
    )
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
            snapshot_label=snapshot_label,
            snapshot_warning=snapshot_warning,
        )
        for team_id, rows in grouped.items()
    }


def team_depth_snapshot_labels(
    path: Path,
    *,
    expected_snapshot_date: str = "",
) -> tuple[str, str]:
    snapshot_types: set[str] = set()
    snapshot_dates: set[str] = set()
    assignment_sources: set[str] = set()
    incomplete_rows = False
    try:
        with path.open(newline="", encoding="utf-8") as file:
            for row in csv.DictReader(file):
                row_types = split_provenance_values(row.get("snapshot_types", ""))
                row_dates = split_provenance_values(row.get("snapshot_dates", ""))
                row_sources = split_provenance_values(row.get("assignment_sources", ""))
                incomplete_rows |= not row_types or not row_dates or not row_sources
                snapshot_types.update(row_types)
                snapshot_dates.update(row_dates)
                assignment_sources.update(row_sources)
    except (OSError, csv.Error):
        snapshot_types = set()
        snapshot_dates = set()
        assignment_sources = set()
        incomplete_rows = True
    expected_dates = {expected_snapshot_date} if expected_snapshot_date else snapshot_dates
    if (
        not incomplete_rows
        and snapshot_types == {"point_in_time_rights"}
        and snapshot_dates == expected_dates
        and assignment_sources
    ):
        return (
            "Verified point-in-time organizational rights snapshot",
            "Assignments reflect the staged full-league rights inventory at its stated historical "
            "cutoff; season statistics remain prior-season evidence.",
        )
    normalized = path.as_posix().lower()
    if "2024_25" in normalized and "ahl" in normalized:
        return (
            "2024-25 NHL season roster + 2024-25 AHL roster",
            "Historical season-participation rosters; more reliable than current-roster proxies, but not a point-in-time draft-night rights snapshot.",
        )
    if "with_ahl" in normalized or "ahl" in normalized:
        return (
            "Pre-2025/26 proxy roster + 2024-25 AHL roster",
            "NHL proxy roster with 2025 draft-class players removed, plus official 2024-25 AHL stats and roster-detail feeds; not a verified historical opening-night roster.",
        )
    if "pre_2025_26_proxy" in normalized or "pre-2025-26-proxy" in normalized:
        return (
            "Pre-2025/26 proxy roster",
            "Current NHL API roster with 2025 draft-class players removed; not a verified historical preseason roster.",
        )
    return (
        "Current NHL API roster",
        "Not a pre-2025/26-season or draft-night roster snapshot.",
    )


def split_provenance_values(value: str) -> set[str]:
    return {item.strip() for item in value.split(";") if item.strip()}


def default_team_fit(
    prospect: HistoricalProspect,
    contexts: dict[str, TeamFitContext],
    tool_score: float,
    override_team_id: str = "",
) -> dict[str, object]:
    selected_team_id = (
        override_team_id.upper() if override_team_id else drafted_team_id(prospect, contexts)
    )
    return build_team_fit(prospect, contexts.get(selected_team_id), tool_score)


def drafted_team_id(
    prospect: HistoricalProspect, contexts: dict[str, TeamFitContext] | None = None
) -> str:
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
            row
            for row in context.depth_rows
            if row.get("role_bucket") == candidate_role_bucket(prospect.position)
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

    best_row = max(
        matching_rows,
        key=lambda row: team_fit_components(row, prospect, tool_score, context.depth_rows)[
            "overall_score"
        ],
    )
    components = team_fit_components(best_row, prospect, tool_score, context.depth_rows)
    score = components["overall_score"]
    role_type = best_row.get("role_type", "")
    scarcity = safe_float(best_row.get("scarcity_score", "0"))
    avg_age = safe_float(best_row.get("avg_age", "0"))
    under_25 = safe_int(best_row.get("under_25", "0"))
    players = safe_int(best_row.get("players", "0"))
    target = safe_float(best_row.get("scarcity_target", "0"))
    level = best_row.get("league_level", "")
    examples = best_row.get("example_players", "")
    peer_examples = peer_pipeline_examples(best_row, context.depth_rows)
    status = team_status(context.team_id)
    ahl_rows = [row for row in context.depth_rows if row.get("league_level") == "AHL"]
    coverage_note = "AHL depth available" if ahl_rows else "AHL depth not loaded"
    contract_note = (
        f"Contract coverage: {components['contract_coverage']:.0%}; "
        f"role commitment: {components['contract_commitment_score']:.0%}; "
        f"roster flexibility: {components['roster_flexibility_score']:.0%}. "
        if components["contract_coverage"] >= 0.50
        else "Contract/cap coverage not loaded. "
    )
    return {
        "score": score,
        "team_id": context.team_id,
        "team_name": context.team_name,
        "role_type": role_type,
        "need_label": classify_team_need(score),
        "team_status": status,
        "team_status_label": TEAM_STATUS_LABELS.get(status, status.replace("_", " ").title()),
        "roster_snapshot_label": context.snapshot_label,
        "roster_snapshot_warning": context.snapshot_warning,
        "roster_need_score": components["roster_need_score"],
        "pipeline_need_score": components["pipeline_need_score"],
        "pipeline_capacity_ceiling": components["pipeline_capacity_ceiling"],
        "timeline_fit_score": components["timeline_fit_score"],
        "risk_appetite_score": components["risk_appetite_score"],
        "contract_opportunity_score": components["contract_opportunity_score"],
        "contract_coverage": components["contract_coverage"],
        "contract_commitment_score": components["contract_commitment_score"],
        "roster_flexibility_score": components["roster_flexibility_score"],
        "bucket_u25_count": components["bucket_u25_count"],
        "bucket_nhl_u25_count": components["bucket_nhl_u25_count"],
        "bucket_ahl_u25_count": components["bucket_ahl_u25_count"],
        "bucket_non_nhl_u25_count": components["bucket_non_nhl_u25_count"],
        "bucket_player_count": components["bucket_player_count"],
        "u25_same_role_count": under_25,
        "role_player_count": players,
        "scarcity_target": target,
        "ahl_coverage": "available" if ahl_rows else "missing",
        "reason": (
            f"{context.team_name} {level} {role_type.replace('_', ' ')} depth shows "
            f"scarcity {scarcity:.2f}, U25 count {under_25}, avg age {avg_age:.1f}. "
            f"Same-position pipeline: {components['bucket_u25_count']} U25 across "
            f"{components['bucket_player_count']} {candidate_role_bucket(prospect.position)} rows. "
            f"NHL-ready U25: {int(components['bucket_nhl_u25_count'])}; "
            f"AHL/prospect U25: {int(components['bucket_non_nhl_u25_count'])}. "
            f"Pipeline capacity ceiling: {components['pipeline_capacity_ceiling']:.0%}. "
            f"{contract_note}"
            f"Team status: {TEAM_STATUS_LABELS.get(status, status)}. {coverage_note}. "
            f"Roster basis: {context.snapshot_label}. "
            f"Current role examples: {examples or 'not available'}. "
            f"U25 peer pipeline examples: {peer_examples or 'not available'}."
        ),
    }


def team_adjusted_score(board_score: float, team_fit: dict[str, object]) -> float:
    fit_score = float(team_fit.get("score", 0.0))
    return (board_score * 0.85) + (fit_score * 0.15)


def candidate_role_bucket(position: str) -> str:
    normalized = position.strip().upper()
    if normalized == "G":
        return "goalie"
    if normalized in {"D", "LD", "RD", "LHD", "RHD"}:
        return "defense"
    if normalized.startswith("C"):
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


def team_fit_components(
    row: dict[str, str],
    prospect: HistoricalProspect,
    tool_score: float,
    context_rows: list[dict[str, str]] | None = None,
) -> dict[str, float]:
    roster_need = roster_need_score(row, tool_score)
    pipeline_profile = bucket_pipeline_profile(row, context_rows)
    bucket_u25 = int(pipeline_profile["bucket_u25_count"])
    bucket_players = int(pipeline_profile["bucket_player_count"])
    pipeline_need = pipeline_need_score(row, prospect, tool_score, pipeline_profile)
    pipeline_ceiling = pipeline_need_ceiling(prospect, pipeline_profile)
    timeline_fit = timeline_fit_score(row, prospect)
    risk_fit = risk_appetite_score(prospect, row)
    contract_opportunity = contract_opportunity_score(row)
    contract_coverage = safe_float(row.get("contract_coverage", "0"))
    if contract_coverage >= 0.50:
        overall = (
            (roster_need * 0.32)
            + (pipeline_need * 0.30)
            + (timeline_fit * 0.16)
            + (risk_fit * 0.12)
            + (contract_opportunity * 0.10)
        )
    else:
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
        "pipeline_capacity_ceiling": pipeline_ceiling,
        "timeline_fit_score": timeline_fit,
        "risk_appetite_score": risk_fit,
        "contract_opportunity_score": contract_opportunity,
        "contract_coverage": contract_coverage,
        "contract_commitment_score": safe_float(row.get("contract_commitment_score", "0")),
        "roster_flexibility_score": safe_float(row.get("roster_flexibility_score", "0.5")),
        "bucket_u25_count": bucket_u25,
        "bucket_nhl_u25_count": pipeline_profile["bucket_nhl_u25_count"],
        "bucket_ahl_u25_count": pipeline_profile["bucket_ahl_u25_count"],
        "bucket_non_nhl_u25_count": pipeline_profile["bucket_non_nhl_u25_count"],
        "bucket_player_count": bucket_players,
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


def pipeline_need_ceiling(
    prospect: HistoricalProspect,
    pipeline_profile: dict[str, float],
) -> float:
    """Limit subtype need when the broader position pipeline is already occupied."""
    bucket = candidate_role_bucket(prospect.position)
    under_25 = int(pipeline_profile["bucket_u25_count"])
    nhl_u25 = int(pipeline_profile["bucket_nhl_u25_count"])
    non_nhl_u25 = int(pipeline_profile["bucket_non_nhl_u25_count"])
    u25_capacity = {"goalie": 2, "center": 4, "wing": 8, "defense": 6}.get(bucket, 4)
    nhl_capacity = {"goalie": 1, "center": 3, "wing": 4, "defense": 4}.get(bucket, 3)
    development_capacity = {"goalie": 2, "center": 4, "wing": 6, "defense": 5}.get(bucket, 4)
    total_occupancy = min(1.0, under_25 / u25_capacity)
    nhl_occupancy = min(1.0, nhl_u25 / nhl_capacity)
    development_occupancy = min(1.0, non_nhl_u25 / development_capacity)
    structural_pressure = (
        (total_occupancy * 0.30) + (nhl_occupancy * 0.45) + (development_occupancy * 0.20)
    )
    return min(1.0, max(0.0, 1.0 - structural_pressure))


def contract_opportunity_score(row: dict[str, str]) -> float:
    coverage = safe_float(row.get("contract_coverage", "0"))
    if coverage < 0.50:
        return 0.50
    commitment = safe_float(row.get("contract_commitment_score", "0"))
    players = max(1, safe_int(row.get("players", "0")))
    expiring_share = safe_int(row.get("expiring_contracts", "0")) / players
    return min(1.0, max(0.0, 1.0 - commitment + (expiring_share * 0.20)))


def bucket_pipeline_counts(
    row: dict[str, str], context_rows: list[dict[str, str]] | None
) -> tuple[int, int]:
    profile = bucket_pipeline_profile(row, context_rows)
    return int(profile["bucket_u25_count"]), int(profile["bucket_player_count"])


def bucket_pipeline_profile(
    row: dict[str, str], context_rows: list[dict[str, str]] | None
) -> dict[str, float]:
    rows = context_rows or [row]
    bucket = row.get("role_bucket", "")
    same_bucket_rows = [item for item in rows if item.get("role_bucket") == bucket]
    nhl_u25 = sum(
        safe_int(item.get("under_25", "0"))
        for item in same_bucket_rows
        if item.get("league_level") == "NHL"
    )
    ahl_u25 = sum(
        safe_int(item.get("under_25", "0"))
        for item in same_bucket_rows
        if item.get("league_level") == "AHL"
    )
    total_u25 = sum(safe_int(item.get("under_25", "0")) for item in same_bucket_rows)
    return {
        "bucket_u25_count": float(total_u25),
        "bucket_nhl_u25_count": float(nhl_u25),
        "bucket_ahl_u25_count": float(ahl_u25),
        "bucket_non_nhl_u25_count": float(max(0, total_u25 - nhl_u25)),
        "bucket_player_count": float(
            sum(safe_int(item.get("players", "0")) for item in same_bucket_rows)
        ),
    }


def peer_pipeline_examples(
    row: dict[str, str], context_rows: list[dict[str, str]], limit: int = 5
) -> str:
    bucket = row.get("role_bucket", "")
    rows = [
        item
        for item in context_rows
        if item.get("role_bucket") == bucket
        and safe_int(item.get("under_25", "0")) > 0
        and item.get("u25_example_players", "").strip()
    ]
    rows.sort(key=peer_example_sort_key)
    examples: list[str] = []
    for item in rows:
        for name in split_example_players(item.get("u25_example_players", "")):
            if name and name not in examples:
                examples.append(name)
            if len(examples) >= limit:
                return "; ".join(examples)
    return "; ".join(examples)


def peer_example_sort_key(row: dict[str, str]) -> tuple[int, int, float]:
    level_order = 0 if row.get("league_level") == "NHL" else 1
    role_order = (
        0 if row.get("role_type", "").startswith(("two_way", "puck_moving", "starter")) else 1
    )
    return (level_order, role_order, -safe_int(row.get("under_25", "0")))


def split_example_players(value: str) -> list[str]:
    return [item.strip() for item in value.split(";") if item.strip()]


def pipeline_need_score(
    row: dict[str, str],
    prospect: HistoricalProspect,
    tool_score: float,
    pipeline_profile: dict[str, float] | None = None,
) -> float:
    profile = pipeline_profile or bucket_pipeline_profile(row, [row])
    bucket_under_25 = int(profile["bucket_u25_count"])
    bucket_players = int(profile["bucket_player_count"])
    bucket_nhl_u25 = int(profile["bucket_nhl_u25_count"])
    bucket_non_nhl_u25 = int(profile["bucket_non_nhl_u25_count"])
    target = safe_float(row.get("scarcity_target", "0")) or 1.0
    under_25 = safe_int(row.get("under_25", "0"))
    players = safe_int(row.get("players", "0"))
    role_type = row.get("role_type", "")
    bucket = candidate_role_bucket(prospect.position)
    premium_role = role_type in {
        "puck_moving_defense",
        "two_way_defense",
        "scoring_center",
        "scoring_wing",
        "starter_goalie",
    }
    u25_pressure = min(1.0, under_25 / max(1.0, target))
    roster_saturation = min(1.0, players / max(1.0, target + 1.0))
    score = 1.0 - ((u25_pressure * 0.62) + (roster_saturation * 0.25))
    bucket_pressure = bucket_pipeline_pressure(bucket, bucket_under_25, bucket_players)
    score -= bucket_pressure
    score -= readiness_pipeline_pressure(bucket, bucket_nhl_u25, bucket_non_nhl_u25)
    if premium_role and under_25 >= 2:
        score -= 0.18
    if bucket == "defense" and under_25 >= 4:
        score -= 0.25
    if bucket == "goalie" and under_25 >= 2:
        score -= 0.15
    if tool_score >= 0.75 and under_25 == 0:
        score += 0.08
    return min(pipeline_need_ceiling(prospect, profile), max(0.0, score))


def readiness_pipeline_pressure(bucket: str, nhl_u25: int, non_nhl_u25: int) -> float:
    if bucket == "goalie":
        return min(0.28, (nhl_u25 * 0.10) + (non_nhl_u25 * 0.08))
    if bucket == "defense":
        return min(0.32, (nhl_u25 * 0.13) + (non_nhl_u25 * 0.06))
    if bucket == "center":
        return min(0.34, (nhl_u25 * 0.14) + (non_nhl_u25 * 0.06))
    if bucket == "wing":
        return min(0.28, (nhl_u25 * 0.09) + (non_nhl_u25 * 0.04))
    return 0.0


def bucket_pipeline_pressure(bucket: str, under_25: int, players: int) -> float:
    if bucket == "goalie":
        if under_25 >= 3:
            return 0.30
        if under_25 >= 2:
            return 0.22
        if under_25 >= 1 and players >= 4:
            return 0.12
        return 0.0
    if bucket == "center":
        if under_25 >= 4:
            return 0.28
        if under_25 >= 2:
            return 0.20
        return 0.0
    if bucket == "wing":
        if under_25 >= 6:
            return 0.26
        if under_25 >= 4:
            return 0.18
        return 0.0
    if bucket == "defense":
        if under_25 >= 5:
            return 0.28
        if under_25 >= 3:
            return 0.18
        return 0.0
    return 0.0


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
    junior_markers = (
        "JRS",
        "JR.",
        "J20",
        "U20",
        "U18",
        "OHL",
        "WHL",
        "QMJHL",
        "USHL",
        "NTDP",
        "NCAA",
    )
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
    qualitative_flags = scouting_qualitative_flags(prospect)
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
            "advanced_games": int(board_row["advanced_games"]),
            "advanced_sample_weight": float(board_row["advanced_sample_weight"]),
            "advanced_role_score": float(board_row["advanced_role_score"]),
            "ep_tool_score": float(board_row["ep_tool_score"]),
            "team_fit_score": float(board_row["team_fit_score"]),
            "evidence_depth": board_row["evidence_depth"],
        },
        "why_high": build_why_high(board_row, qualitative_flags),
        "risk_flags": build_risk_flags(board_row, qualitative_flags),
        "team_fit": {
            "team_id": board_row["team_fit_team"],
            "role": board_row["team_fit_role"],
            "need": board_row["team_fit_need"],
            "score": float(board_row["team_fit_score"]),
            "team_adjusted_score": float(board_row["team_adjusted_score"]),
            "reason": board_row["team_fit_reason"],
        },
        "team_fit_options": team_fit_options or [],
        "stat_evidence": build_stat_evidence(prospect, board_row, qualitative_flags),
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


def build_stat_evidence(
    prospect: HistoricalProspect,
    board_row: dict[str, str],
    qualitative_flags: list[str] | None = None,
) -> dict[str, object]:
    lines = prospect.pre_draft_stat_lines or []
    games = sum(line.games for line in lines)
    goals = sum(line.goals for line in lines)
    assists = sum(line.assists for line in lines)
    points = sum(line.total_points for line in lines)
    regular_games = sum(line.games for line in lines if line.regular_season)
    playoff_games = max(0, games - regular_games)
    adult_games = sum(line.games for line in lines if is_adult_league(line.league))
    leagues = sorted({line.league for line in lines if line.league})
    sources = sorted({line.source or "unknown" for line in lines})
    goalie_lines = [
        line
        for line in lines
        if line.save_percentage is not None
        or line.goals_against_average is not None
        or line.saves is not None
        or line.shots_against is not None
    ]
    goalie_games = sum(line.games for line in goalie_lines)
    goalie_minutes = sum(line.goalie_minutes or 0.0 for line in goalie_lines)
    shots_against = sum(line.shots_against or 0 for line in goalie_lines)
    saves = sum(line.saves or 0 for line in goalie_lines)
    goals_against = sum(line.goals_against or 0 for line in goalie_lines)
    save_percentage = (
        saves / shots_against
        if shots_against
        else weighted_average([(line.save_percentage, line.games) for line in goalie_lines])
    )
    goals_against_average = (
        goals_against * 60 / goalie_minutes
        if goalie_minutes
        else weighted_average([(line.goals_against_average, line.games) for line in goalie_lines])
    )
    return {
        "role_group": board_row["role_group"],
        "stat_lines": len(lines),
        "source_count": len(sources),
        "sources": sources,
        "league_count": len(leagues),
        "leagues": leagues,
        "games": games,
        "goals": goals,
        "assists": assists,
        "points": points,
        "points_per_game": points / games if games else 0.0,
        "regular_games": regular_games,
        "playoff_games": playoff_games,
        "playoff_game_share": playoff_games / games if games else 0.0,
        "adult_games": adult_games,
        "adult_game_share": adult_games / games if games else 0.0,
        "goalie_games": goalie_games,
        "goalie_minutes": round(goalie_minutes, 1),
        "goalie_shots_against": shots_against,
        "goalie_saves": saves,
        "goalie_goals_against": goals_against,
        "goalie_save_percentage": save_percentage,
        "goalie_goals_against_average": goals_against_average,
        "goalie_wins": sum(line.wins or 0 for line in goalie_lines),
        "goalie_losses": sum(line.losses or 0 for line in goalie_lines),
        "goalie_shutouts": sum(line.shutouts or 0 for line in goalie_lines),
        "goalie_quality_score": float(board_row["goalie_quality_score"]),
        "advanced_games": int(board_row.get("advanced_games", "0")),
        "advanced_sample_weight": float(board_row.get("advanced_sample_weight", "0")),
        "plus_minus_per_game": float(board_row.get("plus_minus_per_game", "0")),
        "shots_per_game": float(board_row.get("shots_per_game", "0")),
        "blocks_per_game": float(board_row.get("blocks_per_game", "0")),
        "faceoff_percentage": float(board_row.get("faceoff_percentage", "0")),
        "advanced_role_score": float(board_row.get("advanced_role_score", "0")),
        "qualitative_flags": qualitative_flags or scouting_qualitative_flags(prospect),
    }


def scouting_qualitative_flags(prospect: HistoricalProspect) -> list[str]:
    text = prospect.scouting_text.lower()
    flags: list[str] = []
    if "championship contender" in text or "championship" in text or "won cup" in text:
        flags.append("EP role flag: championship-team context")
    if "important role" in text or "key role" in text or "critical role" in text:
        flags.append("EP role flag: important team role")
    if "playoff" in text:
        flags.append("EP role flag: playoff context")
    return flags


def weighted_average(values: list[tuple[float | None, int]]) -> float:
    numerator = 0.0
    denominator = 0
    for value, weight in values:
        if value is None:
            continue
        numerator += value * max(weight, 1)
        denominator += max(weight, 1)
    return numerator / denominator if denominator else 0.0


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
    if (
        feature.get("is_goalie") == "1"
        and float(feature.get("goalie_quality_score", "0") or 0) == 0.0
    ):
        risks.append("Goalie metrics not yet captured")
    if abs(consensus_delta) >= 10:
        risks.append("Board-consensus gap needs review")
    return ", ".join(risks[:2]) or "No major coverage flags in current sample."


def build_why_high(
    board_row: dict[str, str], qualitative_flags: list[str] | None = None
) -> list[str]:
    points: list[str] = []
    if float(board_row.get("ep_tool_score", "0") or 0) >= 0.75:
        points.append(
            "Elite Prospects guide grades push this player above the pure stat-only view."
        )
    elif float(board_row.get("ep_tool_score", "0") or 0) > 0:
        points.append(
            "Elite Prospects guide grades add a scouting-evidence layer beyond production."
        )
    if float(board_row.get("team_fit_score", "0") or 0) >= 0.65:
        points.append(
            f"{board_row['team_fit_team']} roster context flags this role as a strong fit."
        )
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
        points.append(
            "Goalie evaluation uses save percentage, goals-against context, and workload fields."
        )
    if qualitative_flags:
        points.append(
            "Scouting text adds role/context evidence not fully captured in the current stat rows."
        )
    if int(board_row["pre_draft_league_count"]) > 1:
        points.append(
            "Multi-league history helps separate one-team context from broader performance."
        )
    if not points:
        points.append(
            "Profile remains in range across consensus, role, and league-context signals."
        )
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


def build_risk_flags(
    board_row: dict[str, str], qualitative_flags: list[str] | None = None
) -> list[str]:
    flags: list[str] = []
    if int(board_row["pre_draft_row_count"]) == 1:
        flags.append(
            "Only one pre-draft stat row is currently captured; treat the grade as review-ready, not final."
        )
    if float(board_row["adult_game_share"]) == 0.0:
        flags.append("No adult-league sample is present, so junior translation remains a question.")
    elif board_row.get("meaningful_adult_sample") != "1":
        flags.append(
            "Adult-league exposure is present, but the game sample is too small to carry much weight."
        )
    if float(board_row["playoff_game_share"]) == 0.0 and qualitative_flags:
        flags.append(
            "Scouting text indicates playoff/championship role context, but playoff stat rows are not captured yet."
        )
    elif float(board_row["playoff_game_share"]) == 0.0:
        flags.append("No playoff row is captured yet; pressure-sample context may be incomplete.")
    elif board_row.get("meaningful_playoff_sample") != "1":
        flags.append("Playoff exposure is present, but the game sample is still thin.")
    if board_row["role_group"] == "goalie" and float(board_row["goalie_quality_score"]) == 0.0:
        flags.append("Goalie-specific performance fields are not yet populated for this player.")
    if abs(int(board_row["consensus_delta"])) >= 10:
        flags.append(
            "Board rank and public consensus differ enough to warrant a scouting-room review."
        )
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
    player_details: list[dict[str, object]] | None = None,
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
            "team_views": [],
        }

    evidence_depth_counts: dict[str, int] = {}
    disagreement_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    for row in board_rows:
        evidence_depth_counts[row["evidence_depth"]] = (
            evidence_depth_counts.get(row["evidence_depth"], 0) + 1
        )
        disagreement_counts[row["disagreement_bucket"]] = (
            disagreement_counts.get(row["disagreement_bucket"], 0) + 1
        )
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
        "team_views": build_manifest_team_views(team_contexts or {}, player_details or []),
    }


def build_manifest_team_contexts(
    contexts: dict[str, TeamFitContext], team_id: str = ""
) -> dict[str, object]:
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


def build_manifest_team_views(
    contexts: dict[str, TeamFitContext],
    player_details: list[dict[str, object]],
) -> list[dict[str, object]]:
    views: list[dict[str, object]] = []
    for context in sorted(contexts.values(), key=lambda item: (item.team_name, item.team_id)):
        team_options = team_fit_options_for_team(player_details, context.team_id)
        views.append(
            {
                "team_id": context.team_id,
                "team_name": context.team_name,
                "team_status": team_status(context.team_id),
                "team_status_label": TEAM_STATUS_LABELS.get(
                    team_status(context.team_id), team_status(context.team_id)
                ),
                "snapshot_label": context.snapshot_label,
                "snapshot_warning": context.snapshot_warning,
                "ahl_coverage": "available"
                if any(row.get("league_level") == "AHL" for row in context.depth_rows)
                else "missing",
                "role_gaps": build_team_role_gaps(context),
                "top_matches": team_options[:8],
                "strong_match_count": sum(
                    1 for option in team_options if float(option["score"]) >= 0.65
                ),
                "useful_match_count": sum(
                    1 for option in team_options if float(option["score"]) >= 0.40
                ),
            }
        )
    return views


def team_fit_options_for_team(
    player_details: list[dict[str, object]], team_id: str
) -> list[dict[str, object]]:
    matches: list[dict[str, object]] = []
    for detail in player_details:
        header = detail.get("header", {})
        for option in detail.get("team_fit_options", []):
            if option.get("team_id") != team_id:
                continue
            matches.append(
                {
                    "player_id": detail.get("player_id", ""),
                    "name": header.get("name", ""),
                    "position": header.get("position", ""),
                    "board_rank": header.get("board_rank", 0),
                    "consensus_rank": header.get("consensus_rank", 0),
                    "role": option.get("role_type", ""),
                    "need": option.get("need_label", ""),
                    "score": option.get("score", 0.0),
                    "team_adjusted_score": option.get("team_adjusted_score", 0.0),
                    "pipeline_need_score": option.get("pipeline_need_score", 0.0),
                    "timeline_fit_score": option.get("timeline_fit_score", 0.0),
                    "risk_appetite_score": option.get("risk_appetite_score", 0.0),
                    "contract_opportunity_score": option.get("contract_opportunity_score", 0.5),
                    "contract_coverage": option.get("contract_coverage", 0.0),
                    "bucket_u25_count": option.get("bucket_u25_count", 0),
                    "bucket_nhl_u25_count": option.get("bucket_nhl_u25_count", 0),
                    "bucket_ahl_u25_count": option.get("bucket_ahl_u25_count", 0),
                    "bucket_non_nhl_u25_count": option.get("bucket_non_nhl_u25_count", 0),
                }
            )
    return sorted(
        matches,
        key=lambda item: (
            float(item["score"]),
            float(item["team_adjusted_score"]),
            -int(item["board_rank"] or 999),
        ),
        reverse=True,
    )


def build_team_role_gaps(context: TeamFitContext) -> list[dict[str, object]]:
    gaps: list[dict[str, object]] = []
    for row in context.depth_rows:
        scarcity = safe_float(row.get("scarcity_score", "0"))
        under_25 = safe_int(row.get("under_25", "0"))
        players = safe_int(row.get("players", "0"))
        target = safe_float(row.get("scarcity_target", "0"))
        avg_age = safe_float(row.get("avg_age", "0"))
        same_bucket = bucket_pipeline_profile(row, context.depth_rows)
        nhl_u25 = int(same_bucket["bucket_nhl_u25_count"])
        non_nhl_u25 = int(same_bucket["bucket_non_nhl_u25_count"])
        readiness_penalty = readiness_pipeline_pressure(
            row.get("role_bucket", ""), nhl_u25, non_nhl_u25
        )
        role_priority = (
            scarcity
            + (0.18 if under_25 == 0 else 0.0)
            + (0.08 if avg_age >= 30 else 0.0)
            - min(0.30, readiness_penalty * 0.55)
        )
        gaps.append(
            {
                "role_bucket": row.get("role_bucket", ""),
                "role_type": row.get("role_type", ""),
                "league_level": row.get("league_level", ""),
                "players": players,
                "under_25": under_25,
                "bucket_nhl_u25_count": nhl_u25,
                "bucket_non_nhl_u25_count": non_nhl_u25,
                "readiness_pipeline_pressure": readiness_penalty,
                "scarcity_target": target,
                "scarcity_score": scarcity,
                "avg_age": avg_age,
                "priority_score": min(1.0, max(0.0, role_priority)),
                "example_players": row.get("example_players", ""),
            }
        )
    return sorted(
        gaps,
        key=lambda item: (
            float(item["priority_score"]),
            float(item["scarcity_score"]),
            -int(item["under_25"]),
        ),
        reverse=True,
    )[:8]


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
