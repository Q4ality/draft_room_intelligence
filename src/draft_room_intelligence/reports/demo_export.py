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
    "board_score",
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


@dataclass(frozen=True)
class DemoExportBundle:
    board_rows: list[dict[str, str]]
    compare_rows: list[dict[str, str]]
    player_details: list[dict[str, object]]
    manifest: dict[str, object]


def build_demo_export_bundle(prospects: list[HistoricalProspect]) -> DemoExportBundle:
    feature_rows = [row.to_dict() for row in build_feature_rows(prospects)]
    features_by_id = {row["player_id"]: row for row in feature_rows}
    consensus = consensus_scores(prospects)
    model_scores = role_specific_hybrid_scores(prospects)
    board_scores = {
        player_id: evidence_weighted_board_score(
            model_scores[player_id],
            consensus[player_id],
            features_by_id[player_id],
        )
        for player_id in model_scores.keys() & consensus.keys() & features_by_id.keys()
    }
    ordered_ids = [
        player_id
        for player_id, _ in sorted(board_scores.items(), key=lambda item: (item[1], item[0]), reverse=True)
    ]
    board_ranks = {player_id: index for index, player_id in enumerate(ordered_ids, start=1)}

    board_rows: list[dict[str, str]] = []
    compare_rows: list[dict[str, str]] = []
    player_details: list[dict[str, object]] = []

    prospects_by_id = {prospect.player_id: prospect for prospect in prospects}
    for player_id in ordered_ids:
        prospect = prospects_by_id[player_id]
        feature = features_by_id[player_id]
        board_rank = board_ranks[player_id]
        consensus_rank = int(feature["consensus_rank"])
        consensus_delta = board_rank - consensus_rank
        disagreement_bucket = classify_disagreement(consensus_delta)
        evidence_depth = classify_evidence_depth(feature)
        badges = build_badges(feature, disagreement_bucket)
        short_reason = build_short_reason(feature, disagreement_bucket)
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
            "board_score": f"{board_scores[player_id]:.6f}",
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
            "evidence_depth": evidence_depth,
            "consensus_delta": str(consensus_delta),
            "disagreement_bucket": disagreement_bucket,
            "badges": "|".join(badges),
            "short_reason": short_reason,
            "risk_note": risk_note,
        }
        board_rows.append(board_row)
        compare_rows.append({column: board_row[column] for column in COMPARE_COLUMNS})
        player_details.append(build_player_detail(prospect, board_row))

    return DemoExportBundle(
        board_rows=board_rows,
        compare_rows=compare_rows,
        player_details=player_details,
        manifest=build_manifest(prospects, board_rows),
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


def build_player_detail(prospect: HistoricalProspect, board_row: dict[str, str]) -> dict[str, object]:
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
        },
        "summary": {
            "board_score": float(board_row["board_score"]),
            "model_score": float(board_row["model_score"]),
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
            "evidence_depth": board_row["evidence_depth"],
        },
        "why_high": build_why_high(board_row),
        "risk_flags": build_risk_flags(board_row),
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


def build_badges(feature: dict[str, str], disagreement_bucket: str) -> list[str]:
    badges: list[str] = []
    if disagreement_bucket == "model_higher":
        badges.append("Model Higher")
    elif disagreement_bucket == "consensus_higher":
        badges.append("Consensus Higher")
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


def build_short_reason(feature: dict[str, str], disagreement_bucket: str) -> str:
    reasons: list[str] = []
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


def build_manifest(prospects: list[HistoricalProspect], board_rows: list[dict[str, str]]) -> dict[str, object]:
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
    }


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
