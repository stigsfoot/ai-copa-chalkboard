.PHONY: help install test lint run smoke

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

install: ## Install the package + dev/adk extras (uv recommended)
	uv pip install -e ".[dev,adk]" || pip install -e ".[dev,adk]"

test: ## Run the offline test suite (no API key needed)
	PYTHONPATH=. python -m pytest

lint: ## Lint with ruff (if installed)
	ruff check copa_chalkboard tests || echo "ruff not installed; skipping"

run: ## Run the two-agent pipeline on an image (IMAGE=url-or-path). Needs GEMINI_API_KEY.
	@test -n "$(IMAGE)" || (echo "Usage: make run IMAGE=<url-or-path>"; exit 1)
	python -m copa_chalkboard --image "$(IMAGE)"

smoke: ## Run the vision-reliability smoke-test (<=6 Gemini calls). Needs GEMINI_API_KEY.
	python experiments/scout-smoketest/copa_scout_smoketest.py
