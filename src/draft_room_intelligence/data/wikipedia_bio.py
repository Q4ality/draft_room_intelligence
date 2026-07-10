"""Enrich normalized player tables from public Wikipedia biography pages."""

from __future__ import annotations

import csv
import json
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import quote, urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from draft_room_intelligence.data.eliteprospects_csv import PLAYER_COLUMNS, write_table


WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
MATCH_COLUMNS = [
    "player_id",
    "name",
    "matched",
    "title",
    "wikidata_id",
    "source_url",
    "birth_date",
    "height_cm",
    "weight_kg",
    "handedness",
    "position",
]
CACHE_MISS = object()


@dataclass(frozen=True)
class WikipediaBio:
    title: str
    wikidata_id: str = ""
    source_url: str = ""
    birth_date: str = ""
    height_cm: str = ""
    weight_kg: str = ""
    handedness: str = ""
    position: str = ""


@dataclass(frozen=True)
class WikipediaBioEnrichmentSummary:
    players_scanned: int
    matched_pages: int
    players_updated: int
    birth_dates: int
    heights: int
    weights: int
    handedness: int
    match_report_path: Path


def enrich_wikipedia_bios(
    base_dir: str | Path,
    output_dir: str | Path,
    *,
    limit: int | None = None,
    request_delay_seconds: float = 0.2,
    enable_search_fallback: bool = False,
    progress_every: int = 0,
    cache_dir: str | Path | None = None,
    fetcher: Callable[[str], WikipediaBio | None] = None,
) -> WikipediaBioEnrichmentSummary:
    source_root = Path(base_dir)
    target_root = Path(output_dir)
    if not source_root.exists():
        raise ValueError(f"missing base dataset directory: {source_root}")

    if target_root.exists():
        shutil.rmtree(target_root)
    shutil.copytree(source_root, target_root)

    players = read_table(source_root / "players.csv")
    selected_players = players[:limit] if limit is not None else players
    if fetcher is None and not enable_search_fallback:
        bios_by_name = fetch_wikipedia_bios_batch(
            [player["name"] for player in selected_players],
            request_delay_seconds=request_delay_seconds,
            progress_every=progress_every,
            cache_dir=cache_dir,
        )
    else:
        fetch_bio = fetcher or (
            lambda name: fetch_wikipedia_bio(name, enable_search_fallback=enable_search_fallback)
        )
        bios_by_name = {}
        cache_root = Path(cache_dir) if cache_dir is not None else None
        for index, player in enumerate(selected_players):
            name = player["name"]
            cached = read_cached_bio(cache_root, name)
            if cached is not CACHE_MISS:
                bio = cached
            else:
                if index and request_delay_seconds > 0 and fetcher is None:
                    time.sleep(request_delay_seconds)
                bio = fetch_bio(name)
                write_cached_bio(cache_root, name, bio)
            bios_by_name[name] = bio
            if progress_every > 0 and (index + 1) % progress_every == 0:
                matched = sum(1 for value in bios_by_name.values() if value is not None)
                print(
                    f"Scanned {index + 1}/{len(selected_players)} players; "
                    f"matched {matched} pages.",
                    flush=True,
                )

    matches: list[dict[str, str]] = []
    bios_by_player_id: dict[str, WikipediaBio] = {}
    for player in selected_players:
        bio = bios_by_name.get(player["name"])
        matches.append(build_match_row(player, bio))
        if bio is not None:
            bios_by_player_id[player["player_id"]] = bio

    updated_players: list[dict[str, str]] = []
    players_updated = 0
    for player in players:
        bio = bios_by_player_id.get(player["player_id"])
        if bio is None:
            updated_players.append(player)
            continue
        updated = enrich_player_row(player, bio)
        if updated != player:
            players_updated += 1
        updated_players.append(updated)

    write_table(target_root / "players.csv", PLAYER_COLUMNS, updated_players)
    write_table(target_root / "wikipedia_bio_matches.csv", MATCH_COLUMNS, matches)

    return WikipediaBioEnrichmentSummary(
        players_scanned=len(selected_players),
        matched_pages=len(bios_by_player_id),
        players_updated=players_updated,
        birth_dates=count_filled(updated_players, "birth_date"),
        heights=count_filled(updated_players, "height_cm"),
        weights=count_filled(updated_players, "weight_kg"),
        handedness=count_filled(updated_players, "handedness"),
        match_report_path=target_root / "wikipedia_bio_matches.csv",
    )


