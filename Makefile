.PHONY: help install sync lock test lint fmt run clean

help:
	@echo "McPOS — Multi-channel publishing OS"
	@echo ""
	@echo "  make install   Create venv + install deps (uv sync)"
	@echo "  make sync      Sync venv from uv.lock"
	@echo "  make lock      Re-resolve deps → uv.lock"
	@echo "  make test      Run pytest"
	@echo "  make lint      Run ruff check"
	@echo "  make fmt       Run ruff format"
	@echo "  make run CH=<id> CMD=<cmd>"
	@echo "                 e.g. make run CH=kat CMD='list-episodes'"
	@echo "  make clean     Remove __pycache__, .pytest_cache"

install sync:
	uv sync

lock:
	uv lock

test:
	uv run pytest tests/ -q

lint:
	uv run ruff check mcpos/ tests/

fmt:
	uv run ruff format mcpos/ tests/

run:
	@if [ -z "$(CH)" ] || [ -z "$(CMD)" ]; then \
		echo "usage: make run CH=<channel_id> CMD='<subcommand>'"; exit 1; \
	fi
	uv run python -m mcpos.cli.main $(CMD) $(CH)

clean:
	find . -type d \( -name __pycache__ -o -name .pytest_cache -o -name .ruff_cache \) \
	    -not -path "./.venv/*" -exec rm -rf {} +
