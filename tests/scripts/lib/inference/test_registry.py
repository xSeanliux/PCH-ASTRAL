import json
from pathlib import Path

import polars as pl

from scripts.lib.inference.inference import (
    InferenceResult,
    TreeInferenceMethod,
    RunStatus,
)
from scripts.lib.inference.registry import (
    _iter_shard_rows,
    compact,
    finalize_manifest,
    init_manifest,
    run_key,
    write_result,
)


def _result(
    ran_at: str, *, dataset_id: str = "ds1", config_hash: str = "abc"
) -> InferenceResult:
    return InferenceResult(
        dataset_id=dataset_id,
        tree_inference_method=TreeInferenceMethod.MP,
        config_hash=config_hash,
        method_config_json="{}",
        point_estimate_newick="(a,b);",
        runtime_seconds=1.0,
        status=RunStatus.OK,
        ran_at=ran_at,
    )


def test_run_key_is_human_readable():
    k = run_key(_result("2026-01-01T00:00:00+00:00").to_registry_row())
    assert "ds1" in k and "mp" in k and "abc" in k  # readable, not an opaque hash


def test_write_result_appends_to_shard(tmp_path: Path):
    write_result(_result("2026-01-01T00:00:00+00:00"), tmp_path)
    write_result(_result("2026-01-02T00:00:00+00:00", dataset_id="ds2"), tmp_path)
    shards = list((tmp_path / "inference_data" / "shards").glob("*.jsonl"))
    assert len(shards) == 1  # one shard per process
    assert len(shards[0].read_text().splitlines()) == 2


def test_compact_dedups_keeping_newest_ran_at(tmp_path: Path):
    write_result(_result("2026-01-01T00:00:00+00:00"), tmp_path)
    write_result(_result("2026-01-03T00:00:00+00:00"), tmp_path)  # same key, newer
    write_result(
        _result("2026-01-02T00:00:00+00:00", dataset_id="ds2"), tmp_path
    )  # distinct
    df = pl.read_csv(compact(tmp_path))
    assert df.height == 2
    assert df.filter(pl.col("dataset_id") == "ds1")["ran_at"].to_list() == [
        "2026-01-03T00:00:00+00:00"
    ]


def test_different_config_hash_distinct(tmp_path: Path):
    write_result(_result("2026-01-01T00:00:00+00:00", config_hash="x"), tmp_path)
    write_result(_result("2026-01-01T00:00:00+00:00", config_hash="y"), tmp_path)
    assert pl.read_csv(compact(tmp_path)).height == 2


def test_compact_cleans_up_shards(tmp_path: Path):
    write_result(_result("2026-01-01T00:00:00+00:00"), tmp_path)
    compact(tmp_path)
    shards = tmp_path / "inference_data" / "shards"
    assert not shards.exists() or not list(shards.glob("*.jsonl"))


def test_compact_accumulates_across_cleanups(tmp_path: Path):
    # Shards are deleted after each compact; the registry must still accumulate.
    write_result(_result("2026-01-01T00:00:00+00:00", dataset_id="ds1"), tmp_path)
    compact(tmp_path)
    write_result(_result("2026-01-02T00:00:00+00:00", dataset_id="ds2"), tmp_path)
    df = pl.read_csv(compact(tmp_path))
    assert df.height == 2  # ds1 from prior registry + ds2 from new shard


def _write_shard(tmp_path: Path, text: str) -> None:
    shards = tmp_path / "inference_data" / "shards"
    shards.mkdir(parents=True, exist_ok=True)
    (shards / "job1.jsonl").write_text(text)


def test_iter_shard_rows_skips_torn_tail(tmp_path: Path):
    good1 = json.dumps(_result("2026-01-01T00:00:00+00:00").to_registry_row())
    good2 = json.dumps(
        _result("2026-01-02T00:00:00+00:00", dataset_id="ds2").to_registry_row()
    )
    # 3rd line is a truncated JSON object — a killed writer's torn tail.
    _write_shard(tmp_path, f"{good1}\n{good2}\n{good2[:20]}")
    rows = list(_iter_shard_rows(tmp_path))
    assert len(rows) == 2
    assert [r["dataset_id"] for r in rows] == ["ds1", "ds2"]


def test_compact_drops_torn_line_and_merges_prior(tmp_path: Path):
    # Seed a prior registry row (ds0), then a shard with 2 valid + 1 torn line.
    write_result(_result("2026-01-01T00:00:00+00:00", dataset_id="ds0"), tmp_path)
    compact(tmp_path)  # ds0 now lives in inference_registry.csv, shard cleaned

    good1 = json.dumps(
        _result("2026-01-02T00:00:00+00:00", dataset_id="ds1").to_registry_row()
    )
    good2 = json.dumps(
        _result("2026-01-03T00:00:00+00:00", dataset_id="ds2").to_registry_row()
    )
    _write_shard(tmp_path, f"{good1}\n{good2}\n{good2[:15]}")

    df = pl.read_csv(compact(tmp_path))
    assert sorted(df["dataset_id"].to_list()) == [
        "ds0",
        "ds1",
        "ds2",
    ]  # torn dropped, prior kept


def test_manifest_roundtrip(tmp_path: Path):
    init_manifest(tmp_path, ["mp"])
    finalize_manifest(tmp_path, {"ok": 5, "skipped": 0, "blocked": 0, "failed": 0})
    m = json.loads((tmp_path / "inference_data" / "manifest.json").read_text())
    assert m["methods"] == ["mp"]
    assert m["tally"]["ok"] == 5
    assert m["created_at"] and m["completed_at"]


def test_manifest_preserves_created_at_on_rerun(tmp_path: Path):
    init_manifest(tmp_path, ["mp"])
    first = json.loads((tmp_path / "inference_data" / "manifest.json").read_text())
    init_manifest(tmp_path, ["mp"])  # re-run
    second = json.loads((tmp_path / "inference_data" / "manifest.json").read_text())
    assert second["created_at"] == first["created_at"]


def test_canonical_path_normalizes():
    import os

    from scripts.lib.inference.registry import canonical_path

    assert canonical_path("a/b/../x.csv") == os.path.join("a", "x.csv")
    assert canonical_path("a//x.csv") == os.path.join("a", "x.csv")
    assert canonical_path("dir/x.csv/") == os.path.join("dir", "x.csv")
    assert canonical_path("~/x.csv") == os.path.join(os.path.expanduser("~"), "x.csv")
