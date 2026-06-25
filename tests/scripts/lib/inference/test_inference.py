import polars as pl
from scripts.lib.inference.inference import InferenceResult, TreeInferenceMethod
from scripts.lib.types import Polymorphism
from scripts.py.cli.schemata import INFERENCE_REGISTRY_SCHEMA


def _result() -> InferenceResult:
    # Regression: a bare construction crashed when metadata used `= {}`.
    return InferenceResult(
        dataset_id="d1",
        tree_inference_method=TreeInferenceMethod.PCH_ASTRAL3,
        config_hash="abc",
        method_config_json="{}",
        point_estimate_newick="(a,b);",
        runtime_seconds=1.5,
        status="ok",
        ran_at="2026-06-24T00:00:00",
    )


def test_construct_no_shared_mutable_default():
    a, b = _result(), _result()
    a.metadata["x"] = "1"
    assert b.metadata == {}


def test_registry_row_keys_match_schema():
    row = _result().to_registry_row()
    assert list(row.keys()) == INFERENCE_REGISTRY_SCHEMA.names()


def test_row_builds_dataframe():
    full = InferenceResult(
        dataset_id="d1",
        tree_inference_method=TreeInferenceMethod.MP,
        config_hash="abc",
        method_config_json="{}",
        point_estimate_newick="(a,b);",
        runtime_seconds=1.5,
        status="ok",
        ran_at="2026-06-24T00:00:00",
        poly=Polymorphism.HIGH,
        homoplasy_factor=0.1,
        tree_height=5,
        n_chars=100,
        ret_edges=2,
        target_tree=3,
        replica=1,
    )
    df = pl.DataFrame([full.to_registry_row()], schema=INFERENCE_REGISTRY_SCHEMA)
    assert df.height == 1
    assert df["poly_level"][0] == "high"
