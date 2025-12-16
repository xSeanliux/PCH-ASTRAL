from jinja2 import Environment, FileSystemLoader
import argparse
from pathlib import Path
from uuid import uuid4
import os
from tqdm import tqdm
import time

environment = Environment(loader=FileSystemLoader("scripts/jinja"))
template = environment.get_template("sd_partemplate.jinja")

def parse_args():
    # Create an argument parser
    parser = argparse.ArgumentParser(description="Parse CSV input and output options")

    # Required input argument
    parser.add_argument(
        '-i', '--input',
        type=str,
        required=True,
        help="Path to the input NEXUS file"
    )

    # Required output argument with a default value
    parser.add_argument(
        '-o', '--paroutput',
        type=str,
        required=True,
        help="Path to the output PAR file"
    )
    
    parser.add_argument(
        '-d', '--treefiledir',
        type=str,
        required=True,
        help="Directory to the output tree"
    )

    parser.add_argument(
        '-n', '--treefilename',
        type=str,
        required=True,
        help="Filename of the output tree. Does not include the parent paths nor extension."
    )


    args = parser.parse_args()

    return args

if __name__ == '__main__':
    args = parse_args()
    hash = str(uuid4())
    content = template.render(
        nexus_file_name = args.input,
        output_file_name = args.treefilename,
        output_path_name = args.treefiledir,
    )
    with open(Path(args.paroutput), "w") as fout:
        fout.write(content)