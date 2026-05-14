.PHONY: uv-lock

uv-lock: 
	uv lock

py-test:
	uv run pytest tests/

py-static: 
	uv run ty check scripts/lib scripts/py 

py-fmt: 
	uv run ruff format

py-lint:
	uv run ruff check --fix

setup: 
	chmod +x .git/hooks/precommit
	uv sync