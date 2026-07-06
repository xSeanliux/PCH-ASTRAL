import polars as pl
from scripts.lib.inference.inference import InferenceResult, TreeInferenceMethod, RunStatus
from scripts.py.cli.schemata import INFERENCE_REGISTRY_SCHEMA


def _result() -> InferenceResult:
    return InferenceResult(
        dataset_id="d1",
        tree_inference_method=TreeInferenceMethod.PCH_ASTRAL3,
        config_hash="abc",
        method_config_json="{}",
        point_estimate_newick="(a,b);",
        runtime_seconds=1.5,
        status=RunStatus.OK,
        ran_at="2026-06-24T00:00:00",
    )


def test_registry_row_keys_match_schema():
    row = _result().to_registry_row()
    assert list(row.keys()) == INFERENCE_REGISTRY_SCHEMA.names()


def test_row_builds_dataframe():
    full = InferenceResult(
        dataset_id="/data/sim_0_1_1.csv",
        tree_inference_method=TreeInferenceMethod.MP,
        config_hash="abc",
        method_config_json="{}",
        point_estimate_newick="(a,b);",
        runtime_seconds=1.5,
        status=RunStatus.OK,
        ran_at="2026-06-24T00:00:00",
    )
    df = pl.DataFrame([full.to_registry_row()], schema=INFERENCE_REGISTRY_SCHEMA)
    assert df.height == 1
    assert df["dataset_id"][0] == "/data/sim_0_1_1.csv"
