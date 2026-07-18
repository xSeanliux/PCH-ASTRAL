from scripts.lib.pch import (
    PCH_W,
    print_quartets_for_astral3,
    print_quartets_for_wastral,
)
from scripts.lib.types import Dataset

import argparse
from pathlib import Path
from enum import StrEnum


class OutputMode(StrEnum):
    ASTRAL3 = "astral3"
    WASTRAL = "wastral"
    W_TREE_QMC = "w_tree_qmc"


def main():
    # Initialize argument parser
    parser = argparse.ArgumentParser(
        description="Prints quartets based on the input CSV and quartet generation method PCH-W"
    )

    # Add '-i' argument for a string input
    parser.add_argument("-i", type=str, required=True, help="Path to the input CSV.")
    parser.add_argument("--format", type=str, required=False, default="astral3")

    # WASTER mode
    parser.add_argument(
        "-w",
        "--waster",
        action="store_true",
        help="Enables WASTER mode. It will instead print unique quartetss to STDOUT and quartet weights to STDERR.",
    )

    # Parse arguments
    args = parser.parse_args()

    # Print out the results
    dataset = Dataset.from_path(Path(args.i))
    quartets = PCH_W.get_quartets(dataset)
    if args.waster:
        print_quartets_for_wastral(quartets)
    else:
        print_quartets_for_astral3(quartets)


if __name__ == "__main__":
    main()
