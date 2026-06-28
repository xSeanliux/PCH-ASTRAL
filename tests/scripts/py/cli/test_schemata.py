from scripts.lib.inference.inference import InferenceResult, TreeInferenceMethod, RunStatus
from scripts.py.cli.schemata import INFERENCE_REGISTRY_SCHEMA


def test_row_keys_equal_schema_columns():
    row = InferenceResult(
        dataset_id="d1",
        tree_inference_method=TreeInferenceMethod.GA,
        config_hash="abc",
        method_config_json="{}",
        point_estimate_newick="(a,b);",
        runtime_seconds=1.0,
        status=RunStatus.OK,
        ran_at="2026-06-24T00:00:00",
    ).to_registry_row()
    assert list(row.keys()) == INFERENCE_REGISTRY_SCHEMA.names()
