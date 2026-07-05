# PR 1 — Decouple inference from the simulation

## Why
`api.infer` is already the generic unit (`csv → InferenceResult`), but `handle_inference` bolts simulation-specific things on top: it **stamps sim join keys** (poly/homoplasy/…) into every registry row and computes **FN/FP** against the model truth. That makes `inference_registry.csv` *simulation-shaped* and "condition" a first-class idea — real datasets (Indo-European) don't fit. This PR makes inference **dataset-source-agnostic**: one CSV → one generic entry keyed by its path. Sim metadata and scoring become a **join** and a **separate step**.

Local-only; no SLURM (that's PR 2).

## The generic unit
`infer(input_csv, output_dir, method, config) → InferenceResult`, where the entry is:

```
dataset_id, method, config_hash, method_config_json,
runtime_seconds, point_estimate_newick, tree_set_path,
consensus_method, status, ran_at, log_path
```

**Dropped from the entry:** `poly_level, character_count, min_tree_height, homoplasy_factor, horizontal_edges, model_tree, replica, fn_rate, fp_rate`. Runs identically on a sim CSV or a real one.

## Key decisions

### D1 — `dataset_id = the input path` (not the stem)
Sim stems repeat across conditions (`sim_0_1_1.csv` lives in both `high_0.1_4_320/` and `low_0.1_4_320/`) — which is *why* the registry currently keys on the full sim keys. The generic identity is the **input CSV path string** (as passed / as it appears in `simulated_data_registry.path`): unique for sim's `condition/stem` and for real files, and joinable.
- Dedup/resume key becomes `(dataset_id, method, config_hash)` → `DATASET_KEY_COLUMNS = ["dataset_id"]`.
- Human display stays `Path(dataset_id).name`.

### D2 — sim keys are a join, not columns
Drop the seven sim-key columns from `inference_registry.csv`. Analysis rejoins them:
```python
inference.join(simulated_data_registry, left_on="dataset_id", right_on="path")
```
Trade-off: analysis gains one join; the inference registry stops being sim-locked. (This deliberately reverses the M1 "self-contained inline keys" choice, to generalize.)

### D3 — scoring is a separate step: `pch experiment score`
FN/FP needs the model truth (`model_graph_registry`), which real data lacks. Move scoring out of `handle_inference` into `pch experiment score EXPERIMENT`: read the inference entries, join `dataset_id → simulated_data_registry` to recover `model_tree`/`horizontal_edges`, resolve the reference, score each point estimate, and write a **scores table** (`dataset_id, method, config_hash, fn_rate, fp_rate`). Analysis joins it in. Inference stays pure; real data skips scoring (or uses `pch score` per dataset with a user-supplied reference).
- *Alternative considered:* keep scoring in the `inference` pass but writing to a separate scores shard (one command, still-generic entry). Rejected for clean separation, but it's the lower-friction fallback if the extra step annoys.

## Changes
- `inference.py` — `InferenceResult` sheds the sim-key + fn/fp fields; `dataset_id = path`; slim `RegistryRow`/`to_registry_row`.
- `schemata.py` — `INFERENCE_REGISTRY_SCHEMA` = the generic columns; new `SCORES_SCHEMA`.
- `registry.py` — `DATASET_KEY_COLUMNS = ["dataset_id"]`.
- `scheduler.py` — `dataset_key(row) = (row["dataset_id"],)`; gate/resume logic unchanged.
- `handle_inference.py` — stop stamping sim keys + scoring; the loop runs `infer` → write entry. (Still reads the dataset list from `simulated_data_registry`, but only its `path`.)
- new `handle_score.py` + `pch experiment score`.
- `main.py` — `pch infer` already generic; update the `--json` row shape.
- docs — RUNNING_INFERENCE / CLI / ARCHITECTURE: the entry is generic; sim keys + fn/fp are joins/a separate table.
- tests — registry/scheduler key on `dataset_id`; a scoring-step test; a real-CSV entry test asserting no sim keys.

## Analysis after this PR (three lean tables, joined on dataset_id)
`inference_registry` (trees) ⨝ `simulated_data_registry` (sim keys, on `path`) ⨝ `scores` (fn/fp). Each join is one line on `dataset_id`/`path`.

## Compatibility
Old `inference_registry.csv` (inline sim keys) is stale-shaped; it's per-experiment and regenerated, so no live migration — just note it.

## Out of scope
SLURM (PR 2); wASTRAL/TREE-QMC runners (M4).
