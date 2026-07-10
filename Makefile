.PHONY: install-dev demo evaluate-consensus evaluate-projection evaluate-adjusted-production evaluate-hybrid evaluate-pilot-consensus evaluate-pilot-projection evaluate-pilot-adjusted-production evaluate-pilot-hybrid test lint check clean

PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)

install-dev:
	$(PYTHON) -m pip install -e ".[dev]"

demo:
	$(PYTHON) -m draft_room_intelligence.cli demo

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
