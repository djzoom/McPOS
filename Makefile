.PHONY: bootstrap lint test format deploy

bootstrap:
	python -m venv .venv
	. .venv/bin/activate && pip install -r requirements.txt

lint:
	@echo "🔍 Add linting tools (flake8, ruff, mypy) and wire them here."

test:
	pytest

format:
	@echo "✨ Add formatting commands (black, isort) here."

deploy:
	@echo "🚀 Hook your deployment pipeline here."
