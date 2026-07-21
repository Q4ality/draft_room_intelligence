import csv
import json
from pathlib import Path

import pytest

from draft_room_intelligence.data.nhl_draft import (
    collect_nhl_draft_year,
    generate_nhl_draft_base_tables,
    normalize_pick,
)
from draft_room_intelligence.data.normalized_tables import load_normalized_historical_prospects

FIXTURE = Path(__file__).parent / "fixtures" / "nhl_draft_2024_sample.json"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_generate_nhl_draft_base_tables_writes_loadable_dataset(tmp_path):
    output = generate_nhl_draft_base_tables(FIXTURE, tmp_path / "base", draft_year=2024)

    prospects = load_normalized_historical_prospects(output)
    selections = read_rows(output / "draft_selections.csv")

    assert len(prospects) == 2
    assert prospects[0].name == "Macklin Celebrini"
    assert prospects[0].height_cm == 183
    assert prospects[0].outcome is None
    assert selections[0]["team_id"] == "SJS"
    assert selections[0]["drafted_from_team"] == "Boston University"
    assert selections[0]["source"] == "nhl_draft_api"


def test_collect_nhl_draft_year_reuses_cache_without_network(tmp_path):
    cache_path = tmp_path / "2024" / "picks.json"
    cache_path.parent.mkdir(parents=True)
    cache_path.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")

    result = collect_nhl_draft_year(tmp_path, draft_year=2024)

    assert result.status == "cached"
    assert result.pick_count == 3
    assert result.cache_path == cache_path


def test_normalize_pick_rejects_row_without_identity():
    with pytest.raises(ValueError, match="invalid NHL draft row"):
        normalize_pick({"overallPick": 1}, 2024)


def test_generate_nhl_draft_base_tables_rejects_wrong_year(tmp_path):
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    wrong = tmp_path / "wrong.json"
    wrong.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="does not match"):
        generate_nhl_draft_base_tables(wrong, tmp_path / "base", draft_year=2023)
