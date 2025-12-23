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
from functools import reduce
from scripts.lib.loss_quartets import *
from scripts.lib.utils import *
from scripts.lib.compatibility import *
from itertools import combinations
from typing import List, Tuple, Union
from jinja2 import Environment, FileSystemLoader
import pdb
from collections import Counter

def get_all_csv_paths(folder_path):
    all_paths = glob.glob(folder_path + "/*/*.csv") + glob.glob(folder_path + "/*.csv")
    return all_paths

def get_sorted_tuple(tup):
    return str(sorted(tup))

class Frequenter():
    # supports initialisation with a list of items
    # keeps a frequency table 
    # supports querying of a list of items, returning the most frquent out of them. 
    # ties are broken arbitrarily.
    def __init__(self, arr):
        self.frqs = {}
        for x in arr:
            if x not in self.frqs:
                self.frqs[x] = 0
            self.frqs[x] += 1
    
    def query(self, k):
        return max(k, key=lambda x : self.frqs[x])

    def set_frq(self, k, v):
        self.frqs[k] = v

def process_row(row):
    data = row[3:]
    data = [str(x).split('/') for x in data]
    frq = Frequenter(reduce(
        lambda acc, x : acc + x,
        data,
        [] 
    ))
    data = [ frq.query(k) for k in data ]
    row[3:] = data
    return row

def resolve_polymorphism_using_mp4(df):
    for i, row in enumerate(df.values):
        df.iloc[i, :] = process_row(row)
    return df

def get_canonical_tuple(tup):
    A = tuple(sorted(tup[:2]))
    B = tuple(sorted(tup[2:]))
    if A > B:
        A, B = B, A
    return (*A, *B)



def get_new_omp_names_ret_values(
    names: List[str],
    values: List[List[List[str]]],
    mode: int,
):
    res, votes = {}, Counter()
    # calculate votes
    for row in values:
        name_to_states = {
            n: s for (n, s) in zip(names, row)
        }
        exhibits_state = dict()
        # exhibits_state is state -> which languages have this state 
        for taxon, states in name_to_states.items():
            for c in states:
                if (c in ['0'] and mode != 11 and mode != 12) or c == '?': # only consider known non-homoplastic states, if modes are 11 and 12 then there is no knowledge of homoplastic states 
                    continue
                if c not in exhibits_state:
                    exhibits_state[c] = []

                exhibits_state[c].append(taxon)
        # big_states: all known non-homoplastic states with more than 2 languages exhibiting it 
        big_states = [
            k 
            for (k, v) in exhibits_state.items() 
            if len(v) > 1
        ]
        for k1, k2 in combinations(big_states, 2):
            # l: the lists of the languages exhibiting states i and j
            l1 = exhibits_state[k1]
            l2 = exhibits_state[k2]
            l1_set = set(l1) # this will be used to query to see if there is a REAL split
            l2_set = set(l2)
            l1p = list(combinations(l1_set - l2_set, 2))
            l2p = list(combinations(l2_set - l1_set, 2)) 
            all_q = [ # all possible quartets supported by this character
                get_canonical_tuple((a, b, c, d)) for (a, b) in l1p for (c, d) in l2p 
            ]
            votes.update(all_q)
    if mode == 10 or mode == 11:
        return (None, votes)
    # Now tally up votes        
    # sorting first so that I don't have to do extra calls of get_canonical_tuple
    sorted_names = sorted(names)
    ties, unique_best = 0, 0
    for a, b, c, d in combinations(sorted_names, 4):
        quartet_counts = sorted([
            ((a, b, c, d), votes[(a, b, c, d)]),
            ((a, c, b, d), votes[(a, c, b, d)]),
            ((a, d, b, c), votes[(a, d, b, c)]),
        ], key = lambda x: x[1], reverse=True)
        if quartet_counts[0][1] > quartet_counts[1][1]:
            res[quartet_counts[0][0]] = 1
            unique_best += 1
        elif quartet_counts[1][1] > quartet_counts[2][1]:
            # if first and second are equal then take both
            # Don't take anything if all three are the same
            res[quartet_counts[0][0]] = 1
            res[quartet_counts[1][0]] = 1
            ties += 1
    
    return ({
            'votes': votes, 
            'ties': ties, 
            'unique_best': unique_best
        }, 
        res
    )


# TODO: add this to readme
def get_new_omp(
    csv_path: str,
    mode: int
    ):
    assert 9 <= mode <= 12, "mode has to be between 9 and 12"
    names, values = get_values(csv_path)
    return get_new_omp_names_ret_values(
        names=names,
        values=values,
        mode=mode,
    ) 

def get_quartets(csv_path   : str, 
                mode        : int=11,
                do_filter      : bool=False,
                filter_lim  : int=2,
    ):
    '''
    mode    desc
    1~9     DEPRECATED
    10      PCH-ASTRAL+K 
    11      PCH-ASTRAL-K
    returns a tuple (metadata, quartets). Most of the times you just want quartets so do
    _, quartets = get_quartets(...).
    '''
    assert mode in [10, 11]
    return get_new_omp(csv_path, mode)

def get_quartets_names_ret_values(
    names, ret_values, mode, do_filter, filter_lim, weights = None
):
    assert mode in [10, 11]
    return get_new_omp_names_ret_values(
        names=names,
        values=ret_values,
        mode=mode,
    )

def print_quartets(
        csv_path: str, 
        mode: int, 
    ): 
    _, quartets = get_quartets(csv_path=csv_path, mode=mode)
    for q, w in quartets.items():
        if(type(q) == tuple):
            (a, b, c, d) = q
            print(f'(({a},{b}),({c},{d}));\n' * w, end="") 
        elif(type(q) == str):
            if(q[-1] != '\n'):
                q = q + '\n'
            print(q * w, end="")

def print_waster_quartets(
        csv_path: str, 
        mode: int, 
        quartets_path: Union[Path, str], 
        counts_path: Union[Path, str],
    ):
    _, quartets = get_quartets(csv_path=csv_path, mode=mode)
    print(f"Found {len(quartets)} unique quartets.")
    with open(quartets_path, "w") as qf, open(counts_path, "w") as cf: 
        for q, w in quartets.items():
            if(type(q) == tuple):
                (a, b, c, d) = q
                qf.write(f'(({a},{b}),({c},{d}));\n')
                cf.write(f'{w}\n')
            elif(type(q) == str):
                if(q[-1] != '\n'):
                    q = q + '\n'
                qf.write(q)
                cf.write(f'{w}\n')

def print_quartets_in_nexus(
        csv_path: str, 
        mode: int
    ):
    """
    Takes a csv path and a mode (like all other methods), 
    and will print quartets in NEXUS format. In particular, if ab|cd is a quartet with weight W, 
    then there will be a parsimony character A such that it has weight W and 
    A(a) = A(b) = 0,
    A(c) = A(d) = 1,
    A(x) = ? for all other taxa.
    """
    names, _ = get_values(csv_path) # list of all taxa names
    name_id = { # assign each name a numerical ID
        n: i for i, n in enumerate(names)
    }
    _, quartets = get_quartets(
        csv_path = csv_path,
        mode = mode,
    )
    # names: list of taxa names
    # quartets: list of strings of length |quartet|, one for each quaret, with 0s on one side, 1s on the other, and ?s elsewhere
    # weights: list of tuples (weight, [indices of quartets with that weight])
    pass

