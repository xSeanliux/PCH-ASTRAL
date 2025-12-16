import argparse
from pathlib import Path
from Bio import Phylo
from scripts.lib.quartet_scorer import QuartetScorer
from scripts.lib.getQuartets import get_quartets
from typing import Tuple, List
import subprocess
from uuid import uuid4
import os
import re
# Define the function that will process the input arguments and do something with them

def test_astral(tree_path, quartets):
    uid = str(uuid4())
    quartet_file = os.path.expanduser(f"~/scratch/test_quartet_{uid}")
    # java -jar ASTRAL/astral.5.7.8.jar -i $QUARTET_FILE -q $TREE 
    with open(quartet_file, "w") as f:
        for q, w in quartets:
            (a, b, c, d) = q
            f.write(f'(({a},{b}),({c},{d}));\n' * w)
    result = subprocess.run(
        "java -jar ASTRAL/astral.5.7.8.jar".split() + 
        [
            "-i", quartet_file,
            "-q", tree_path,
            "-t", "1"
        ],
        capture_output=True,
        text=True
    )
    result = result.stderr
    print(result)
    total_quartets = int(
        re.search(
            r'Number of quartet trees in the gene trees: (?P<total_quartets>\d+)', result
        ).group('total_quartets')
    )
    score = int(
        re.search(
            r'Final quartet score is: (?P<score>\d+)',
            result
        ).group('score')
    )
    return score, total_quartets

def test_quartets(
    tree_path,
    quartets: List[Tuple[Tuple, int]]
):
    tree = Phylo.read(tree_path, "newick")
    tree.root_with_outgroup(["HI"])
    buffer_quartets = get_buffer_quartets(tree)
    quartets = quartets + buffer_quartets
    qs_score, qs_total = test_qs(tree, quartets)
    astral_score, astral_total = test_astral(tree_path, quartets)    
    print(f"ASTRAL SCORE = {astral_score}, QS SCORE = {qs_score}")
    return astral_score == qs_score


    


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
        print(f"Tree loaded from: {tree_path}")
        # Example: Do something with the data file (perhaps parse it or load it)
        print(f"Data file: {data_path}")

        # Example: Output file handling
        # print(f"Output will be saved to: {output_path}")
        _, quartets = get_quartets(
            csv_path = data_path
        )
        all_quartets = list(quartets.items())
        r = test_astral(
            tree_path=tree_path,
            quartets = all_quartets
        )
        print(r)
                       

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
