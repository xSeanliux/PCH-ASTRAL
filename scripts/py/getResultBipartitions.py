from scripts.lib.getBipartitions import trees_to_newick
import argparse


def parse_arguments():
    # Initialize the ArgumentParser object
    parser = argparse.ArgumentParser(description="Input: please input ")

    # Add argument for input file
    parser.add_argument('-f', '--folder', required=True, help="Path to the input file path storing trees")
    parser.add_argument('-n', '--name', required=False, default="", help="Path to the input file name storing tree")

    parser.add_argument('-m', '--mp4', action='store_true', help="Enable option M, will get file under $FOLDER/MP4/trees/$FILENAME.trees")
    parser.add_argument('-g', '--ga', action='store_true', help="Enable option G, will get file under $FOLDER/GA/trees1/$FILENAME.trees")
    parser.add_argument('-c', '--covarion', action='store_true', help="Enable option C, will get file under $FOLDER/COV/trees/$FILENAME.tree")

    # Add argument for format with a default value of 'newick'

    # Parse the arguments
    args = parser.parse_args()

    # Return the parsed arguments
    return args

def get_and_print_trees(
    trees_path: str,
    schema: str
):
    trees = trees_to_newick(
        trees_path=trees_path,
        schema=schema,
    )
    for t in trees:
        print(t)

def main():
    # Parse the command-line arguments
    args = parse_arguments()
    if args.mp4:
        get_and_print_trees(
            trees_path=f"{args.folder}/MP4/trees/{args.name}.trees",
            schema="nexus",
        )
    if args.ga:
        get_and_print_trees(
            trees_path=f"{args.folder}/GA/trees1/{args.name}.trees",
            schema="nexus",
        )
    if args.covarion:
        get_and_print_trees(
            trees_path=f"{args.folder}/COV/trees/{args.name}.tree",
            schema="newick",
        )

    # print(f"Got {len(trees)} trees")

if __name__ == "__main__":
    main()