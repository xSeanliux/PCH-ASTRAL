import argparse
from pathlib import Path
from Bio import Phylo
from scripts.lib.quartet_scorer import QuartetScorer
from scripts.lib.getQuartets import get_quartets

# Define the function that will process the input arguments and do something with them
def main():
    # Set up the argument parser
    parser = argparse.ArgumentParser(description="Process tree, data, and output paths")
    
    # Add command-line arguments
    parser.add_argument('-t', '--tree', type=str, required=True, help='Path to the tree file (required)')
    parser.add_argument('-d', '--data', type=str, required=True, help='Path to the data file (required)')
    # parser.add_argument('-o', '--output', type=str, required=True, help='Path for the output file (required)')

    # Parse the arguments
    args = parser.parse_args()

    # Convert paths to Path objects for easier manipulation
    tree_path = Path(args.tree)
    data_path = Path(args.data)
    # output_path = Path(args.output)

    # Example usage of Bio.Phylo and Path (could be expanded depending on your task)
    try:
        # Assuming the tree file is a Newick format, you could load the tree like this
        tree = Phylo.read(tree_path, 'newick')
        print(f"Tree loaded from: {tree_path}")
        # Example: Do something with the data file (perhaps parse it or load it)
        print(f"Data file: {data_path}")
        _, quartets = get_quartets(
            csv_path = data_path,
            mode = 11
        )
        # 11 for EVANS-ALL-K
        # Example: Output file handling
        # print(f"Output will be saved to: {output_path}")

        scorer = QuartetScorer(tree)
        score = 0
        total_quartets = 0
        for q, w in quartets.items():
            total_quartets += w
            if scorer.test_quartet(q):
                score += w
        print(f"{score} / {total_quartets} = {score / total_quartets} quartets satisfied.")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
