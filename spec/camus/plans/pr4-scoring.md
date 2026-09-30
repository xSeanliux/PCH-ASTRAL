# CAMUS network scoring — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Score every row of `camus_registry.csv` against its reference network with PhyloNet `CmpNets -m cluster`, writing `inference_data/network_scores.csv`.

**Architecture:** An adapter turns a contact network file (`net{h}-{t}.txt`) into topology-only Rich newick, two contact edges per event. A scorer writes one NEXUS to a temp file, runs `bin/PhyloNet.jar` with a 2 h timeout, parses the distance line. A handler clones `handle_score.py`: join the family registry to the sim registry, score each new key, full rewrite. Scoring never touches inference rows or resume.

**Tech Stack:** Python 3.12, polars, pytest, Java (PhyloNet 3.8.5 at `bin/PhyloNet.jar`). Type checker `ty`, linter `ruff`.

**Spec:** `spec/camus/PLAN.md` section "PR 4", `spec/camus/scoring.md`, `docs/adr/0001-bidirectional-reference-networks.md`. Terms in `CONTEXT.md`.

## Global Constraints

- Run tests with `uv run python -m pytest tests/ -q`; type-check with `uv run ty check scripts/lib scripts/py`; lint with `uv run ruff check` and `uv run ruff format`. All three clean before commit.
- No `Any`, no `object` as a type, no `# type: ignore` on lines that can be typed (user rule).
- Keep prose brief: comments and docstrings say why, not what.
- Contact event i (1-based, events sorted by `contact_time` ascending) between clades A and B: `A → ((A)#H{2i},#H{2i-1})`, `B → ((B)#H{2i-1},#H{2i})`. Donor above hybrid on both. Verified in PhyloNet; do not reorder.
- Clade match: exact substring of line 1, anchored on `[(,]` before and `[:,)]` after, exactly one match or raise.
- Branch lengths stripped last. Output ends in exactly one `;`.
- NEXUS: `net1` is the reference, `net2` the estimate. One `;` after each newick. No inheritance probabilities.
- Output line: `The cluster-based distance between two networks: FN FP AVG` (verified 3.8.5).
- Assert equal taxon sets in Python before calling the jar: CmpNets returns numbers silently on a mismatch.
- `network_scores.csv` columns: `dataset_id, guide_tree, config_hash, k, fn, fp, avg, runtime_seconds, status`. Status `ok | failed | timeout`; failed and timed-out rows carry null scores and a runtime. Key: `(dataset_id, guide_tree, config_hash, k)`; `config_hash` is in the key so a future `CamusConfig` knob cannot collide two families.
- Timeout 2 h (7200 s) per call. Runtime measured in the handler around the call so every row has one.
- Commit messages: Conventional Commits, end with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- One `gh stack` layer per task on trunk `camus-registry`: `camus-scoring/adapter` ← `camus-scoring/scorer` ← `camus-scoring/cli`. The orchestrator switches layers; implementers commit on the current branch.

## Review Focus

1. Clade `t2` must not match inside `t26`, nor `t1` inside `t15`. Pinned by Task 1's `test_leaf_clade_does_not_match_a_longer_label`.
2. Two events on one branch: earliest outermost, and the descendant's clade is still found after the ancestor's wrap. Pinned by Task 1's `test_two_contacts_on_one_branch_nest_earliest_outermost`.
3. The 6-taxon reference reproduces `scoring.md` byte for byte. Pinned by Task 1's `test_six_taxon_reference`.
4. Mismatched taxon sets raise before the jar runs. Pinned by Task 2's `test_network_score_rejects_mismatched_taxa`.
5. A timed-out or failed call writes a row with null scores, a runtime and its status, and a rerun does not retry it. Pinned by Task 3's `test_timeout_and_failure_rows` and `test_incremental`.
6. `handle_network_score` reads `camus_registry.csv`, never `inference_registry.csv`, and writes nothing else. Pinned by Task 3's `test_writes_scores`.

---

### Task 1: `network_format.py` — contact network file → Rich newick

**Files:**
- Create: `scripts/lib/inference/network_format.py`
- Test: `tests/scripts/lib/inference/test_network_format.py`

