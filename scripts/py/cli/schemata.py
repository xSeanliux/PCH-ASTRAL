import polars as pl
from polars import Int64, String, Float64, Boolean

CONFIG_KEY = {
    "poly_level": String,
    "character_count": Int64,
    "min_tree_height": Int64,
    "homoplasy_factor": Float64,
}

MODEL_NETWORK_KEY = {
    "horizontal_edges": Int64,
    "model_tree": Int64,
}

CONFIG_REGISTRY_SCHEMA = pl.Schema(
    {
        **CONFIG_KEY,
        "do_borrowing": Boolean,
        "path": String,
    }
)

MODEL_GRAPH_REGISTRY = pl.Schema(
    {
        **MODEL_NETWORK_KEY,
        "path": String,
    }
)

SIMULATED_DATA_REGISTRY_SCHEMA = pl.Schema(
    {**CONFIG_KEY, **MODEL_NETWORK_KEY, "replica": Int64, "path": String},
)

INFERENCE_REGISTRY_SCHEMA = pl.Schema(
    {
        "dataset_id": String,  # the input CSV path — the generic identity
        "method": String,
        "config_hash": String,
        "method_config_json": String,
        "runtime_seconds": Float64,
        "point_estimate_newick": String,
        "tree_set_path": String,
        "consensus_method": String,
        "status": String,
        "ran_at": String,
        "log_path": String,
    }
)

# FN/FP live here (from `pch experiment score`), joined back on dataset_id/method/config_hash.
SCORES_SCHEMA = pl.Schema(
    {
        "dataset_id": String,
        "method": String,
        "config_hash": String,
        "fn_rate": Float64,
        "fp_rate": Float64,
    }
)