def fetch_wikipedia_bio(name: str, *, enable_search_fallback: bool = False) -> WikipediaBio | None:
    try:
        page_data = resolve_page_data(name, enable_search_fallback=enable_search_fallback)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        return None
    if page_data is None:
        return None

    title = str(page_data.get("title", ""))
    extract = str(page_data.get("extract", ""))
    if not looks_like_hockey_player(name, title, extract):
        return None

    try:
        parsed = query_wikipedia(
            {
                "action": "parse",
                "format": "json",
                "page": title,
                "prop": "wikitext",
            }
        )
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        return None
    wikitext = parsed.get("parse", {}).get("wikitext", {}).get("*", "")
    values = parse_infobox_bio(str(wikitext))
    wikidata_id = str(page_data.get("pageprops", {}).get("wikibase_item", ""))
    return WikipediaBio(
        title=title,
        wikidata_id=wikidata_id,
        source_url=f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}",
        birth_date=values.get("birth_date", ""),
        height_cm=values.get("height_cm", ""),
        weight_kg=values.get("weight_kg", ""),
        handedness=values.get("handedness", ""),
        position=values.get("position", ""),
    )


def fetch_wikipedia_bios_batch(
    names: list[str],
    *,
    request_delay_seconds: float,
    progress_every: int,
    cache_dir: str | Path | None,
) -> dict[str, WikipediaBio | None]:
    cache_root = Path(cache_dir) if cache_dir is not None else None
    bios_by_name: dict[str, WikipediaBio | None] = {}
    unresolved: list[str] = []
    for name in names:
        cached = read_cached_bio(cache_root, name)
        if cached is CACHE_MISS:
            unresolved.append(name)
        else:
            bios_by_name[name] = cached

    for batch_index, batch in enumerate(chunks(unresolved, 50)):
        if batch_index and request_delay_seconds > 0:
            time.sleep(request_delay_seconds)
        batch_bios = fetch_wikipedia_bio_batch(batch)
        for name in batch:
            bio = batch_bios.get(name)
            bios_by_name[name] = bio
            write_cached_bio(cache_root, name, bio)
        if progress_every > 0:
            scanned = min(len(bios_by_name), len(names))
            if scanned % progress_every == 0 or scanned == len(names):
                matched = sum(1 for value in bios_by_name.values() if value is not None)
                print(f"Scanned {scanned}/{len(names)} players; matched {matched} pages.", flush=True)

    return {name: bios_by_name.get(name) for name in names}


def fetch_wikipedia_bio_batch(names: list[str]) -> dict[str, WikipediaBio | None]:
    if not names:
        return {}
    try:
        response = query_wikipedia(
            {
                "action": "query",
                "format": "json",
                "titles": "|".join(names),
                "prop": "pageprops|extracts|revisions",
                "exintro": "1",
                "explaintext": "1",
                "redirects": "1",
                "rvprop": "content",
                "rvslots": "main",
            }
        )
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        return {name: None for name in names}

    names_by_key = {normalize_person_key(name): name for name in names}
    bios_by_name: dict[str, WikipediaBio | None] = {name: None for name in names}
    for page_data in response.get("query", {}).get("pages", {}).values():
        if "missing" in page_data:
            continue
        title = str(page_data.get("title", ""))
        name = names_by_key.get(normalize_person_key(title))
        if name is None:
            continue
        extract = str(page_data.get("extract", ""))
        if not looks_like_hockey_player(name, title, extract):
            continue
        values = parse_infobox_bio(extract_wikitext_from_page(page_data))
        bios_by_name[name] = WikipediaBio(
            title=title,
            wikidata_id=str(page_data.get("pageprops", {}).get("wikibase_item", "")),
            source_url=f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}",
            birth_date=values.get("birth_date", ""),
            height_cm=values.get("height_cm", ""),
            weight_kg=values.get("weight_kg", ""),
            handedness=values.get("handedness", ""),
            position=values.get("position", ""),
        )
    return bios_by_name


