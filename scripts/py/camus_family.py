"""Convert CAMUS's network CSV to a family CSV (NETWORK_FAMILY_SCHEMA plus extras).

python3 -m scripts.py.camus_family --input <name>.csv --output <name>.family.csv
"""

import argparse
from pathlib import Path

import polars as pl

# CAMUS's header -> family columns; the newick is kept as written.
CAMUS_TO_COLUMN = {
    "Number of Branches": "edges_added",
    "Extended Newick": "network_newick",
    "Quartet Satisfied Percent": "quartet_satisfied_percent",
}


def camus_to_family(path: Path) -> pl.DataFrame:
    """The family of CAMUS's network CSV at `path`, one row per network."""
    df = pl.read_csv(path, columns=list(CAMUS_TO_COLUMN)).rename(CAMUS_TO_COLUMN)
    return df.select(CAMUS_TO_COLUMN.values())  # required columns first


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    camus_to_family(args.input).write_csv(args.output)
