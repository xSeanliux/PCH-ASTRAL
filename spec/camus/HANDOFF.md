# Handoff

PR 4 is built on the `camus-scoring` gh-stack (`adapter` ← `scorer` ← `cli`, trunk
`camus-registry`), reviewed and smoke-tested; see `PROGRESS.md`. Nothing is queued. Pick
from "Follow-ups" in `PROGRESS.md`; `experiments/camus_study` on the cluster is the natural
next.

Running notes that still hold: binaries are symlinked into `bin/` per worktree; the sandbox
refuses `source`, so set `PYTHONPATH=. PCH_SCRATCH=... PCH_ASTRAL_XMX=4g` inline; smoke
data lives in `experiments/camus_smoke/` (git-ignored); checks are
`uv run python -m pytest tests/ -q` (196 pass), `uv run ty check scripts/lib scripts/py`,
`uv run ruff check`, `uv run ruff format`.

User preferences: brevity everywhere; no `Any`, `object`, or avoidable `# type: ignore`;
record raw data, defer analysis and knobs; terse replies, normal prose in code, commits and
PR bodies; ask before pushing or opening a PR.
