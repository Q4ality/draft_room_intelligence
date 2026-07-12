"""Import local Elite Prospects draft-guide PDFs into normalized tables."""

from __future__ import annotations

import base64
import json
import os
import re
import subprocess
from dataclasses import dataclass
from dataclasses import replace
from pathlib import Path
from typing import Protocol
from urllib.request import Request
from urllib.request import urlopen

from draft_room_intelligence.data.eliteprospects_csv import (
    PLAYER_COLUMNS,
    SEASON_STAT_LINE_COLUMNS,
    build_player_id,
    write_table,
)
from draft_room_intelligence.data.league_standardization import normalize_league_name


EP_PDF_PROFILE_COLUMNS = [
    "player_id",
    "draft_year",
    "name",
    "page_start",
    "page_end",
    "rank",
    "rank_range",
    "grade",
    "position",
    "handedness",
    "height_text",
    "height_cm",
    "weight_kg",
    "birth_date",
    "shades_of",
    "badges",
    "profile_summary",
    "profile_text_chars",
    "extraction_warnings",
    "source",
    "source_id",
    "source_url",
]

EP_PDF_TOOL_GRADE_COLUMNS = [
    "player_id",
    "tool",
    "grade",
    "source",
    "source_id",
    "source_url",
]

RANKING_COLUMNS = [
    "player_id",
    "draft_year",
    "source",
    "rank",
    "scope",
    "position",
    "source_id",
    "source_url",
]

TOOL_LABELS = ["skating", "shooting", "passing", "handling", "sense", "physical"]
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
DEFAULT_VISION_MODEL = "gpt-5.6"


class ToolGradeVisionClient(Protocol):
    def extract_tool_grades(
        self,
        image_path: Path,
        profile: EliteProspectsPdfProfile,
    ) -> dict[str, str]:
        """Return tool grades keyed by skating/shooting/passing/handling/sense/physical."""


@dataclass(frozen=True)
class EliteProspectsPdfProfile:
    player_id: str
    draft_year: int
    name: str
    page_start: int
    page_end: int
    rank: str
    rank_range: str
    grade: str
    position: str
    handedness: str
    height_text: str
    height_cm: str
    weight_kg: str
    birth_date: str
    shades_of: str
    badges: tuple[str, ...]
    profile_summary: str
    profile_text: str
    stat_lines: tuple[dict[str, str], ...]
    tool_grades: tuple[dict[str, str], ...]
    extraction_warnings: tuple[str, ...]
    source_url: str


@dataclass(frozen=True)
class EliteProspectsPdfExport:
    players: list[dict[str, str]]
    season_stat_lines: list[dict[str, str]]
    rankings: list[dict[str, str]]
    profiles: list[EliteProspectsPdfProfile]
    profile_rows: list[dict[str, str]]
    tool_grade_rows: list[dict[str, str]]


def write_eliteprospects_pdf_tables(
    pdf_path: str | Path,
    output_dir: str | Path,
    *,
    draft_year: int,
    page_start: int = 1,
    page_end: int | None = None,
    profile_limit: int | None = None,
    vision_missing_tool_grades: bool = False,
    vision_model: str = DEFAULT_VISION_MODEL,
    vision_api_key: str | None = None,
    pdftoppm_path: str | Path = "pdftoppm",
    vision_render_dpi: int = 160,
    vision_client: ToolGradeVisionClient | None = None,
) -> EliteProspectsPdfExport:
    page_texts = extract_pdf_page_texts(pdf_path, page_start=page_start, page_end=page_end)
    export = normalize_eliteprospects_pdf_pages(
        page_texts,
        draft_year=draft_year,
        source_name=Path(pdf_path).name,
        profile_limit=profile_limit,
    )
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    if vision_missing_tool_grades:
        export = enrich_missing_tool_grades_with_vision(
            Path(pdf_path),
            root / "vision_pages",
            export,
            model=vision_model,
            api_key=vision_api_key,
            pdftoppm_path=pdftoppm_path,
            render_dpi=vision_render_dpi,
            vision_client=vision_client,
        )
    write_table(root / "players.csv", PLAYER_COLUMNS, export.players)
    write_table(root / "season_stat_lines.csv", SEASON_STAT_LINE_COLUMNS, export.season_stat_lines)
    write_table(root / "rankings.csv", RANKING_COLUMNS, export.rankings)
    write_table(root / "ep_pdf_profiles.csv", EP_PDF_PROFILE_COLUMNS, export.profile_rows)
    write_table(root / "ep_pdf_tool_grades.csv", EP_PDF_TOOL_GRADE_COLUMNS, export.tool_grade_rows)
    report = format_pdf_extraction_report(export)
    (root / "extraction_report.md").write_text(report, encoding="utf-8")
    return export