**Interfaces:**
- Produces: `contact_network_to_rich_newick(text: str) -> str`. `text` is the whole file: line 1 the base tree (with lengths, possibly no trailing `;`), then `cladeA;cladeB;contact_time;transmission_strength` lines. An `h = 0` file (one line) returns the tree, lengths stripped.

- [ ] **Step 1: Write the failing tests**

`tests/scripts/lib/inference/test_network_format.py`:

```python
import pytest

from scripts.lib.inference.network_format import contact_network_to_rich_newick

SIX = "((((A:1,B:1):1,C:1):1,(D:1,E:1):1):1,OUT:1)"


def test_six_taxon_reference():
    # The case measured in spec/camus/scoring.md.
    text = SIX + "\nB;C;0.5;0.3\n"
    assert (
        contact_network_to_rich_newick(text)
        == "((((A,((B)#H2,#H1)),((C)#H1,#H2)),(D,E)),OUT);"
    )


def test_base_tree_alone_strips_lengths():
    assert contact_network_to_rich_newick(SIX + ";\n") == "((((A,B),C),(D,E)),OUT);"


def test_subtree_clade_is_matched_without_its_length():
    text = SIX + "\n(A:1,B:1);D;0.5;0.3\n"
    assert (
        contact_network_to_rich_newick(text)
        == "(((((A,B))#H2,#H1),C),(((D)#H1,#H2),E)),OUT);"
    )


def test_two_contacts_on_one_branch_nest_earliest_outermost():
    # Listed later, happens earlier: sorted by time, so the t=0.2 event wraps outside.
    text = SIX + "\nB;C;0.8;0.3\nB;D;0.2;0.3\n"
    out = contact_network_to_rich_newick(text)
    assert out == "((((A,((((B)#H4,#H3))#H2,#H1)),((C)#H3,#H4)),(((D)#H1,#H2),E)),OUT);"


def test_leaf_clade_does_not_match_a_longer_label():
    tree = "(((t2:1,t26:1):1,t1:1):1,OUT:1)"
    out = contact_network_to_rich_newick(tree + "\nt2;t1;0.5;0.3\n")
    assert out == "(((((t2)#H2,#H1),t26),((t1)#H1,#H2)),OUT);"


def test_missing_clade_raises():
    with pytest.raises(ValueError, match="matched 0"):
        contact_network_to_rich_newick(SIX + "\nZ;C;0.5;0.3\n")
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run python -m pytest tests/scripts/lib/inference/test_network_format.py -q`
Expected: FAIL with `ImportError` (no module `network_format`).

- [ ] **Step 3: Implement `network_format.py`**

```python
"""Contact network file -> Rich newick for PhyloNet.

`net{h}-{t}.txt`: line 1 the base tree, then one `cladeA;cladeB;time;strength`
line per contact event. Each event becomes two contact edges, one per direction
(docs/adr/0001), so a single-direction estimate cannot score 0 when h >= 1.
"""

import re

_LENGTH = re.compile(r":[-+0-9.eE]+")


def _wrap(tree: str, clade: str, wrapped: str) -> str:
    # Anchor on newick delimiters so `t2` never matches inside `t26`.
    pattern = re.compile(rf"(?<=[(,]){re.escape(clade)}(?=[:,)])")
    tree, n = pattern.subn(lambda _: wrapped, tree)
    if n != 1:
        raise ValueError(f"clade {clade!r} matched {n} times, want 1")
    return tree


def contact_network_to_rich_newick(text: str) -> str:
    """Line 1 of `text` is the base tree; each later line a contact event."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    tree = lines[0].rstrip(";")
    events: list[tuple[float, str, str]] = []
    for line in lines[1:]:
        a, b, time, _strength = line.split(";")
        events.append((float(time), a, b))
    # Earliest first: an ancestor branch's event wraps before a descendant's
    # clade is looked up, and the descendant is still an exact substring.
    for i, (_, a, b) in enumerate(sorted(events), start=1):
        tree = _wrap(tree, a, f"(({a})#H{2 * i},#H{2 * i - 1})")
        tree = _wrap(tree, b, f"(({b})#H{2 * i - 1},#H{2 * i})")
    return _LENGTH.sub("", tree) + ";"
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run python -m pytest tests/scripts/lib/inference/test_network_format.py -q`
Expected: all PASS.

- [ ] **Step 5: Lint, type-check, commit**

