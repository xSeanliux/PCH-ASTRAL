.PHONY: uv-lock

uv-lock: 
	uv lock

py-test:
	uv run python -m pytest tests/

py-static: 
	uv run ty check scripts/lib scripts/py 

py-fmt: 
	uv run ruff format scripts/lib scripts/py

py-lint:
	uv run ruff check --fix scripts/lib scripts/py

py-lint-check:
	uv run ruff check scripts/lib scripts/py

install-uv: 
	@curl -LsSf https://astral.sh/uv/install.sh | sh

install-astral3:
	@bash scripts/sh/installs/install_astral3.sh

install-aster:
	@bash scripts/sh/installs/install_aster.sh

install-w-tree-qmc:
	@bash scripts/sh/installs/install_w_tree_qmc.sh

install-paup:
	@bash scripts/sh/installs/install_paup.sh

install-mrbayes: 
	@bash scripts/sh/installs/install_mrbayes.sh

install-bins: install-astral3 install-aster install-mrbayes install-paup install-w-tree-qmc

setup: install-uv
	uv sync