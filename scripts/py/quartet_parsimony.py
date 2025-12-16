from scripts.lib.getQuartets import get_quartets
from scripts.lib.utils import get_values
from pathlib import Path
from uuid import uuid4
from jinja2 import Environment, FileSystemLoader
import argparse
import os
from tqdm import tqdm
import time


environment = Environment(loader=FileSystemLoader(f"{os.getenv('TALLIS')}/QuartetMethods/scripts/jinja"))
template = environment.get_template("parsimony_template.jinja")

def parse_args():
    # Create an argument parser
    parser = argparse.ArgumentParser(description="Parse CSV input and output options")

    # Required input argument
    parser.add_argument(
        '-i', '--input',
        type=str,
        required=True,
        help="Path to the input CSV file"
    )

    # Optional output argument with a default value
    parser.add_argument(
        '-o', '--output',
        type=str,
        required=True,
        help="Path to the output file"
    )

    parser.add_argument(
        '-n', '--name',
        type=str,
        required=True,
        help="PAUP* outfile name"
    )
    # Flag for enabling filtering
    parser.add_argument(
        '-f', '--filter',
        action='store_true',
        help="Enable filtering"
    )

    # Optional limit argument (integer)
    parser.add_argument(
        '-l', '--limit',
        type=int,
        default=2,
        help="Limit for filtering (optional), only quartets with weight (aka frequency) strictly larger than this will be kept. Used to keep file sizes down."
    )

    parser.add_argument(
        '-m', '--mode',
        type=int,
        default=1,
        help="quartet generation mode (default 1, don't change if you don't know)"
    )

    # Parse arguments
    args = parser.parse_args()

    return args

def get_character(q, name_id):
    s = ["?"] * len(name_id)
    s[name_id[q[0]]] = s[name_id[q[1]]] = '0'
    s[name_id[q[2]]] = s[name_id[q[3]]] = '1'
    return ''.join(s)


if __name__ == '__main__':
    args = parse_args()
    """
    Takes a csv path and a mode (like all other methods), 
    and will print quartets in NEXUS format. In particular, if ab|cd is a quartet with weight W, 
    then there will be a parsimony character A such that it has weight W and 
    A(a) = A(b) = 0,
    A(c) = A(d) = 1,
    A(x) = ? for all other taxa.
    """
    csv_path = args.input
    names, _ = get_values(csv_path) # list of all taxa names
    name_id = { # assign each name a numerical ID
        n: i for i, n in enumerate(names)
    }
    q_start_time = time.time()
    _, quartets = get_quartets(
        csv_path = args.input,
        mode = args.mode,
        do_filter=args.filter,
        filter_lim=args.limit,
    )
    q_end_time = time.time()
    if args.filter:
        print(f"Filtering enabled. Will remove all quartets whose frequency is <= {args.limit}.")
    else:
        print(f"Filtering disabled. Will keep all generated quartets.")
    print(f"Quartet generation finished in {q_end_time - q_start_time}s.")
    print(f"Found {len(quartets)} unique quartets.")
    weights = {}
    quartets_list = []
    for (q, w) in tqdm(quartets.items()):
        quartets_list.append(get_character(q, name_id))
        weights.setdefault(w, [])
        weights[w].append(len(quartets_list))

    for w, wlist in weights.items():
        weights[w] = ' '.join(map(str, wlist))

    # print(quartets_list)
    hash = str(uuid4())
    content = template.render(
        names=names,
        quartets=quartets_list,
        weights=weights,
        outfilename=args.name,
    )
    with open(Path(args.output), "w") as fout:
        fout.write(content)
    # names: list of taxa names
    # quartets: list of strings of length |quartet|, one for each quaret, with 0s on one side, 1s on the other, and ?s elsewhere
    # weights: dict of (weight, [indices of quartets with that weight])