"""Rule-based scouting text extraction placeholder.

Later this can be replaced by LLM + schema extraction while keeping the same
ScoutingFeatures output shape.
"""

from __future__ import annotations

from draft_room_intelligence.domain import Prospect, ScoutingFeatures


KEYWORDS = {
    "skating_positive": ("fast", "explosive", "separation", "edges", "transition"),
    "skating_risk": ("heavy feet", "burst", "pace", "skating concern"),
    "iq_positive": ("reads", "anticipates", "intelligent", "mature", "processes"),
    "compete_positive": ("compete", "motor", "forecheck", "engagement"),
    "defense_positive": ("defensive", "two-way", "matchup", "reliable", "detail"),
    "skill_positive": ("hands", "release", "creator", "playmaking", "dynamic", "power-play"),
    "risk": ("inconsistent", "perimeter", "needs", "risk", "limited", "not a high-end"),
}


def extract_scouting_features(prospect: Prospect) -> ScoutingFeatures:
    text = prospect.scouting_text.lower()

    skating = score_keywords(text, KEYWORDS["skating_positive"]) - score_keywords(
        text, KEYWORDS["skating_risk"], weight=0.35
    )
    hockey_iq = score_keywords(text, KEYWORDS["iq_positive"])
    compete = score_keywords(text, KEYWORDS["compete_positive"])
    defense = score_keywords(text, KEYWORDS["defense_positive"])
    skill = score_keywords(text, KEYWORDS["skill_positive"])

    risk_tags = tuple(keyword for keyword in KEYWORDS["risk"] if keyword in text)
    evidence = tuple(sentence.strip() for sentence in prospect.scouting_text.split(".") if sentence.strip())[:3]
    role_projection = infer_role(text, prospect.position)

    return ScoutingFeatures(
        player_id=prospect.player_id,
        skating_score=round(clamp_score(skating), 2),
        hockey_iq_score=round(clamp_score(hockey_iq), 2),
        compete_score=round(clamp_score(compete), 2),
        defense_score=round(clamp_score(defense), 2),
        skill_score=round(clamp_score(skill), 2),
        risk_tags=risk_tags,
        role_projection=role_projection,
        evidence=evidence,
    )


def score_keywords(text: str, keywords: tuple[str, ...], weight: float = 0.22) -> float:
    return sum(weight for keyword in keywords if keyword in text)


def clamp_score(value: float) -> float:
    return max(0.0, min(1.0, 0.45 + value))


def infer_role(text: str, position: str) -> str:
    if "middle-six" in text:
        return "middle-six forward"
    if "top-six" in text:
        return "top-six forward"
    if "matchup" in text and position == "C":
        return "matchup center"
    if position.endswith("HD") or position in {"RHD", "LHD"}:
        if "transition" in text:
            return "transition defenseman"
        return "two-way defenseman"
    return "needs role projection review"