def extract_wikitext_from_page(page_data: dict[str, object]) -> str:
    revisions = page_data.get("revisions", [])
    if not isinstance(revisions, list) or not revisions:
        return ""
    revision = revisions[0]
    if not isinstance(revision, dict):
        return ""
    slots = revision.get("slots", {})
    if isinstance(slots, dict):
        main = slots.get("main", {})
        if isinstance(main, dict):
            return str(main.get("*", "") or main.get("content", ""))
    return str(revision.get("*", ""))


def resolve_page_data(name: str, *, enable_search_fallback: bool) -> dict[str, object] | None:
    page_data = query_page_data(name)
    if page_data is not None or not enable_search_fallback:
        return page_data

    search = query_wikipedia(
        {
            "action": "query",
            "format": "json",
            "list": "search",
            "srsearch": f'"{name}" hockey',
            "srlimit": "5",
        }
    )
    for result in search.get("query", {}).get("search", []):
        title = str(result.get("title", ""))
        if normalize_person_key(title) != normalize_person_key(name):
            continue
        page_data = query_page_data(title)
        if page_data is not None:
            return page_data
    return None


def query_page_data(title: str) -> dict[str, object] | None:
    try:
        page = query_wikipedia(
            {
                "action": "query",
                "format": "json",
                "titles": title,
                "prop": "pageprops|extracts",
                "exintro": "1",
                "explaintext": "1",
                "redirects": "1",
            }
        )
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        return None
    pages = page.get("query", {}).get("pages", {})
    if not pages:
        return None
    page_data = next(iter(pages.values()))
    if "missing" in page_data:
        return None
    return page_data


def query_wikipedia(params: dict[str, str]) -> dict[str, object]:
    url = f"{WIKIPEDIA_API_URL}?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": "draft-room-intelligence/0.1"})
    for attempt in range(3):
        try:
            with urlopen(request, timeout=20) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            if error.code != 429 or attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))
    raise ValueError("unreachable Wikipedia retry state")


def looks_like_hockey_player(expected_name: str, title: str, extract: str) -> bool:
    combined = f"{title} {extract}".lower()
    if "may refer to" in combined or "disambiguation" in combined:
        return False
    names_match = normalize_person_key(expected_name) == normalize_person_key(title)
    if not names_match:
        return False
    return "ice hockey" in combined or "hockey player" in combined or "hockey" in combined


def normalize_person_key(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())


def parse_infobox_bio(wikitext: str) -> dict[str, str]:
    fields = parse_infobox_fields(wikitext)
    return {
        "birth_date": parse_birth_date(fields.get("birth_date", "")),
        "height_cm": parse_height_cm(fields),
        "weight_kg": parse_weight_kg(fields),
        "handedness": parse_handedness(fields.get("shoots", "") or fields.get("catches", "")),
        "position": normalize_position(fields.get("position", "")),
    }


