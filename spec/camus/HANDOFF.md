# Handoff: build PR 4, network scoring

Prompt for the next agent. Read `PROGRESS.md` for where things stand.

## Your task

Build PR 4 of the CAMUS work: score each inferred network against its reference
network with PhyloNet `CmpNets`, writing `inference_data/network_scores.csv`. The design
is `PLAN.md`, section "PR 4 — Network scoring with PhyloNet", and the measurements behind
it are `scoring.md`. The decision that shapes the adapter is
`docs/adr/0001-bidirectional-reference-networks.md`. Terms are in `CONTEXT.md`; use them.

Done when `pch experiment network-score experiments/camus_smoke/experiment_specification.yaml`
runs on a laptop over the 72 rows of `camus_registry.csv` and writes `network_scores.csv`
with FN, FP, AVG and a runtime per row.

## How to work

1. Branch `camus-scoring` off `camus-registry` (PR #35). Open the PR against
   `camus-registry`; it is the fifth PR in the stack.
2. Write a task plan first, at `spec/camus/plans/pr4-scoring.md`, in the shape of
   `spec/camus/plans/pr3-registry.md`: tasks with exact code and tests, a Global
   Constraints section, a Review Focus list. Aim for three tasks: the adapter; the
   scorer (`resolve_reference_network`, `network_score` with timeout); the CLI command
   and its handler.
3. Execute with a subagent team, as the user wants: one implementer subagent per task,
   one reviewer per task, a whole-branch review on the most capable model, one fix wave,
   one scoped re-review. Keep a ledger. Run the smoke experiment yourself at the end.
4. Commit and push when the user says so; open the PR with a body that carries the
   measurements, like #33 and #35.

## Facts you need

- CAMUS newicks in `camus_registry.csv` are topology-only Rich newick, like
  `(((A,(B)#H1),((#H1,C),D)),OUT);`. Row k = 0 is the guide tree.
- Reference networks: `simulation_data/model_networks/net{h}-{t}.txt`, line 1 the base
  tree with lengths and the outgroup grafted, then one contact line per event,
  `cladeA;cladeB;time;strength`. Clades are exact substrings of line 1, without their
  own length. Register rows: `model_graph_registry.csv` (`horizontal_edges`, `model_tree`,
  `path`, `outgroup`, ...). The dataset → model tree join is via
  `simulated_data_registry.csv` on `dataset_id == path`, as `handle_score.py` does it.
- Adapter output for contact event i between clades A and B, verified in PhyloNet:
  `A_subtree → ((A_subtree)#H{2i},#H{2i-1})`, `B_subtree → ((B_subtree)#H{2i-1},#H{2i})`.
  Donor above hybrid on both branches. Several contacts on one branch nest by
  `contact_time`, earliest outermost. Strip lengths last. Anchor clade matches on
  delimiters so `t2` never matches `t26`.
- CmpNets contract, verified on 3.8.5: NEXUS with a `NETWORKS` block and
  `CmpNets net1 net2 -m cluster;`, bare identifiers, the newick's own `;` ends the
  statement, net1 is the reference, output line
  `The cluster-based distance between two networks: FN FP AVG`. Any level works.
  Inheritance probabilities crash it. Mismatched taxon sets return numbers silently:
  assert equal sets in Python first.
- Timeout 2 h per call, `runtime_seconds` per row, status `ok | failed | timeout`;
  failed and timed-out rows are written with null scores. The paper saw over 5 h for one
  51-species network; ours are 31 taxa with k up to about 6, unmeasured.
- Scoring is a separate stage: never touches inference rows or resume.

## Running things here

- Binaries live in the main checkout's `bin/` and are git-ignored; a fresh worktree has
  none. Symlink them (`LingPhyloSimulator.jar`, `paup`, `mb`, `Astral`, `astral3`,
  `wastral`, `PhyloNet.jar`) and build CAMUS with `bash scripts/sh/installs/install_camus.sh`.
  Or symlink from `.claude/worktrees/camus-run/bin`, which has all of them.
- The worktree sandbox refuses `source`, heredoc-appends into git commands, and most
  compound shell. Set env inline:
  `PYTHONPATH=. PCH_SCRATCH=/private/tmp/claude-501/scr PCH_ASTRAL_XMX=4g uv run python -m scripts.py.cli.main ...`.
  To run a shell script directly: `PATH="$PWD/.venv/bin:$PATH" bash scripts/sh/...`.
- Smoke data with 12 families already exists in
  `.claude/worktrees/camus-registry/experiments/camus_smoke/` (simulation_data and
  inference_data, git-ignored). Copy both folders into your worktree to skip the
  6-minute inference run; paths inside are relative to the repo root.
- Checks: `uv run python -m pytest tests/ -q` (179 pass at #35),
  `uv run ty check scripts/lib scripts/py`, `uv run ruff check`, `uv run ruff format`.

## User preferences

- Brevity everywhere: code comments, docs, replies. Every word must earn its place.
- No `Any`, no `object` as a type, no avoidable `# type: ignore`.
- Record raw data; defer analysis, figures and config knobs. Do not add a quartet
  filter option, an elbow plot, or a calibration gate.
- Replies in terse fragments are fine; code, commits and PR bodies in normal prose.
- Ask before pushing or opening a PR unless already told to.
