from scripts.lib.getQuartets import print_quartets, get_quartets
from scripts.lib.utils import eprint
import optparse

import argparse

def main():
    # Initialize argument parser
    parser = argparse.ArgumentParser(description="Prints quartets based on the input CSV and quartet generation method (default 1)")
    
    # Add '-i' argument for a string input
    parser.add_argument('-i', type=str, required=True, help="Path to the input CSV.")
    
    # Add '-q' argument for an integer input, with a default value of 1 
    parser.add_argument('-q', type=int, default=10, help="Quartet generation strategy. Default 1 is EVANS-ALL. Others are kept but not used")

    # WASTER mode
    parser.add_argument('-w', '--waster', action='store_true', help="Enables WASTER mode. It will instead print unique quartetss to STDOUT and quartet weights to STDERR.")

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
    
    # Parse arguments
    args = parser.parse_args()
    
    # Print out the results
    if args.waster:
        _, quartets = get_quartets(
            csv_path = args.i,
            mode = args.q,
            do_filter=args.filter,
            filter_lim=args.limit,
        )
        for (a, b, c, d), C in quartets.items():
            print(f'(({a},{b}),({c},{d}));')  
            eprint(C)
    else:
        print_quartets(
            csv_path=args.i,
            mode=args.q,
            do_filter=args.filter,
            filter_lim=args.limit,
        )

if __name__ == '__main__':
    main()