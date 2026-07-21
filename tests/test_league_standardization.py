from draft_room_intelligence.data.league_standardization import normalize_league_name


def test_normalize_league_name_handles_official_nhl_draft_codes():
    assert normalize_league_name("H-EAST") == "NCAA"
    assert normalize_league_name("BIG10") == "NCAA"
    assert normalize_league_name("NTDP") == "USHL"
    assert normalize_league_name("NTDP - USHL") == "USHL"
    assert normalize_league_name("SWEDEN-JR.") == "Sweden Jrs."
    assert normalize_league_name("FINLAND-JR.") == "Finland Jrs."
    assert normalize_league_name("RUSSIA-JR.") == "Russia Jr."
    assert normalize_league_name("Nationell") == "Sweden Jrs."


def test_normalize_league_name_matches_aliases_case_insensitively():
    assert normalize_league_name("hockey east") == "NCAA"
    assert normalize_league_name("swehl") == "SHL"
    assert normalize_league_name("rus-mhl") == "MHL"
