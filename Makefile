.PHONY: uv-lock

uv-lock: 
	uv lock

py-test:
	uv run pytest tests/

py-static: 
	uv run ty check scripts/lib scripts/py 

py-fmt: 
	uv run ruff format scripts/lib scripts/py

py-lint:
	uv run ruff check --fix scripts/lib scripts/py

setup: 
	uv sync