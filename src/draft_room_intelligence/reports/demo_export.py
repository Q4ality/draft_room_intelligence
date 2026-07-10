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
    "average_league_weight",
    "pre_draft_row_count",
    "pre_draft_league_count",
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
    "evidence_depth",
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
            "average_league_weight": feature["average_league_weight"],
            "pre_draft_row_count": feature["pre_draft_row_count"],
            "pre_draft_league_count": feature["pre_draft_league_count"],
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
                "source": "mixed",
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
    if float(feature["adult_game_share"]) > 0.15:
        badges.append("Adult-League")
    if int(feature["pre_draft_league_count"]) > 1:
        badges.append("Multi-League")
    if classify_evidence_depth(feature) == "low":
        badges.append("Low Evidence")
    return badges


def build_short_reason(feature: dict[str, str], disagreement_bucket: str) -> str:
    reasons: list[str] = []
    if float(feature["role_percentile"]) >= 0.9:
        reasons.append("Strong same-role production")
    if float(feature["average_league_weight"]) >= 1.0:
        reasons.append("Good competition context")
    if float(feature["adult_game_share"]) > 0.15:
        reasons.append("Meaningful adult exposure")
    if int(feature["pre_draft_league_count"]) > 1:
        reasons.append("Multi-league evidence")
    if disagreement_bucket == "model_higher":
        reasons.append("Model sees more upside than consensus")
    return ", ".join(reasons[:2]) or "Balanced profile with usable evidence."


def build_risk_note(feature: dict[str, str], consensus_delta: int) -> str:
    risks: list[str] = []
    if int(feature["pre_draft_row_count"]) == 1:
        risks.append("Thin evidence base")
    if float(feature["adult_game_share"]) == 0.0:
        risks.append("No adult-league exposure yet")
    if float(feature["playoff_game_share"]) == 0.0:
        risks.append("Limited playoff signal")
    if abs(consensus_delta) >= 10:
        risks.append("Large disagreement versus consensus")
    return ", ".join(risks[:2]) or "Normal variance remains in the profile."


def build_why_high(board_row: dict[str, str]) -> list[str]:
    points: list[str] = []
    if float(board_row["role_percentile"]) >= 0.9:
        points.append("Strong role-adjusted production relative to peers.")
    if float(board_row["average_league_weight"]) >= 1.0:
        points.append("Primary competition context is stronger than average.")
    if float(board_row["adult_game_share"]) > 0.15:
        points.append("Meaningful adult-league exposure boosts confidence.")
    if int(board_row["pre_draft_league_count"]) > 1:
        points.append("Multi-league history provides deeper evidence.")
    if not points:
        points.append("Profile remains competitive across core board signals.")
    return points[:3]


def build_risk_flags(board_row: dict[str, str]) -> list[str]:
    flags: list[str] = []
    if int(board_row["pre_draft_row_count"]) == 1:
        flags.append("Limited pre-draft evidence depth.")
    if float(board_row["adult_game_share"]) == 0.0:
        flags.append("No adult-league exposure before draft.")
    if float(board_row["playoff_game_share"]) == 0.0:
        flags.append("Little or no playoff signal in the current sample.")
    if abs(int(board_row["consensus_delta"])) >= 10:
        flags.append("Large disagreement between board rank and consensus rank.")
    if not flags:
        flags.append("No outsized structural risk flags from the current data.")
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

    featured = sorted(
        board_rows,
        key=lambda row: (abs(int(row["consensus_delta"])), -int(row["board_rank"])),
        reverse=True,
    )[:10]
    return {
        "draft_year": prospects[0].draft_year,
        "player_count": len(prospects),
        "dataset_status": classify_dataset_status(board_rows),
        "evidence_depth_counts": evidence_depth_counts,
        "disagreement_counts": disagreement_counts,
        "source_counts": source_counts,
        "featured_player_ids": [row["player_id"] for row in featured],
    }


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
