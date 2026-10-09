"""Convert SNaQ's .networks plus the rerooted best .net to a family CSV.

    python3 -m scripts.py.snaq_family --networks <name>.networks --best <name>.net \
        --output <name>.family.csv
"""

import argparse
import re
from pathlib import Path

import polars as pl

# `<newick>;, with -loglik <x>`; SNaQ's bug/problem notes don't match and are skipped.
NETWORK_LINE = re.compile(r"^(.*;), with -loglik (\S+)")
# Hybrid labels `#H<n>`; each appears twice, once per parent edge.
HYBRID = re.compile(r"#H\d+")


def snaq_to_family(networks_path: Path, best_path: Path) -> pl.DataFrame:
    """The family of SNaQ's networks, best first, as the .net point estimate.

    SNaQ writes no .networks when the best is a tree; the family is then the .net
    alone, with null `neg_loglik`. SNaQ's -loglik -1 (failed optimization) is null.
    """
    best = best_path.read_text().strip()
    lines = networks_path.read_text().splitlines() if networks_path.exists() else []
    matches = [m for line in lines if (m := NETWORK_LINE.match(line))]
    newicks = [best] + [m[1] for m in matches[1:]]
    neg_logliks = [float(m[2]) for m in matches] or [None]
    return pl.DataFrame(
        {
            "edges_added": [len(set(HYBRID.findall(n))) for n in newicks],
            "network_newick": newicks,
            "neg_loglik": [None if x == -1 else x for x in neg_logliks],
            "is_best": [i == 0 for i in range(len(newicks))],
        },
        schema={
            "edges_added": pl.Int64,
            "network_newick": pl.String,
            "neg_loglik": pl.Float64,
            "is_best": pl.Boolean,
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--networks", type=Path, required=True)
    parser.add_argument("--best", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    snaq_to_family(args.networks, args.best).write_csv(args.output)