def parse_infobox_fields(wikitext: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in wikitext.splitlines():
        match = re.match(r"\|\s*([A-Za-z0-9_ ]+)\s*=\s*(.*)", line)
        if match:
            fields[match.group(1).strip().lower()] = match.group(2).strip()
    return fields


def parse_birth_date(value: str) -> str:
    match = re.search(r"\{\{\s*birth date(?: and age)?\s*\|(\d{4})\|(\d{1,2})\|(\d{1,2})", value, re.I)
    if match:
        year, month, day = match.groups()
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", value)
    if match:
        year, month, day = match.groups()
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    return ""


def parse_height_cm(fields: dict[str, str]) -> str:
    direct = first_number(fields.get("height_cm", ""))
    if direct:
        return str(round(float(direct)))
    feet = first_number(fields.get("height_ft", ""))
    inches = first_number(fields.get("height_in", ""))
    if feet:
        total_inches = float(feet) * 12 + float(inches or 0)
        return str(round(total_inches * 2.54))
    return ""


def parse_weight_kg(fields: dict[str, str]) -> str:
    direct = first_number(fields.get("weight_kg", ""))
    if direct:
        return str(round(float(direct)))
    pounds = first_number(fields.get("weight_lb", ""))
    if pounds:
        return str(round(float(pounds) * 0.453592))
    return ""


def parse_handedness(value: str) -> str:
    cleaned = strip_markup(value).lower()
    if "left" in cleaned:
        return "L"
    if "right" in cleaned:
        return "R"
    return ""


def normalize_position(value: str) -> str:
    cleaned = strip_markup(value).lower()
    if "goaltender" in cleaned or "goalie" in cleaned:
        return "G"
    if "defenc" in cleaned or "defens" in cleaned:
        return "D"
    if "left wing" in cleaned or cleaned == "lw":
        return "L"
    if "right wing" in cleaned or cleaned == "rw":
        return "R"
    if "centre" in cleaned or "center" in cleaned or cleaned == "c":
        return "C"
    return ""


def strip_markup(value: str) -> str:
    value = re.sub(r"\[\[[^|\]]+\|([^\]]+)\]\]", r"\1", value)
    value = re.sub(r"\[\[([^\]]+)\]\]", r"\1", value)
    value = re.sub(r"\{\{[^{}]*\}\}", "", value)
    return re.sub(r"<[^>]+>", "", value).strip()


def first_number(value: str) -> str:
    match = re.search(r"\d+(?:\.\d+)?", strip_markup(value))
    return match.group(0) if match else ""


def enrich_player_row(player: dict[str, str], bio: WikipediaBio) -> dict[str, str]:
    updated = dict(player)
    for field in ("birth_date", "height_cm", "weight_kg", "handedness", "position"):
        value = getattr(bio, field)
        if value and not updated.get(field):
            updated[field] = value
    if bio.wikidata_id:
        updated["source_id"] = bio.wikidata_id
    if bio.source_url:
        updated["source_url"] = bio.source_url
    updated["source"] = merge_source_label(updated.get("source", ""), "wikipedia_bio")
    return updated


def merge_source_label(existing: str, label: str) -> str:
    labels = [item.strip() for item in existing.split("+") if item.strip()]
    if label not in labels:
        labels.append(label)
    return "+".join(labels)


def build_match_row(player: dict[str, str], bio: WikipediaBio | None) -> dict[str, str]:
    if bio is None:
        return {
            "player_id": player["player_id"],
            "name": player["name"],
            "matched": "false",
            "title": "",
            "wikidata_id": "",
            "source_url": "",
            "birth_date": "",
            "height_cm": "",
            "weight_kg": "",
            "handedness": "",
            "position": "",
        }
    return {
        "player_id": player["player_id"],
        "name": player["name"],
        "matched": "true",
        "title": bio.title,
        "wikidata_id": bio.wikidata_id,
        "source_url": bio.source_url,
        "birth_date": bio.birth_date,
        "height_cm": bio.height_cm,
        "weight_kg": bio.weight_kg,
        "handedness": bio.handedness,
        "position": bio.position,
    }


def read_table(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def count_filled(rows: list[dict[str, str]], column: str) -> int:
    return sum(1 for row in rows if row.get(column))


def read_cached_bio(cache_root: Path | None, name: str) -> WikipediaBio | None | object:
    if cache_root is None:
        return CACHE_MISS
    path = cache_path(cache_root, name)
    if not path.exists():
        return CACHE_MISS
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return CACHE_MISS
    if not payload.get("matched"):
        return None
    bio = payload.get("bio", {})
    if not isinstance(bio, dict):
        return CACHE_MISS
    return WikipediaBio(
        title=str(bio.get("title", "")),
        wikidata_id=str(bio.get("wikidata_id", "")),
        source_url=str(bio.get("source_url", "")),
        birth_date=str(bio.get("birth_date", "")),
        height_cm=str(bio.get("height_cm", "")),
        weight_kg=str(bio.get("weight_kg", "")),
        handedness=str(bio.get("handedness", "")),
        position=str(bio.get("position", "")),
    )


def write_cached_bio(cache_root: Path | None, name: str, bio: WikipediaBio | None) -> None:
    if cache_root is None:
        return
    cache_root.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object]
    if bio is None:
        payload = {"name": name, "matched": False}
    else:
        payload = {
            "name": name,
            "matched": True,
            "bio": {
                "title": bio.title,
                "wikidata_id": bio.wikidata_id,
                "source_url": bio.source_url,
                "birth_date": bio.birth_date,
                "height_cm": bio.height_cm,
                "weight_kg": bio.weight_kg,
                "handedness": bio.handedness,
                "position": bio.position,
            },
        }
    cache_path(cache_root, name).write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def cache_path(cache_root: Path, name: str) -> Path:
    return cache_root / f"{normalize_person_key(name) or 'unknown'}.json"


def chunks(values: list[str], size: int) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]