def enrich_missing_tool_grades_with_vision(
    pdf_path: Path,
    image_dir: Path,
    export: EliteProspectsPdfExport,
    *,
    model: str = DEFAULT_VISION_MODEL,
    api_key: str | None = None,
    pdftoppm_path: str | Path = "pdftoppm",
    render_dpi: int = 160,
    vision_client: ToolGradeVisionClient | None = None,
) -> EliteProspectsPdfExport:
    client = vision_client or OpenAiVisionToolGradeClient(
        model=model,
        api_key=api_key or os.environ.get("OPENAI_API_KEY", ""),
    )
    profiles: list[EliteProspectsPdfProfile] = []
    for profile in export.profiles:
        if profile.tool_grades or "missing_tool_grades" not in profile.extraction_warnings:
            profiles.append(profile)
            continue
        image_path = render_pdf_page(
            pdf_path,
            image_dir,
            page_number=profile.page_start,
            pdftoppm_path=pdftoppm_path,
            dpi=render_dpi,
        )
        grades = normalize_tool_grade_map(client.extract_tool_grades(image_path, profile))
        if grades:
            source_id = f"{profile.draft_year}-ep-pdf-page-{profile.page_start}"
            tool_grades = tuple(
                {
                    "player_id": profile.player_id,
                    "tool": tool,
                    "grade": grades[tool],
                    "source": "eliteprospects_pdf_vision",
                    "source_id": source_id,
                    "source_url": profile.source_url,
                }
                for tool in TOOL_LABELS
                if tool in grades
            )
            warnings = tuple(
                warning
                for warning in profile.extraction_warnings
                if warning != "missing_tool_grades"
            )
            profiles.append(
                replace(
                    profile,
                    tool_grades=tool_grades,
                    extraction_warnings=(*warnings, "tool_grades_from_vision"),
                )
            )
        else:
            profiles.append(profile)
    return build_export_from_profiles(profiles)


class OpenAiVisionToolGradeClient:
    def __init__(
        self,
        *,
        model: str = DEFAULT_VISION_MODEL,
        api_key: str,
        endpoint: str = OPENAI_RESPONSES_URL,
    ) -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for --vision-missing-tool-grades")
        self.model = model
        self.api_key = api_key
        self.endpoint = endpoint

    def extract_tool_grades(
        self,
        image_path: Path,
        profile: EliteProspectsPdfProfile,
    ) -> dict[str, str]:
        base64_image = base64.b64encode(image_path.read_bytes()).decode("ascii")
        image_url = f"data:image/png;base64,{base64_image}"
        payload = {
            "model": self.model,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": tool_grade_prompt(profile),
                        },
                        {
                            "type": "input_image",
                            "image_url": image_url,
                        },
                    ],
                }
            ],
        }
        request = Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urlopen(request, timeout=120) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
        return parse_tool_grade_json(extract_response_text(response_payload))


def tool_grade_prompt(profile: EliteProspectsPdfProfile) -> str:
    return "\n".join(
        [
            "Extract only the six Elite Prospects tool grade numbers visible "
            "on this player profile.",
            f"Player: {profile.name}",
            "Return strict JSON with exactly these lowercase keys when visible:",
            "skating, shooting, passing, handling, sense, physical.",
            "Values must be strings like \"6.5\" or \"8.0\".",
            "Do not infer hidden values. If a value is not visible, omit that key.",
            "Return JSON only.",
        ]
    )


