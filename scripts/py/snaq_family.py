"""Convert SNaQ's .networks plus the chosen, rerooted .net to a family CSV.

    python3 -m scripts.py.snaq_family --networks <name>.networks --best <name>.net \
        --choice <name>.choice --output <name>.family.csv
"""

import argparse
import re
from pathlib import Path

import polars as pl

# `<newick>;, with -loglik <x>`; SNaQ's bug/problem notes don't match and are skipped.
NETWORK_LINE = re.compile(r"^(.*;), with -loglik (\S+)")
# Hybrid labels `#H<n>`; each appears twice, once per parent edge.
HYBRID = re.compile(r"#H\d+")


def snaq_to_family(
    networks_path: Path, best_path: Path, choice_path: Path
) -> pl.DataFrame:
    """The family of SNaQ's networks in .networks order, the chosen row as the .net.

    `run_snaq.jl` writes `.choice` = the 0-based row consistent with the outgroup, or
    `none` (no .net; no row `is_best`). Other rows keep SNaQ's newick. SNaQ writes no
    .networks when the best is a tree; the family is then the .net alone, with null
    `neg_loglik`. SNaQ's -loglik -1 (failed optimization) is null.
    """
    choice = choice_path.read_text().strip()
    lines = networks_path.read_text().splitlines() if networks_path.exists() else []
    matches = [m for line in lines if (m := NETWORK_LINE.match(line))]
    newicks = [m[1] for m in matches] or [best_path.read_text().strip()]
    index = None if choice == "none" else int(choice)
    if index is not None:
        newicks[index] = best_path.read_text().strip()
    neg_logliks = [float(m[2]) for m in matches] or [None]
    return pl.DataFrame(
        {
            "edges_added": [len(set(HYBRID.findall(n))) for n in newicks],
            "network_newick": newicks,
            "is_best": [i == index for i in range(len(newicks))],
            "neg_loglik": [None if x == -1 else x for x in neg_logliks],
        },
        schema={
            "edges_added": pl.Int64,
            "network_newick": pl.String,
            "is_best": pl.Boolean,
            "neg_loglik": pl.Float64,
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--networks", type=Path, required=True)
    parser.add_argument("--best", type=Path, required=True)
    parser.add_argument("--choice", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    snaq_to_family(args.networks, args.best, args.choice).write_csv(args.output)
