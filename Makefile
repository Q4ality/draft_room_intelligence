.PHONY: install-dev demo demo-2025-readiness team-fit-2025 validate-pilot-2019 team-depth-sample nhl-roster-sample ep-pdf-sample evaluate-consensus evaluate-projection evaluate-adjusted-production evaluate-hybrid evaluate-pilot-consensus evaluate-pilot-projection evaluate-pilot-adjusted-production evaluate-pilot-hybrid test lint check clean

PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)

install-dev:
	$(PYTHON) -m pip install -e ".[dev]"

demo:
	$(PYTHON) -m draft_room_intelligence.cli demo

demo-2025-readiness:
	PYTHONPATH=src $(PYTHON) -m draft_room_intelligence.cli build-demo-readiness data/processed/demo_2025_wikipedia_bio_chl_ushl_wikicareer_wikisearch_stats_chltrueplayoffs_openstats_russian_nordic_cleanup_ep_pdf/final outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf --team-depth-csv outputs/org_team_depth_2024_25_with_ahl/depth.csv --gap-top-n 35 --movement-top-n 40

team-fit-2025:
	PYTHONPATH=src $(PYTHON) -m draft_room_intelligence.cli merge-roster-csvs outputs/org_rosters_2024_25_with_ahl.csv outputs/nhl_rosters_20242025.csv outputs/ahl_rosters_2024_25.csv --resolve-cross-org-assignments --nhl-season 20242025 --assignment-cache-dir data/raw/rosters/assignment_logs/20242025
	PYTHONPATH=src $(PYTHON) -m draft_room_intelligence.cli report-team-depth outputs/org_rosters_2024_25_with_ahl.csv outputs/org_team_depth_2024_25_with_ahl

validate-pilot-2019:
	PYTHONPATH=src $(PYTHON) -m draft_room_intelligence.cli report-historical-validation data/processed/pilot_2019 outputs/validation_2019 --precision-n 25 --top-n 25

team-depth-sample:
	PYTHONPATH=src $(PYTHON) -m draft_room_intelligence.cli report-team-depth tests/fixtures/team_rosters_sample.csv outputs/team_depth_sample

nhl-roster-sample:
	PYTHONPATH=src $(PYTHON) -m draft_room_intelligence.cli import-nhl-rosters outputs/nhl_rosters_sample.csv --teams NYI --roster-json-dir tests/fixtures/nhl_api --stats-json-dir tests/fixtures/nhl_api
	PYTHONPATH=src $(PYTHON) -m draft_room_intelligence.cli report-team-depth outputs/nhl_rosters_sample.csv outputs/nhl_team_depth_sample

ep-pdf-sample:
	PYTHONPATH=src $(PYTHON) -m draft_room_intelligence.cli import-eliteprospects-pdf data/raw/draftdata/Draft25.pdf outputs/ep_pdf_2025_sample --draft-year 2025 --page-start 29 --page-end 80 --profile-limit 10

evaluate-consensus:
	$(PYTHON) -m draft_room_intelligence.cli evaluate tests/fixtures/historical_prospects.csv --baseline consensus --precision-n 1

evaluate-projection:
	$(PYTHON) -m draft_room_intelligence.cli evaluate tests/fixtures/historical_prospects.csv --baseline projection --precision-n 1

evaluate-adjusted-production:
	$(PYTHON) -m draft_room_intelligence.cli evaluate tests/fixtures/historical_prospects.csv --baseline adjusted-production --precision-n 1

evaluate-hybrid:
	$(PYTHON) -m draft_room_intelligence.cli evaluate tests/fixtures/historical_prospects.csv --baseline hybrid --precision-n 1

evaluate-pilot-consensus:
	$(PYTHON) -m draft_room_intelligence.cli evaluate data/processed/pilot_2019 --baseline consensus --precision-n 25

evaluate-pilot-projection:
	$(PYTHON) -m draft_room_intelligence.cli evaluate data/processed/pilot_2019 --baseline projection --precision-n 25

evaluate-pilot-adjusted-production:
	$(PYTHON) -m draft_room_intelligence.cli evaluate data/processed/pilot_2019 --baseline adjusted-production --precision-n 25

evaluate-pilot-hybrid:
	$(PYTHON) -m draft_room_intelligence.cli evaluate data/processed/pilot_2019 --baseline hybrid --precision-n 25

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check src tests

check: lint test

clean:
	rm -rf .pytest_cache .ruff_cache build dist *.egg-info
