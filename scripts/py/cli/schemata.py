import polars as pl
from polars import Int64, String, Float64, Boolean


CONFIG_REGISTRY_SCHEMA = pl.Schema(
    {
        "poly_level": String,
        "character_count": Int64,
        "min_tree_height": Int64,
        "homoplasy_factor": Float64,
        "do_borrowing": Boolean,
        "path": String,
    }
)

NETWORK_REGISTRY_SCHEMA = pl.Schema(
    {
        "horizontal_edges": Int64,
        "model_tree": Int64,
        "path": String,
    }
)
