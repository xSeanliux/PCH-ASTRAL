from scripts.lib.utils import trees_to_newick
from Bio.Phylo import parse
import argparse


def parse_arguments():
    # Initialize the ArgumentParser object
    parser = argparse.ArgumentParser(description="Parse input file and format")

    # Add argument for input file
    parser.add_argument(
        "-i", "--input", required=True, help="Path to the input file storing trees"
    )

    # Add argument for format with a default value of 'newick'
    parser.add_argument(
        "-f",
        "--format",
        default="newick",
        choices=["newick", "nexus"],
        help="Format of the file (default: 'newick'). Choices are: 'newick' or 'nexus'",
    )

    # Parse the arguments
    args = parser.parse_args()

    # Return the parsed arguments
    return args


def main():
    # Parse the command-line arguments
    args = parse_arguments()

    trees = parse(file=args.input, format=args.format)
    newick = trees_to_newick(trees=trees)
    for t in newick:
        print(t)
    # print(f"Got {len(trees)} trees")


if __name__ == "__main__":
    main()
