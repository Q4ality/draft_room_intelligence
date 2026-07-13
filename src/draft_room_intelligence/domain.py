"""Domain objects used across the PoC.

These are intentionally small dataclasses. They make the demo pipeline easy to
replace later with pandas, DuckDB, Pydantic, or ORM-backed records.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class Prospect:
    player_id: str
    name: str
    draft_year: int
    position: str
    league: str
    age_at_draft: float
    height_cm: int
    weight_kg: int
    games: int
    goals: int
    assists: int
    consensus_rank: int
    scouting_text: str = ""

    @property
    def points(self) -> int:
        return self.goals + self.assists

    @property
    def points_per_game(self) -> float:
        if self.games == 0:
            return 0.0
        return self.points / self.games


@dataclass(frozen=True)
class SourceRecord:
    """Trace a normalized player row back to the raw source it came from."""

    source: str
    source_id: str
    player_name: str
    draft_year: int
    url: str = ""
    collected_at: date | None = None


@dataclass(frozen=True)
class ToolGrade:
    tool: str
    grade: float
    source: str = ""
    source_id: str = ""
    source_url: str = ""


@dataclass(frozen=True)
class PreDraftStatLine:
    """Stats that would have been available before a draft."""

    league: str
    team: str
    season: str
    games: int
    goals: int
    assists: int
    points: int | None = None
    regular_season: bool = True
    source: str = ""
    source_id: str = ""
    source_url: str = ""
    goalie_minutes: float | None = None
    shots_against: int | None = None
    saves: int | None = None
    goals_against: int | None = None
    save_percentage: float | None = None
    goals_against_average: float | None = None
    wins: int | None = None
    losses: int | None = None
    ties: int | None = None
    shutouts: int | None = None

    @property
    def total_points(self) -> int:
        if self.points is not None:
            return self.points
        return self.goals + self.assists

    @property
    def points_per_game(self) -> float:
        if self.games == 0:
            return 0.0
        return self.total_points / self.games


@dataclass(frozen=True)
class DevelopmentStatLine:
    """Season-level post-draft progress in any league or competition."""

    season: str
    league: str
    team: str
    games: int
    goals: int
    assists: int
    points: int | None = None
    age: float | None = None
    regular_season: bool = True
    source: str = ""
    source_id: str = ""
    source_url: str = ""
    goalie_minutes: float | None = None
    shots_against: int | None = None
    saves: int | None = None
    goals_against: int | None = None
    save_percentage: float | None = None
    goals_against_average: float | None = None
    wins: int | None = None
    losses: int | None = None
    ties: int | None = None
    shutouts: int | None = None

    @property
    def total_points(self) -> int:
        if self.points is not None:
            return self.points
        return self.goals + self.assists

    @property
    def points_per_game(self) -> float:
        if self.games == 0:
            return 0.0
        return self.total_points / self.games


@dataclass(frozen=True)
class DraftSelection:
    draft_year: int
    team_id: str
    round_number: int
    overall_pick: int


@dataclass(frozen=True)
class DraftOutcome:
    """Post-draft results used only for evaluation and backtests."""

    player_id: str
    nhl_games: int
    nhl_points: int
    seasons_played: int = 0
    time_to_nhl_years: float | None = None
    value_proxy: float | None = None

    @property
    def is_nhler(self) -> bool:
        return self.nhl_games >= 100

    @property
    def is_impact_player(self) -> bool:
        return self.nhl_games >= 200 or self.nhl_points >= 100

    @property
    def is_bust(self) -> bool:
        return self.nhl_games < 50


@dataclass(frozen=True)
class HistoricalProspect:
    """Normalized historical row joining identity, inputs, and eventual outcome."""

    player_id: str
    name: str
    draft_year: int
    position: str
    age_at_draft: float
    height_cm: int
    weight_kg: int
    consensus_rank: int
    stat_line: PreDraftStatLine
    handedness: str = ""
    birth_date: date | None = None
    nationality: str = ""
    pre_draft_stat_lines: tuple[PreDraftStatLine, ...] = field(default_factory=tuple)
    selection: DraftSelection | None = None
    outcome: DraftOutcome | None = None
    development_path: tuple[DevelopmentStatLine, ...] = field(default_factory=tuple)
    sources: tuple[SourceRecord, ...] = field(default_factory=tuple)
    scouting_text: str = ""
    scouting_badges: tuple[str, ...] = field(default_factory=tuple)
    shades_of: str = ""
    tool_grades: tuple[ToolGrade, ...] = field(default_factory=tuple)

    @property
    def was_drafted(self) -> bool:
        return self.selection is not None

    @property
    def draft_slot(self) -> int | None:
        if self.selection is None:
            return None
        return self.selection.overall_pick

    @property
    def development_leagues(self) -> tuple[str, ...]:
        leagues: list[str] = []
        for line in self.development_path:
            if line.league not in leagues:
                leagues.append(line.league)
        return tuple(leagues)

    @property
    def latest_development_line(self) -> DevelopmentStatLine | None:
        if not self.development_path:
            return None
        return self.development_path[-1]

    def to_projection_prospect(self) -> Prospect:
        return Prospect(
            player_id=self.player_id,
            name=self.name,
            draft_year=self.draft_year,
            position=self.position,
            league=self.stat_line.league,
            age_at_draft=self.age_at_draft,
            height_cm=self.height_cm,
            weight_kg=self.weight_kg,
            games=self.stat_line.games,
            goals=self.stat_line.goals,
            assists=self.stat_line.assists,
            consensus_rank=self.consensus_rank,
            scouting_text=self.scouting_text,
        )


@dataclass(frozen=True)
class TeamContext:
    team_id: str
    name: str
    competitive_timeline: str
    risk_appetite: float
    position_needs: dict[str, float] = field(default_factory=dict)
    archetype_needs: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class Projection:
    player_id: str
    nhl_probability: float
    impact_probability: float
    bust_probability: float
    expected_value: float
    confidence: float
    positive_drivers: tuple[str, ...]
    risk_drivers: tuple[str, ...]


@dataclass(frozen=True)
class ScoutingFeatures:
    player_id: str
    skating_score: float
    hockey_iq_score: float
    compete_score: float
    defense_score: float
    skill_score: float
    risk_tags: tuple[str, ...]
    role_projection: str
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class TeamAdjustedRecommendation:
    player_id: str
    team_id: str
    base_value: float
    team_fit_bonus: float
    risk_penalty: float
    adjusted_value: float
    recommendation: str