```bash
uv run ruff format scripts/lib/inference/network_format.py tests/scripts/lib/inference/test_network_format.py
uv run ruff check scripts/lib/inference/network_format.py tests/scripts/lib/inference/test_network_format.py
uv run ty check scripts/lib scripts/py
git add scripts/lib/inference/network_format.py tests/scripts/lib/inference/test_network_format.py
git commit -m "feat(camus): adapter from contact network file to Rich newick"
```

---

### Task 2: `scoring.py` — `resolve_reference_network`, `network_score`

**Files:**
- Modify: `scripts/lib/inference/scoring.py`
- Test: `tests/scripts/lib/inference/test_scoring.py` (append)

**Interfaces:**
- Consumes: `contact_network_to_rich_newick` (Task 1), `MODEL_GRAPH_REGISTRY`.
- Produces: `NetworkScore(fn, fp, avg)`; `resolve_reference_network(experiment_folder: Path, horizontal_edges: int, model_tree: int) -> str` (cached like `resolve_reference_newick`); `taxa(newick: str) -> set[str]`; `network_score(estimate_newick: str, reference_newick: str, *, timeout_seconds: float = 7200) -> NetworkScore`, raising `subprocess.TimeoutExpired` past the timeout, `ValueError` on a taxon mismatch, `RuntimeError` on a bad exit or unparsable output.

- [ ] **Step 1: Write the failing tests**

Append to `tests/scripts/lib/inference/test_scoring.py`. The file's module-level `pytestmark` skips everything without `Rscript`; move it onto the two existing tests and guard the new ones on Java + the jar:

```python
import shutil
from pathlib import Path

import polars as pl
import pytest

from scripts.lib.inference.scoring import (
    network_score,
    resolve_reference_network,
    score,
    taxa,
)

needs_r = pytest.mark.skipif(shutil.which("Rscript") is None, reason="Rscript not installed")
needs_phylonet = pytest.mark.skipif(
    shutil.which("java") is None or not Path("bin/PhyloNet.jar").exists(),
    reason="java or bin/PhyloNet.jar missing",
)

TREE = "((t1,t2),(t3,t4),t5);"


@needs_r
def test_identical_trees_zero_rates() -> None:
    ...  # unchanged body


@needs_r
def test_discordant_estimate_has_fn() -> None:
    ...  # unchanged body


REF = "((((A,((B)#H2,#H1)),((C)#H1,#H2)),(D,E)),OUT);"


def test_taxa_skips_hybrid_labels_and_lengths():
    assert taxa("((A:1,(B:1)#H1:1),(#H1,C:1));") == {"A", "B", "C"}


def test_network_score_rejects_mismatched_taxa():
    with pytest.raises(ValueError, match="taxon sets differ"):
        network_score("((A,B),C);", REF)


def test_resolve_reference_network_reads_the_registered_file(tmp_path: Path):
    net = tmp_path / "net1-1.txt"
    net.write_text("((((A:1,B:1):1,C:1):1,(D:1,E:1):1):1,OUT:1)\nB;C;0.5;0.3\n")
    (tmp_path / "simulation_data").mkdir()
    pl.DataFrame(
        {
            "horizontal_edges": [1],
            "model_tree": [1],
            "path": [str(net)],
            "outgroup": ["OUT"],
            "outgroup_seed": [1],
            "outgroup_branch_length": [1.0],
            "ingroup_stem_length": [1.0],
        }
    ).write_csv(tmp_path / "simulation_data" / "model_graph_registry.csv")
    assert resolve_reference_network(tmp_path, 1, 1) == REF
    with pytest.raises(ValueError):
        resolve_reference_network(tmp_path, 2, 1)


@needs_phylonet
def test_network_score_reference_against_itself_is_zero():
    s = network_score(REF, REF)
    assert (s.fn, s.fp, s.avg) == (0.0, 0.0, 0.0)


@needs_phylonet
def test_network_score_plain_tree_has_fn():
    # scoring.md: the plain tree scores FN 0.333, FP 0.
    s = network_score("((((A,B),C),(D,E)),OUT);", REF)
    assert s.fn == pytest.approx(1 / 3)
    assert s.fp == 0.0
    assert s.avg == pytest.approx(1 / 6)
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run python -m pytest tests/scripts/lib/inference/test_scoring.py -q`
Expected: FAIL with `ImportError` (`network_score`, `resolve_reference_network`, `taxa`).

