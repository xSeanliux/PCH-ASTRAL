import numpy as np 
import pandas as pd
import os
import glob
import json
from tqdm import tqdm
from pathlib import Path
from Bio import Phylo
import treeswift
from io import StringIO
import sys

def nexus_to_newick(trees_path): # expects a path to a .trees file under GA/ in NEXUS format. Reads all trees.
    try:
        with open(trees_path, "r") as f:
            data = Phylo.NexusIO.parse(f)
            output = StringIO()
            written_trees = Phylo.NewickIO.write(data, output, plain=True) # plain = True removes branch lengths which aren't important
            newick_trees = output.getvalue().split('\n')[:-1] # there's a newline following the last tree
            def resolve_tree(newick_tree):
                tree = treeswift.read_tree(newick_tree, schema='newick')
                #print(newick_tree)
                tree.resolve_polytomies()
                return tree.newick()
            trees_resolved = list(map(
            resolve_tree 
            , newick_trees))
            output.close()
            return trees_resolved
    except Exception:
        print(f"❌ Failed when trying to get bipartitions from {trees_path}: perhaps file does not exist?")
        exit(1)

def trees_to_newick(
    trees_path: str,
    schema: str = "nexus",
    ): 
    """
    This function reads in a list of trees in a specified format (schema) (newick/nexus), resolves each tree arbitrarily, and returns a list of newick strings.
    """
    # expects a path to a .trees file under GA/ in NEXUS format. Reads all trees.
    output = StringIO()
    Phylo.convert(trees_path, schema, output, "newick") # convert all trees in trees_path to newick format and store them in output buffer
    newick_trees = output.getvalue().split('\n')[:-1] # there's a newline following the last tree
    def resolve_tree(newick_tree):
        tree = treeswift.read_tree(newick_tree, schema='newick')
        #print(newick_tree)
        tree.resolve_polytomies()
        return tree.newick()
    trees_resolved = list(map(
    resolve_tree 
    , newick_trees))
    output.close()
    return trees_resolved

def get_bipartitions(folder : str,
                    morph   : str, 
                    f       : str, 
                    poly    : str, 
                    treeidx : int,
                    replica : int,
                    mode    : int,
                    suffix  : str = ""): # suffix: e.g. -morechrs, -nohp, etc.
    '''
    Mode 
    1, 2    No bipartitions 
    3       GA       
    4       MP4
    5       GA + MP4
    '''
    # print("the mode is", mode, "dir = ", os.getcwd())
    if mode <= 2:
        return
    bipartitions = []
    morph_folder = 'outputs_with_morph' if morph == "true" else 'outputs_no_morph'
    inference_folder = f"./OneMostProb/{folder}/{morph_folder}/inference_outputs-{f}{suffix}/{poly}_noborrowing"
    if mode == 3 or mode == 5: # GA
        bipartitions += nexus_to_newick(f"{inference_folder}/GA/trees1/{poly}_{treeidx}_{replica}.trees")
    if mode == 4 or mode == 5: # MP4
        bipartitions += nexus_to_newick(f"{inference_folder}/MP4/trees/{poly}_{treeidx}_{replica}.trees")

    print('\n'.join(bipartitions), end="")

def get_bipartitions_new(
    tree_output: str, 
    id: str,
    mode: int, 
):
    if mode <= 2:
        return 
    bipartitions = []
    if mode == 3 or mode == 5:
        bipartitions.extend(nexus_to_newick(f"{tree_output}/GA/trees1/{id}.trees"))
    if mode == 4 or mode == 5:
        bipartitions.extend(nexus_to_newick(f"{tree_output}/MP4/trees/{id}.trees"))
    
    print('\n'.join(bipartitions), end="")


def get_bipartitions_specific(mode    : int,
                    output_folder: str,
                    filename: str = ""):
    '''
    Mode 
    1, 2    No bipartitions 
    3       GA       
    4       MP4
    5       GA + MP4
    '''
    # print("the mode is", mode, "dir = ", os.getcwd())
    if mode <= 2:
        return
    bipartitions = []
    if mode == 3 or mode == 5: # GA
        bipartitions += nexus_to_newick(f"./OneMostProb/{output_folder}/GA/trees1/{filename}.trees")
    if mode == 4 or mode == 5: # MP4
        bipartitions += nexus_to_newick(f"./OneMostProb/{output_folder}/MP4/trees/{filename}.trees")

    print('\n'.join(bipartitions), end="")
