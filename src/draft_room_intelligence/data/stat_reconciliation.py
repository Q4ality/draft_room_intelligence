"""Reconcile duplicate season stat rows from multiple sources."""

from __future__ import annotations

from dataclasses import dataclass

from draft_room_intelligence.data.eliteprospects_csv import SEASON_STAT_LINE_COLUMNS


RECONCILIATION_AUDIT_COLUMNS = [
    "player_id",
    "season",
    "league",
    "team",
    "regular_season",
    "row_count",
    "sources",
    "action",
    "conflict_fields",
    "chosen_sources",
]

IDENTITY_COLUMNS = ["player_id", "season", "league", "team", "regular_season"]
SOURCE_COLUMNS = ["source", "source_id", "source_url"]
SKATER_STAT_COLUMNS = ["games", "goals", "assists", "points"]
GOALIE_STAT_COLUMNS = [
    "goalie_minutes",
    "shots_against",
    "saves",
    "goals_against",
    "save_percentage",
    "goals_against_average",
    "wins",
    "losses",
    "ties",
    "shutouts",
]
MERGE_COLUMNS = [
    "age",
    "timing",
    *SKATER_STAT_COLUMNS,
    *GOALIE_STAT_COLUMNS,
]

TEAM_ALIASES_BY_LEAGUE = {
    "ohl": {
        "BAR": "Barrie Colts",
        "BFD": "Brantford Bulldogs",
        "BRAM": "Brampton Steelheads",
        "ER": "Erie Otters",
        "FLNT": "Flint Firebirds",
        "GUE": "Guelph Storm",
        "KGN": "Kingston Frontenacs",
        "KIT": "Kitchener Rangers",
        "LDN": "London Knights",
        "NB": "North Bay Battalion",
        "NIAG": "Niagara IceDogs",
        "OSH": "Oshawa Generals",
        "OTT": "Ottawa 67's",
        "OS": "Owen Sound Attack",
        "PBO": "Peterborough Petes",
        "SAR": "Sarnia Sting",
        "SAG": "Saginaw Spirit",
        "SOO": "Soo Greyhounds",
        "SBY": "Sudbury Wolves",
        "WSR": "Windsor Spitfires",
    },
    "qmjhl": {
        "BAC": "Acadie-Bathurst Titan",
        "BB": "Blainville-Boisbriand Armada",
        "CHA": "Charlottetown Islanders",
        "CHI": "Chicoutimi Saguenéens",
        "DRU": "Drummondville Voltigeurs",
        "GAT": "Gatineau Olympiques",
        "HAL": "Halifax Mooseheads",
        "MON": "Moncton Wildcats",
        "QUE": "Québec Remparts",
        "RIM": "Rimouski Océanic",
        "ROU": "Rouyn-Noranda Huskies",
        "SHA": "Shawinigan Cataractes",
        "SHE": "Sherbrooke Phoenix",
        "SNB": "Saint John Sea Dogs",
        "VDO": "Val-d'Or Foreurs",
        "VIC": "Victoriaville Tigres",
    },
    "whl": {
        "BDN": "Brandon Wheat Kings",
        "CGY": "Calgary Hitmen",
        "EDM": "Edmonton Oil Kings",
        "EVT": "Everett Silvertips",
        "KAM": "Kamloops Blazers",
        "KEL": "Kelowna Rockets",
        "LET": "Lethbridge Hurricanes",
        "MJ": "Moose Jaw Warriors",
        "PG": "Prince George Cougars",
        "POR": "Portland Winterhawks",
        "RD": "Red Deer Rebels",
        "REG": "Regina Pats",
        "SAS": "Saskatoon Blades",
        "SEA": "Seattle Thunderbirds",
        "SPO": "Spokane Chiefs",
        "SC": "Swift Current Broncos",
        "TC": "Tri-City Americans",
        "VAN": "Vancouver Giants",
        "VIC": "Victoria Royals",
        "WEN": "Wenatchee Wild",
    },
}


@dataclass(frozen=True)
class StatReconciliationResult:
    rows: list[dict[str, str]]
    audit_rows: list[dict[str, str]]
    duplicate_groups: int
    conflict_groups: int


