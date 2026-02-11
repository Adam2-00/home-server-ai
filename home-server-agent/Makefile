.PHONY: install test clean run web dashboard help

help:
	@echo "Home Server AI Setup Agent - Makefile"
	@echo ""
	@echo "Available targets:"
	@echo "  install    - Install dependencies"
	@echo "  test       - Run tests"
	@echo "  run        - Run interactive setup"
	@echo "  web        - Run with web configuration"
	@echo "  dry-run    - Show what would be done (no execution)"
	@echo "  dashboard  - Show session dashboard"
	@echo "  clean      - Clean up generated files"
	@echo ""

install:
	pip3 install -r requirements.txt

test:
	python3 tests/test_basic.py

run:
	python3 main.py

web:
	python3 main.py --web

dry-run:
	python3 main.py --dry-run

dashboard:
	python3 dashboard.py

clean:
	rm -f *.log state.db config.json session_*.json
	rm -rf __pycache__ */__pycache__
