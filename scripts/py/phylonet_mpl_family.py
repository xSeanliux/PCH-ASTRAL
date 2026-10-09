"""Convert PhyloNet InferNetwork_MPL's result file to a family CSV.

    python3 -m scripts.py.phylonet_mpl_family --result <name>.result \
        --output <name>.family.csv
"""

import argparse
import re
from pathlib import Path

import polars as pl

# `Inferred Network #<i>:`, the newick, `Total log probability: <x>`; best first.
NETWORK = re.compile(
    r"Inferred Network #\d+:\s*\n(.*;)\s*\nTotal log probability: (\S+)"
)
# Hybrid labels `#H<n>`; each appears twice, once per parent edge.
HYBRID = re.compile(r"#H\d+")


def phylonet_mpl_to_family(result_path: Path) -> pl.DataFrame:
    """The family of PhyloNet-MPL's networks, best first, newicks as written.

    `log_probability` is PhyloNet's log pseudo-likelihood; higher is better.

    :raises ValueError: if the result holds no network.
    """
    matches = NETWORK.findall(result_path.read_text())
    if not matches:
        raise ValueError(f"no network in {result_path}")
    return pl.DataFrame(
        {
            "edges_added": [len(set(HYBRID.findall(n))) for n, _ in matches],
            "network_newick": [n for n, _ in matches],
            "log_probability": [float(x) for _, x in matches],
            "is_best": [i == 0 for i in range(len(matches))],
        },
        schema={
            "edges_added": pl.Int64,
            "network_newick": pl.String,
            "log_probability": pl.Float64,
            "is_best": pl.Boolean,
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    phylonet_mpl_to_family(args.result).write_csv(args.output)