- [ ] **Step 3: Implement**

In `scripts/lib/inference/scoring.py`, change the module docstring to `"""RF and network scoring — the only scoring subprocess sites."""`, add `import re` and `from scripts.lib.inference.network_format import contact_network_to_rich_newick`, and append:

```python
@dataclass
class NetworkScore:
    fn: float
    fp: float
    avg: float


# Cached like resolve_reference_newick: one parse per distinct key per process.
@functools.lru_cache(maxsize=None)
def resolve_reference_network(
    experiment_folder: Path, horizontal_edges: int, model_tree: int
) -> str:
    """Rich newick of the reference network; h == 0 is the base tree alone."""
    reg = experiment_folder / "simulation_data" / "model_graph_registry.csv"
    df = pl.read_csv(reg, schema=MODEL_GRAPH_REGISTRY).filter(
        (pl.col("horizontal_edges") == horizontal_edges)
        & (pl.col("model_tree") == model_tree)
    )
    if df.height == 0:
        raise ValueError(
            f"No network for h={horizontal_edges}, model_tree={model_tree} in {reg}"
        )
    return contact_network_to_rich_newick(
        Path(df.row(0, named=True)["path"]).read_text()
    )


# A leaf label follows `(` or `,`; a hybrid reference `#H1` starts with `#`.
_TAXON = re.compile(r"(?<=[(,])[^(),:;#]+")
_DISTANCE = re.compile(r"distance between two networks:\s*(\S+)\s+(\S+)\s+(\S+)")


def taxa(newick: str) -> set[str]:
    return set(_TAXON.findall(newick))


def network_score(
    estimate_newick: str, reference_newick: str, *, timeout_seconds: float = 7200
) -> NetworkScore:
    """`CmpNets -m cluster`, reference as net1. Raises subprocess.TimeoutExpired
    past `timeout_seconds`."""
    if taxa(estimate_newick) != taxa(reference_newick):
        # CmpNets returns numbers for mismatched sets; fail loudly instead.
        raise ValueError(
            f"taxon sets differ: {sorted(taxa(estimate_newick) ^ taxa(reference_newick))}"
        )
    nexus = (
        "#NEXUS\nBEGIN NETWORKS;\n"
        f"Network net1 = {reference_newick.strip().rstrip(';')};\n"
        f"Network net2 = {estimate_newick.strip().rstrip(';')};\n"
        "END;\nBEGIN PHYLONET;\nCmpNets net1 net2 -m cluster;\nEND;\n"
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".nex", delete=False) as f:
        f.write(nexus)
        tmp = Path(f.name)
    try:
        proc = subprocess.run(
            ["java", "-jar", "bin/PhyloNet.jar", str(tmp)],
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"PhyloNet failed (exit {proc.returncode}): {proc.stdout}{proc.stderr}"
            )
        m = _DISTANCE.search(proc.stdout)
        if m is None:
            raise RuntimeError(f"PhyloNet: no distance line in {proc.stdout!r}")
        fn, fp, avg = (float(x) for x in m.groups())
        return NetworkScore(fn=fn, fp=fp, avg=avg)
    finally:
        tmp.unlink(missing_ok=True)
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run python -m pytest tests/scripts/lib/inference/test_scoring.py tests/scripts/lib/inference/test_network_format.py -q`
Expected: all PASS (the two `needs_phylonet` tests run: `bin/PhyloNet.jar` is present here).

- [ ] **Step 5: Lint, type-check, commit**

```bash
uv run ruff format scripts/lib/inference/scoring.py tests/scripts/lib/inference/test_scoring.py
uv run ruff check scripts/lib/inference/scoring.py tests/scripts/lib/inference/test_scoring.py
uv run ty check scripts/lib scripts/py
git add scripts/lib/inference/scoring.py tests/scripts/lib/inference/test_scoring.py
git commit -m "feat(camus): network_score via PhyloNet CmpNets, resolve_reference_network"
```

---

### Task 3: `handle_network_score.py` + `pch experiment network-score`

**Files:**
- Modify: `scripts/py/cli/schemata.py` (add `NETWORK_SCORES_SCHEMA` after `SCORES_SCHEMA`)
- Create: `scripts/py/cli/handle_network_score.py`
- Modify: `scripts/py/cli/main.py` (register the command)
- Test: `tests/scripts/py/cli/test_handle_network_score.py`

**Interfaces:**
- Consumes: `camus_registry.registry_path`, `registry.canonical_path`, `resolve_reference_network`, `network_score` (Task 2), `CAMUS_REGISTRY_SCHEMA`, `SIMULATED_DATA_REGISTRY_SCHEMA`.
- Produces: `handle_network_score(config: ExperimentConfig) -> Path`; `NETWORK_SCORES_SCHEMA`; command `pch experiment network-score CONFIG`.

- [ ] **Step 1: Add the schema**

In `scripts/py/cli/schemata.py`, after `SCORES_SCHEMA`:

```python
# One row per (dataset, guide tree, config, k): CmpNets -m cluster against the
# reference network. Null scores with status `failed` | `timeout`.
NETWORK_SCORES_SCHEMA = pl.Schema(
    {
        "dataset_id": String,
        "guide_tree": String,
        "config_hash": String,
        "k": Int64,
        "fn": Float64,
        "fp": Float64,
        "avg": Float64,
        "runtime_seconds": Float64,
        "status": String,
    }
)
```

- [ ] **Step 2: Write the failing tests**

`tests/scripts/py/cli/test_handle_network_score.py`:

```python
import subprocess
from pathlib import Path

import polars as pl
import pytest

import scripts.py.cli.handle_network_score as hns
from scripts.lib.experiment import ExperimentConfig
from scripts.lib.inference.scoring import NetworkScore
from scripts.py.cli.handle_network_score import handle_network_score
from scripts.py.cli.schemata import CAMUS_REGISTRY_SCHEMA, NETWORK_SCORES_SCHEMA

from tests.scripts.py.cli.test_handle_inference import _config

REF_TEXT = "((((A:1,B:1):1,C:1):1,(D:1,E:1):1):1,OUT:1)\nB;C;0.5;0.3\n"
NEWICKS = ["((((A,B),C),(D,E)),OUT);", "((((A,((B)#H1)),(#H1,C)),(D,E)),OUT);"]


def _setup(tmp_path: Path) -> ExperimentConfig:
    sim_dir = tmp_path / "simulation_data" / "simulated_data" / "high_0.1_4_320"
    sim_dir.mkdir(parents=True)
    dataset = sim_dir / "sim_1_1_1.csv"
    dataset.write_text("id,feature,weight,A,B,C,D,E,OUT\n")
    net = tmp_path / "simulation_data" / "net1-1.txt"
    net.write_text(REF_TEXT)
    pl.DataFrame(
        {
            "horizontal_edges": [1],
            "model_tree": [1],
            "path": [str(net)],
            "outgroup": ["OUT"],
            "outgroup_seed": [1],
            "outgroup_branch_length": [1.0],
            "ingroup_stem_length": [1.0],
        }
    ).write_csv(tmp_path / "simulation_data" / "model_graph_registry.csv")
    pl.DataFrame(
        {
            "poly_level": ["high"],
            "character_count": [320],
            "min_tree_height": [4],
            "homoplasy_factor": [0.1],
            "horizontal_edges": [1],
            "model_tree": [1],
            "replica": [1],
            "path": [str(dataset)],
        }
    ).write_csv(tmp_path / "simulation_data" / "simulated_data_registry.csv")
    (tmp_path / "inference_data").mkdir()
    pl.DataFrame(
        {
            "dataset_id": [str(dataset)] * 2,
            "guide_tree": ["true_tree"] * 2,
            "config_hash": ["h"] * 2,
            "runtime_seconds": [1.0] * 2,
            "status": ["ok"] * 2,
            "ran_at": ["2026-09-29T00:00:00+00:00"] * 2,
            "log_path": ["l"] * 2,
            "k": [0, 1],
            "qsat_percent": [0.0, 50.0],
            "network_newick": NEWICKS,
        },
        schema=CAMUS_REGISTRY_SCHEMA,
    ).write_csv(tmp_path / "inference_data" / "camus_registry.csv")
    return ExperimentConfig.model_validate(
        _config(tmp_path, methods={"camus": {"guide_trees": ["true_tree"]}})
    )


def test_writes_scores(tmp_path: Path, monkeypatch):
    cfg = _setup(tmp_path)
    seen: list[tuple[str, str]] = []
    monkeypatch.setattr(
        hns, "network_score", lambda est, ref: seen.append((est, ref)) or NetworkScore(0.5, 0.0, 0.25)
    )
    out = handle_network_score(cfg)

    df = pl.read_csv(out, schema=NETWORK_SCORES_SCHEMA).sort("k")
    assert df.columns == list(NETWORK_SCORES_SCHEMA.keys())
    assert df["k"].to_list() == [0, 1]
    assert df["fn"].to_list() == [0.5, 0.5]
    assert df["status"].to_list() == ["ok", "ok"]
    assert all(t >= 0 for t in df["runtime_seconds"].to_list())
    assert [e for e, _ in seen] == NEWICKS
    assert {r for _, r in seen} == {"((((A,((B)#H2,#H1)),((C)#H1,#H2)),(D,E)),OUT);"}


def test_incremental(tmp_path: Path, monkeypatch):
    cfg = _setup(tmp_path)
    calls: list[int] = []
    monkeypatch.setattr(
        hns, "network_score", lambda est, ref: calls.append(1) or NetworkScore(0.5, 0.0, 0.25)
    )
    handle_network_score(cfg)
    handle_network_score(cfg)
    assert len(calls) == 2
    assert pl.read_csv(tmp_path / "inference_data" / "network_scores.csv").height == 2


def test_timeout_and_failure_rows(tmp_path: Path, monkeypatch, capsys):
    cfg = _setup(tmp_path)

    def fake(est: str, ref: str) -> NetworkScore:
        if "#H1" in est:
            raise subprocess.TimeoutExpired(["java"], 7200)
        raise RuntimeError("boom")

    monkeypatch.setattr(hns, "network_score", fake)
    out = handle_network_score(cfg)

    df = pl.read_csv(out, schema=NETWORK_SCORES_SCHEMA).sort("k")
    assert df["status"].to_list() == ["failed", "timeout"]
    assert df["fn"].to_list() == [None, None]
    assert df["runtime_seconds"].null_count() == 0
    assert "boom" in capsys.readouterr().out

    # Not retried: the rows are visible, so the next run leaves them alone.
    monkeypatch.setattr(hns, "network_score", lambda est, ref: pytest.fail("retried"))
    handle_network_score(cfg)
```

- [ ] **Step 3: Run the tests to see them fail**

Run: `uv run python -m pytest tests/scripts/py/cli/test_handle_network_score.py -q`
Expected: FAIL with `ImportError` (no module `handle_network_score`).

- [ ] **Step 4: Implement the handler**

`scripts/py/cli/handle_network_score.py`:

```python
"""`pch experiment network-score` — CmpNets each network family row against its
reference network.

Reads camus_registry.csv, joins simulated_data_registry on dataset_id == path for
(horizontal_edges, model_tree), writes inference_data/network_scores.csv. A key
already in the file is kept, failed and timed-out rows included: a slow network
stays visible and is not retried every run. Never touches inference rows.
"""

import subprocess
import time
from pathlib import Path

import polars as pl
from rich import print

from scripts.lib.experiment import ExperimentConfig
from scripts.lib.inference import camus_registry, registry
from scripts.lib.inference.registry import Cell
from scripts.lib.inference.scoring import network_score, resolve_reference_network
from scripts.py.cli.schemata import (
    CAMUS_REGISTRY_SCHEMA,
    NETWORK_SCORES_SCHEMA,
    SIMULATED_DATA_REGISTRY_SCHEMA,
)

KEY = ["dataset_id", "guide_tree", "config_hash", "k"]


def handle_network_score(config: ExperimentConfig) -> Path:
    experiment_folder = config.experiment_folder
    fam_csv = camus_registry.registry_path(experiment_folder)
    assert fam_csv.exists(), (
        f"No network family registry at {fam_csv}. Run `pch experiment inference` with camus first."
    )
    sim_csv = experiment_folder / "simulation_data" / "simulated_data_registry.csv"
    assert sim_csv.exists(), f"No simulation registry at {sim_csv}."
    out = experiment_folder / "inference_data" / "network_scores.csv"

    existing = (
        pl.read_csv(out, schema=NETWORK_SCORES_SCHEMA)
        if out.exists()
        else pl.DataFrame(schema=NETWORK_SCORES_SCHEMA)
    )
    already = {tuple(r[c] for c in KEY) for r in existing.iter_rows(named=True)}

    fam = pl.read_csv(fam_csv, schema=CAMUS_REGISTRY_SCHEMA)
    sim = pl.read_csv(sim_csv, schema=SIMULATED_DATA_REGISTRY_SCHEMA).select(
        pl.col("path").map_elements(registry.canonical_path, return_dtype=pl.String),
        "horizontal_edges",
        "model_tree",
    )
    joined = fam.join(sim, left_on="dataset_id", right_on="path")

    new: list[dict[str, Cell]] = []
    for r in joined.iter_rows(named=True):
        key = tuple(r[c] for c in KEY)
        if key in already or not r["network_newick"]:
            continue
        already.add(key)  # a duplicate sim `path` row fans the join out
        row: dict[str, Cell] = {c: r[c] for c in KEY} | {"fn": None, "fp": None, "avg": None}
        label = f"{r['dataset_id']} {r['guide_tree']} k={r['k']}"
        t0 = time.perf_counter()
        try:
            ref = resolve_reference_network(
                experiment_folder, r["horizontal_edges"], r["model_tree"]
            )
            s = network_score(r["network_newick"], ref)
            row |= {"fn": s.fn, "fp": s.fp, "avg": s.avg, "status": "ok"}
        except subprocess.TimeoutExpired:
            row["status"] = "timeout"
            print(f"[yellow]Timed out: {label}[/yellow]")
        except Exception as e:  # noqa: BLE001 — one bad score must not abort the pass
            row["status"] = "failed"
            print(f"[yellow]Scoring failed for {label}: {e}[/yellow]")
        row["runtime_seconds"] = time.perf_counter() - t0
        print(f"{row['status']} {label} in {row['runtime_seconds']:.1f}s")
        new.append(row)

    out.parent.mkdir(parents=True, exist_ok=True)
    pl.concat([existing, pl.DataFrame(new, schema=NETWORK_SCORES_SCHEMA)]).write_csv(out)
    return out
```

`Cell` is `str | int | float | None` in `registry.py`; import it rather than redefining.

- [ ] **Step 5: Register the command**

In `scripts/py/cli/main.py`, import `from scripts.py.cli.handle_network_score import handle_network_score` and add after `score_experiment`:

```python
@experiment.command(name="network-score")
def network_score_experiment(config_path: Path):
    """CmpNets every network family row against its reference network."""
    out = handle_network_score(_get_experiment_config(config_path))
    print(f"Network scores in [green]{out}[/green] (join to camus_registry.csv).")
```

- [ ] **Step 6: Run the tests to see them pass**

Run: `uv run python -m pytest tests/ -q`
Expected: all PASS.

- [ ] **Step 7: Lint, type-check, commit**

```bash
uv run ruff format scripts/py/cli/schemata.py scripts/py/cli/handle_network_score.py scripts/py/cli/main.py tests/scripts/py/cli/test_handle_network_score.py
uv run ruff check scripts/py/cli/schemata.py scripts/py/cli/handle_network_score.py scripts/py/cli/main.py tests/scripts/py/cli/test_handle_network_score.py
uv run ty check scripts/lib scripts/py
git add scripts/py/cli/schemata.py scripts/py/cli/handle_network_score.py scripts/py/cli/main.py tests/scripts/py/cli/test_handle_network_score.py
git commit -m "feat(camus): pch experiment network-score writes network_scores.csv"
```

---

### Smoke run (by the orchestrator, after all tasks)

```bash
PYTHONPATH=. PCH_SCRATCH=/private/tmp/claude-501/scr PCH_ASTRAL_XMX=4g uv run python -m scripts.py.cli.main experiment network-score experiments/camus_smoke/experiment_specification.yaml
```

Expected: 72 rows in `experiments/camus_smoke/inference_data/network_scores.csv`, no `failed`, runtimes recorded. Record the runtime distribution and the k = 0 vs k > 0 FN pattern in the PR body.