def reconcile_stat_lines(rows: list[dict[str, str]]) -> StatReconciliationResult:
    grouped: dict[tuple[str, str, str, str, str], list[dict[str, str]]] = {}
    for row in rows:
        normalized = normalize_stat_row(row)
        grouped.setdefault(reconciliation_key(normalized), []).append(normalized)

    output_rows: list[dict[str, str]] = []
    audit_rows: list[dict[str, str]] = []
    duplicate_groups = 0
    conflict_groups = 0
    for key in sorted(grouped):
        group = grouped[key]
        if len(group) == 1:
            output_rows.append(group[0])
            continue
        duplicate_groups += 1
        merged, conflict_fields, chosen_sources = merge_stat_group(group)
        if conflict_fields:
            conflict_groups += 1
        output_rows.append(merged)
        audit_rows.append(
            {
                "player_id": key[0],
                "season": key[1],
                "league": key[2],
                "team": key[3],
                "regular_season": key[4],
                "row_count": str(len(group)),
                "sources": "; ".join(sorted({row.get("source", "") for row in group if row.get("source", "")})),
                "action": "merged_with_conflicts" if conflict_fields else "merged",
                "conflict_fields": "; ".join(conflict_fields),
                "chosen_sources": "; ".join(chosen_sources),
            }
        )

    return StatReconciliationResult(
        rows=output_rows,
        audit_rows=audit_rows,
        duplicate_groups=duplicate_groups,
        conflict_groups=conflict_groups,
    )


def merge_stat_group(rows: list[dict[str, str]]) -> tuple[dict[str, str], list[str], list[str]]:
    base = max(rows, key=source_priority)
    merged = dict(base)
    conflict_fields: list[str] = []
    chosen_sources: list[str] = []
    for column in MERGE_COLUMNS:
        values = [row for row in rows if row.get(column)]
        if not values:
            merged[column] = ""
            continue
        chosen = max(values, key=lambda row: (source_priority(row), value_specificity(row.get(column, ""))))
        normalized_values = {
            normalize_stat_value(column, row.get(column, ""))
            for row in values
            if normalize_stat_value(column, row.get(column, ""))
        }
        if len(normalized_values) > 1:
            conflict_fields.append(column)
        merged[column] = chosen[column]
        chosen_sources.append(f"{column}:{chosen.get('source', '') or 'unknown'}")

    merged["source"] = merge_source_labels(rows)
    source_owner = max(rows, key=source_priority)
    merged["source_id"] = source_owner.get("source_id", "")
    merged["source_url"] = source_owner.get("source_url", "")
    return normalize_stat_row(merged), conflict_fields, chosen_sources


def normalize_stat_row(row: dict[str, str]) -> dict[str, str]:
    normalized = {column: str(row.get(column, "") or "").strip() for column in SEASON_STAT_LINE_COLUMNS}
    normalized["regular_season"] = normalize_regular_season(normalized.get("regular_season", ""))
    return normalized


def reconciliation_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        row.get("player_id", ""),
        row.get("season", ""),
        normalize_key_value(row.get("league", "")),
        normalize_team_key(row.get("league", ""), row.get("team", "")),
        normalize_regular_season(row.get("regular_season", "")),
    )


def normalize_team_key(league: str, team: str) -> str:
    league_key = normalize_key_value(league)
    alias = TEAM_ALIASES_BY_LEAGUE.get(league_key, {}).get(team.strip().upper())
    return normalize_key_value(alias or team)


def normalize_key_value(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())


def normalize_regular_season(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"false", "0", "no", "playoffs", "playoff"}:
        return "false"
    return "true"


def normalize_stat_value(column: str, value: str) -> str:
    stripped = value.strip()
    if not stripped:
        return ""
    if column == "save_percentage" and stripped.startswith("."):
        return f"0{stripped}"
    try:
        numeric = float(stripped)
    except ValueError:
        return stripped.lower()
    return f"{numeric:.3f}".rstrip("0").rstrip(".")


def source_priority(row: dict[str, str]) -> int:
    labels = source_labels(row.get("source", ""))
    if labels & {"chl", "ushl", "open-stats"}:
        return 60
    if labels & {"puckpedia"}:
        return 55
    if labels & {"eliteprospects", "eliteprospects_pdf", "eliteprospects_pdf_vision"}:
        return 50
    if labels & {"wikipedia-career"}:
        return 25
    if labels & {"wikipedia", "wikipedia_bio"}:
        return 15
    return 10


def source_labels(value: str) -> set[str]:
    labels: set[str] = set()
    for raw in value.replace("+", ";").split(";"):
        label = raw.strip()
        if label:
            labels.add(label)
    return labels


def value_specificity(value: str) -> int:
    return len(value.strip())


def merge_source_labels(rows: list[dict[str, str]]) -> str:
    labels: list[str] = []
    for row in sorted(rows, key=source_priority, reverse=True):
        for label in source_labels(row.get("source", "")):
            if label not in labels:
                labels.append(label)
    return "; ".join(labels)