def render_pdf_page(
    pdf_path: Path,
    image_dir: Path,
    *,
    page_number: int,
    pdftoppm_path: str | Path = "pdftoppm",
    dpi: int = 160,
) -> Path:
    image_dir.mkdir(parents=True, exist_ok=True)
    output_prefix = image_dir / f"page_{page_number}"
    subprocess.run(
        [
            str(pdftoppm_path),
            "-f",
            str(page_number),
            "-l",
            str(page_number),
            "-png",
            "-singlefile",
            "-r",
            str(dpi),
            str(pdf_path),
            str(output_prefix),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    image_path = output_prefix.with_suffix(".png")
    if not image_path.exists():
        raise RuntimeError(f"pdftoppm did not create expected image: {image_path}")
    return image_path


def extract_response_text(payload: dict) -> str:
    if payload.get("output_text"):
        return str(payload["output_text"])
    parts: list[str] = []
    for item in payload.get("output", []) or []:
        for content in item.get("content", []) or []:
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                parts.append(str(content["text"]))
    return "\n".join(parts)


def parse_tool_grade_json(text: str) -> dict[str, str]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"OpenAI vision response was not valid JSON: {text[:200]}") from exc
    if not isinstance(payload, dict):
        raise ValueError("OpenAI vision response must be a JSON object")
    return normalize_tool_grade_map(payload)


def normalize_tool_grade_map(values: dict) -> dict[str, str]:
    grades: dict[str, str] = {}
    for raw_tool, raw_grade in values.items():
        tool = str(raw_tool).strip().lower().replace(" ", "_")
        if tool not in TOOL_LABELS or raw_grade in ("", None):
            continue
        grade = normalize_tool_grade_value(str(raw_grade))
        if grade:
            grades[tool] = grade
    return grades


def normalize_tool_grade_value(value: str) -> str:
    match = re.search(r"([1-9](?:\.\d)?)", value)
    if not match:
        return ""
    grade = float(match.group(1))
    if grade < 1 or grade > 9:
        return ""
    return f"{grade:.1f}"


def extract_pdf_page_texts(
    pdf_path: str | Path,
    *,
    page_start: int = 1,
    page_end: int | None = None,
) -> list[tuple[int, str]]:
    try:
        import pypdf
    except ImportError as exc:
        raise RuntimeError(
            "pypdf is required for Elite Prospects PDF import. "
            "Install project dependencies with `make install-dev`."
        ) from exc

    reader = pypdf.PdfReader(str(pdf_path))
    final_page = page_end or len(reader.pages)
    page_texts: list[tuple[int, str]] = []
    for page_number in range(max(1, page_start), min(final_page, len(reader.pages)) + 1):
        page = reader.pages[page_number - 1]
        page_texts.append((page_number, page.extract_text() or ""))
    return page_texts


def normalize_eliteprospects_pdf_pages(
    page_texts: list[tuple[int, str]],
    *,
    draft_year: int,
    source_name: str = "eliteprospects_pdf",
    profile_limit: int | None = None,
) -> EliteProspectsPdfExport:
    profiles: list[EliteProspectsPdfProfile] = []
    for page_number, text in page_texts:
        profile = parse_profile_page(
            text,
            draft_year=draft_year,
            page_number=page_number,
            source_name=source_name,
        )
        if profile is None:
            continue
        profiles.append(profile)
        if profile_limit is not None and len(profiles) >= profile_limit:
            break

    return build_export_from_profiles(profiles)


def build_export_from_profiles(profiles: list[EliteProspectsPdfProfile]) -> EliteProspectsPdfExport:
    players = [profile_to_player_row(profile) for profile in profiles]
    stat_lines = [line for profile in profiles for line in profile.stat_lines]
    rankings = [profile_to_ranking_row(profile) for profile in profiles if profile.rank]
    profile_rows = [profile_to_profile_row(profile) for profile in profiles]
    tool_grade_rows = [row for profile in profiles for row in profile.tool_grades]
    return EliteProspectsPdfExport(
        players=players,
        season_stat_lines=stat_lines,
        rankings=rankings,
        profiles=profiles,
        profile_rows=profile_rows,
        tool_grade_rows=tool_grade_rows,
    )


def parse_profile_page(
    text: str,
    *,
    draft_year: int,
    page_number: int,
    source_name: str,
) -> EliteProspectsPdfProfile | None:
    if not looks_like_profile_page(text):
        return None

    warnings: list[str] = []
    name, position_hint = extract_name_and_position(text)
    if not name:
        return None
    source_id = f"{draft_year}-ep-pdf-page-{page_number}"
    player_id = build_player_id(draft_year, "", name)
    source_url = f"{source_name}#page={page_number}"

    bio = extract_bio(text, position_hint=position_hint)
    for key in ("position", "birth_date", "height_cm", "weight_kg"):
        if not bio.get(key):
            warnings.append(f"missing_{key}")

    rank_range = extract_rank_range(text)
    rank = extract_rank(text, rank_range=rank_range)
    grade = extract_grade(text)
    stat_lines = tuple(
        build_stat_line(
            player_id,
            row,
            source_id=source_id,
            source_url=source_url,
        )
        for row in extract_stat_rows(text, draft_year=draft_year)
    )
    if not stat_lines:
        warnings.append("missing_stat_lines")

    tool_grades = tuple(
        {
            "player_id": player_id,
            "tool": tool,
            "grade": grade_value,
            "source": "eliteprospects_pdf",
            "source_id": source_id,
            "source_url": source_url,
        }
        for tool, grade_value in extract_tool_grades(text).items()
    )
    if not tool_grades:
        warnings.append("missing_tool_grades")

    return EliteProspectsPdfProfile(
        player_id=player_id,
        draft_year=draft_year,
        name=name,
        page_start=page_number,
        page_end=page_number,
        rank=rank,
        rank_range=rank_range,
        grade=grade,
        position=bio.get("position", ""),
        handedness=bio.get("handedness", ""),
        height_text=bio.get("height_text", ""),
        height_cm=bio.get("height_cm", ""),
        weight_kg=bio.get("weight_kg", ""),
        birth_date=bio.get("birth_date", ""),
        shades_of=extract_shades_of(text),
        badges=tuple(extract_badges(text, grade=grade)),
        profile_summary=extract_profile_summary(text),
        profile_text=extract_profile_text(text, name=name),
        stat_lines=stat_lines,
        tool_grades=tool_grades,
        extraction_warnings=tuple(warnings),
        source_url=source_url,
    )


def looks_like_profile_page(text: str) -> bool:
    normalized = text.upper()
    return (
        ("STATISTICS" in normalized or "TEAM LEAGUE GP" in normalized)
        and ("POSITION(S)" in normalized or "TOOL GRADES" in normalized)
        and "PLAYER INDEX" not in normalized
        and "GRADE PROSPECTS" not in normalized
    )


def extract_name_and_position(text: str) -> tuple[str, str]:
    pipe_match = re.search(r"\n(?P<position>[A-Z][A-Z/]{0,5})\|(?P<name>[^\n]+)", text)
    if pipe_match:
        return clean_text(pipe_match.group("name")), pipe_match.group("position")

    shades_match = re.search(r"^\s*(?P<name>.+?)\s+SHADES OF\.\.\.", text, flags=re.IGNORECASE)
    if shades_match:
        return clean_text(shades_match.group("name")), ""
    return "", ""


def extract_bio(text: str, *, position_hint: str) -> dict[str, str]:
    bio: dict[str, str] = {}
    compact = clean_text(text)
    match_2025 = re.search(
        r"(?P<weight>\d{3})\s*lbs\s+(?P<handedness>[LR])(?P<height>\d+[\'’][0-9.]+[\"”])\s+"
        r"(?P<birth_date>\d{4}-\d{2}-\d{2})",
        compact,
    )
    if match_2025:
        bio.update(
            {
                "position": normalize_pdf_position(position_hint),
                "handedness": match_2025.group("handedness"),
                "height_text": match_2025.group("height"),
                "height_cm": str(height_to_cm(match_2025.group("height"))),
                "weight_kg": str(pounds_to_kg(match_2025.group("weight"))),
                "birth_date": match_2025.group("birth_date"),
            }
        )
        return bio

    match_2026 = re.search(
        r"HEIGHT\s+(?P<height>\d+[\'’][0-9.]+[\"”])\s+(?P<weight>\d{3})\s*lbs\s+WEIGHT\s+"
        r"(?P<handedness>Left|Right|L|R)\s+(?P<birth_date>\d{4}-\d{2}-\d{2}).+?"
        r"(?P<position>[A-Z]{1,3}(?:/[A-Z]{1,3})?)\s+POSITION\(S\)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if match_2026:
        bio.update(
            {
                "position": normalize_pdf_position(match_2026.group("position")),
                "handedness": normalize_handedness(match_2026.group("handedness")),
                "height_text": match_2026.group("height"),
                "height_cm": str(height_to_cm(match_2026.group("height"))),
                "weight_kg": str(pounds_to_kg(match_2026.group("weight"))),
                "birth_date": match_2026.group("birth_date"),
            }
        )
    return bio


def extract_stat_rows(text: str, *, draft_year: int) -> list[dict[str, str]]:
    season = extract_statistics_season(text) or f"{draft_year - 1}-{str(draft_year)[-2:]}"
    rows: list[dict[str, str]] = []
    for line in text.splitlines():
        stat_match = re.match(
            r"^(?P<label>.+?)\s+(?P<games>\d+)\s+(?P<goals>\d+)\s+(?P<assists>\d+)\s+"
            r"(?P<points>\d+)\s+(?P<gpg>[0-9.]+)\s+(?P<apg>[0-9.]+)\s+(?P<ppg>[0-9.]+)$",
            line.strip(),
        )
        if not stat_match:
            continue
        label = stat_match.group("label").strip()
        team, league = split_team_league(label)
        if not team or not league:
            continue
        rows.append(
            {
                "season": season,
                "league": league,
                "team": team,
                "games": stat_match.group("games"),
                "goals": stat_match.group("goals"),
                "assists": stat_match.group("assists"),
                "points": stat_match.group("points"),
            }
        )
    return rows


def build_stat_line(
    player_id: str,
    row: dict[str, str],
    *,
    source_id: str,
    source_url: str,
) -> dict[str, str]:
    return {
        "player_id": player_id,
        "season": row["season"],
        "league": normalize_league_name(row["league"]),
        "team": row["team"],
        "games": row["games"],
        "goals": row["goals"],
        "assists": row["assists"],
        "points": row["points"],
        "age": "",
        "timing": "pre_draft",
        "regular_season": "true",
        "source": "eliteprospects_pdf",
        "source_id": source_id,
        "source_url": source_url,
        "goalie_minutes": "",
        "shots_against": "",
        "saves": "",
        "goals_against": "",
        "save_percentage": "",
        "goals_against_average": "",
        "wins": "",
        "losses": "",
        "ties": "",
        "shutouts": "",
    }


def split_team_league(label: str) -> tuple[str, str]:
    parenthesized = re.match(r"^(?P<team>.+?)\s+\((?P<league>[^)]+)\)$", label)
    if parenthesized:
        return parenthesized.group("team").strip(), parenthesized.group("league").strip()
    parts = label.rsplit(" ", maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return "", ""


def extract_statistics_season(text: str) -> str:
    match = re.search(r"(\d{4}-\d{2})\s+STATISTICS", text, flags=re.IGNORECASE)
    return match.group(1) if match else ""


def extract_tool_grades(text: str) -> dict[str, str]:
    match = re.search(
        r"Tool Grades\s*\(1\.0 to 9\.0\)\s+(?P<values>.+?)\s+Skating\s+Shooting"
        r"\s+Passing\s+Handling\s+Sense\s+Physical",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return {}
    values = [value.replace(" ", "") for value in re.findall(r"\d\.\s*\d", match.group("values"))]
    return dict(zip(TOOL_LABELS, values, strict=False))


def extract_grade(text: str) -> str:
    match_2026 = re.search(r"\n(?P<grade>[ABCDF])\nBADGES\nGRADE", text)
    if match_2026:
        return match_2026.group("grade")
    match_2025 = re.search(
        r"Tool Grades\s*\(1\.0 to 9\.0\).+?\s(?P<grade>[ABCDF])\s+Skating\s+Shooting",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return match_2025.group("grade") if match_2025 else ""


def extract_rank_range(text: str) -> str:
    match = re.search(r"(?:Range:|RANK RANGE)\s*(\d+\s*-\s*\d+)", text, flags=re.IGNORECASE)
    return clean_text(match.group(1)) if match else ""


def extract_rank(text: str, *, rank_range: str) -> str:
    match_2025 = re.search(r"\n(?P<rank>\d{1,3})\nShades of", text, flags=re.IGNORECASE)
    if match_2025:
        return match_2025.group("rank")
    match_2026 = re.search(r"^.+?SHADES OF\.\.\..*?(?P<rank>\d{1,3})\s*$", text.splitlines()[0])
    if match_2026:
        return match_2026.group("rank")
    return rank_range.split("-")[0].strip() if rank_range else ""


def extract_shades_of(text: str) -> str:
    match = re.search(r"SHADES OF\.\.\.\s*(?P<value>.+?)(?:\n|$)", text, flags=re.IGNORECASE)
    if not match:
        match = re.search(r"Shades of\.\.\.\s*(?P<value>.+?)(?:\n|$)", text)
    if not match:
        return ""
    return re.sub(r"\d{1,3}$", "", clean_text(match.group("value"))).strip()


def extract_badges(text: str, *, grade: str) -> list[str]:
    badges: list[str] = []
    match_2025 = re.search(
        r"\d{3}\s*lbs\s+[LR]\d+[\'’][0-9.]+[\"”]\s+\d{4}-\d{2}-\d{2}\n"
        r"(?P<badges>.+?)\n\d{1,3}\nShades",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if match_2025:
        badges.extend(extract_badge_tokens(match_2025.group("badges"), grade=grade))

    match_2026_primary = re.search(
        r"\n(?P<badge>[A-Z][A-Za-z ]{2,40})\n[ABCDF]\nBADGES\nGRADE",
        text,
    )
    if match_2026_primary:
        badges.append(clean_text(match_2026_primary.group("badge")))

    match_2026_more = re.search(
        r"(?:SKATING|PHYSICAL)\s*(?P<badges>.+?)\s*PROSPECT PROFILE",
        text,
        flags=re.DOTALL,
    )
    if match_2026_more:
        badges.extend(extract_badge_tokens(match_2026_more.group("badges"), grade=grade))

    return sorted(set(badge for badge in badges if badge))


def extract_badge_tokens(value: str, *, grade: str) -> list[str]:
    tokens: list[str] = []
    for line in value.splitlines():
        line = clean_text(line)
        if not line or line == grade:
            continue
        if line.upper() in {"SKATING", "SHOOTING", "PASSING", "HANDLING", "SENSE", "PHYSICAL"}:
            continue
        if len(line) <= 40:
            tokens.append(line)
    return tokens


def extract_profile_summary(text: str) -> str:
    match_2025 = re.search(
        r"Elevator Pitch\s+(?P<summary>.+?)\s+Tool Grades",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if match_2025:
        return clean_text(match_2025.group("summary"))
    match_2026 = re.search(
        r"PROSPECT SUMMARY\s+(?P<summary>.+?)\s+(?:SHOOTING|2025-\d{2}\s+STATISTICS)",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    return clean_text(match_2026.group("summary")) if match_2026 else ""


def extract_profile_text(text: str, *, name: str) -> str:
    pipe_marker = f"|{name}"
    if pipe_marker in text:
        return clean_text(
            text.split(pipe_marker, maxsplit=1)[0].replace("NHL DRAFT GUIDE 2025", "")
        )
    match = re.search(
        r"POSITION\(S\)\s+(?P<body>.+?)\s+(?:SKATING|PROSPECT SUMMARY)",
        text,
        flags=re.DOTALL,
    )
    if match:
        return clean_text(match.group("body"))
    return ""


def profile_to_player_row(profile: EliteProspectsPdfProfile) -> dict[str, str]:
    return {
        "player_id": profile.player_id,
        "name": profile.name,
        "birth_date": profile.birth_date,
        "nationality": "",
        "position": profile.position,
        "handedness": profile.handedness,
        "height_cm": profile.height_cm,
        "weight_kg": profile.weight_kg,
        "age_at_draft": "",
        "source": "eliteprospects_pdf",
        "source_id": f"{profile.draft_year}-ep-pdf-page-{profile.page_start}",
        "source_url": profile.source_url,
    }


def profile_to_ranking_row(profile: EliteProspectsPdfProfile) -> dict[str, str]:
    return {
        "player_id": profile.player_id,
        "draft_year": str(profile.draft_year),
        "source": "eliteprospects_pdf",
        "rank": profile.rank,
        "scope": "eliteprospects_draft_guide",
        "position": profile.position,
        "source_id": f"{profile.draft_year}-ep-pdf-page-{profile.page_start}",
        "source_url": profile.source_url,
    }


def profile_to_profile_row(profile: EliteProspectsPdfProfile) -> dict[str, str]:
    return {
        "player_id": profile.player_id,
        "draft_year": str(profile.draft_year),
        "name": profile.name,
        "page_start": str(profile.page_start),
        "page_end": str(profile.page_end),
        "rank": profile.rank,
        "rank_range": profile.rank_range,
        "grade": profile.grade,
        "position": profile.position,
        "handedness": profile.handedness,
        "height_text": profile.height_text,
        "height_cm": profile.height_cm,
        "weight_kg": profile.weight_kg,
        "birth_date": profile.birth_date,
        "shades_of": profile.shades_of,
        "badges": "; ".join(profile.badges),
        "profile_summary": profile.profile_summary,
        "profile_text_chars": str(len(profile.profile_text)),
        "extraction_warnings": "; ".join(profile.extraction_warnings),
        "source": "eliteprospects_pdf",
        "source_id": f"{profile.draft_year}-ep-pdf-page-{profile.page_start}",
        "source_url": profile.source_url,
    }


def format_pdf_extraction_report(export: EliteProspectsPdfExport) -> str:
    profiles_with_stats = sum(1 for profile in export.profiles if profile.stat_lines)
    profiles_with_tools = sum(1 for profile in export.profiles if profile.tool_grades)
    warning_counts: dict[str, int] = {}
    for profile in export.profiles:
        for warning in profile.extraction_warnings:
            warning_counts[warning] = warning_counts.get(warning, 0) + 1
    lines = [
        "# Elite Prospects PDF Extraction",
        "",
        "## Summary",
        f"- profiles: {len(export.profiles)}",
        f"- players: {len(export.players)}",
        f"- stat_lines: {len(export.season_stat_lines)}",
        f"- profiles_with_stats: {profiles_with_stats}",
        f"- profiles_with_tool_grades: {profiles_with_tools}",
        "",
        "## Warnings",
    ]
    if warning_counts:
        lines.extend(f"- {warning}: {count}" for warning, count in sorted(warning_counts.items()))
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def normalize_pdf_position(value: str) -> str:
    return value.replace("/", "").upper()


def normalize_handedness(value: str) -> str:
    normalized = value.strip().upper()
    if normalized == "LEFT":
        return "L"
    if normalized == "RIGHT":
        return "R"
    return normalized[:1]


def height_to_cm(value: str) -> int:
    normalized = value.replace("’", "'").replace("”", '"')
    match = re.match(r"(?P<feet>\d+)'(?P<inches>[0-9.]+)", normalized)
    if not match:
        return 0
    inches = int(match.group("feet")) * 12 + float(match.group("inches"))
    return round(inches * 2.54)


def pounds_to_kg(value: str) -> int:
    return round(int(value) * 0.453592) if value else 0
