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


def get_rooted_quartets(tup):
    # returns all rooted quartets that have the split ab|cd
    a, b, c, d = tup
    labels = [a, b, c, d]
    pA = (a, b)
    pB = (c, d)
    return [
        RootedQuartet("BAL", labels, pA),                   # ((a,b),(c,d))
        RootedQuartet("LOP", labels, pA),                   # (a,(b,(c,d)))
        RootedQuartet("LOP", labels, tuple(reversed(pA))),  # (b,(a,(c,d)))
        RootedQuartet("LOP", labels, pB),                   # (c,(d,(a,b)))
        RootedQuartet("LOP", labels, tuple(reversed(pB))),  # (d,(c,(a,b)))
    ]

def get_loss_based_quartets(df, mode):
    '''
    mode    desc
    1       OneMostProb
    2       Deprecated
    3       MP4
    4       Loss-Rooted
    5       Loss-Unrooted
    6       Loss-ChrAgg
    7       Loss-OneMostProb (to be implemented)
    '''
    assert(4 <= mode <= 6)
    quartets = {}
    names = df.columns.values[3:]
    values = df.values[:, 3:]
    row_states_dict = [] # a list of rows, where each row = state name -> list of character names
    for row in values:
        row_states_dict.append({
            n: str(s).split('/') for (n, s) in zip(names, row)
        })

    
    if(mode == 6):
        # aggregate by character
        for nametup in combinations(names, 4):
            counts = {} # tree -> how many times they were chosen
            for states_dict in row_states_dict:
                best_trees = get_best_quartets_loss({
                    x : states_dict[x] for x in nametup
                })
                if(len(best_trees) >= 15): # when all trees have the same score, no information is supplied.
                    continue
                best_trees = list(map(lambda x: x.rooted_quartet(), best_trees))
                for rep in best_trees: 
                    addOne(counts, rep)
            aggr_trees = list(sorted(counts.items(), reverse=True, key=lambda x: x[1])) # get most selected trees
            res_trees = [t for (t, n) in aggr_trees if n == aggr_trees[0][1]] 
            for res_tree in res_trees:
                addOne(quartets, res_tree)

        return (None, quartets)

    for states_dict in row_states_dict: 
        #print(states_dict)
        for nametup in combinations(names, 4):
            best_trees = get_best_quartets_loss({
                x : states_dict[x] for x in nametup
            })

            if(len(best_trees) >= 15): # when all trees have the same score, no information is supplied.
                continue
            
            # list of best trees -> get quartets from them -> turn back into a list
            if(mode == 4):
                best_trees = list(map(lambda x: x.rooted_quartet(), best_trees))
            elif(mode == 5):
                best_trees = list(map(lambda x: x.get_unrooted_tuple(), best_trees))

            for tup in best_trees:
                addOne(quartets, tup)
    return (None, quartets) 
    # return (None, quartets)
    # where quartets is a dict (a,b,c,d) -> w

def best_rooted_quartets(trees: List[RootedQuartet], leaf_states): 
    '''
    @params 
    trees: a list of RootedQuartets with the same leaves
    leaf_states: dict of leaf -> list of states they exhibit. 

    All trees must have the same leaves, which are exactly the leaves described by that of leaf_staets
    '''

    trees = trees.copy() # avoid modifying original trees
    state_to_leaves = {}
    for leaf, states in leaf_states.items():
        for s in states: 
            if s not in state_to_leaves:
                state_to_leaves[s] = []
            state_to_leaves[s].append(leaf)

    for _, leaves in state_to_leaves.items():
        for tree in trees:
            tree.add_states(leaves)
    
    trees = sorted(trees, key=lambda x : x.loss)
    best_loss = trees[0].loss
    return [ t for t in trees if t.loss == best_loss]


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
            if(('t19', 't23', 't28', 't9') in all_q):
                breakpoint()
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
    1       OneMostProb+k (should be deprecated soon but right now all our results are on this method)
    2       Deprecated (AllMostProb)
    3       MP4
    4       Loss-Rooted
    5       Loss-Unrooted
    6       Loss-ChrAgg
    7       Loss-OneMostProb (to be implemented)
    8       OneMostProb, but using the `weights` column. Weights have to be integers!
    9       EVANS-ONE+k
    10      EVANS-ALL+k 
    11      EVANS-ALL-k, where the homoplsatic state is treated as any other.
    12      EVANS-ONE-k
    13      ONEMOSTPROB-k
    returns a tuple (metadata, quartets). Most of the times you just want quartets so do
    _, quartets = get_quartets(...).
    '''
    df = pd.read_csv(csv_path)
    if mode == 3:
        df = resolve_polymorphism_using_mp4(df)
    if 4 <= mode <= 6:
        return get_loss_based_quartets(df=df, mode=mode)
    if 9 <= mode <= 12: # This is where EVANS-ALL and EVANS-ONE +-K are!
        return get_new_omp(csv_path, mode)

    names, ret_values = get_values(csv_path)
    if mode == 8:
        weights = get_weights(csv_path)
    else:
        weights = None

    return get_quartets_names_ret_values(
        names = names,
        ret_values = ret_values,
        mode = mode,
        do_filter = do_filter,
        filter_lim = filter_lim,
        weights = weights,
    )

def get_quartets_names_ret_values(
    names, ret_values, mode, do_filter, filter_lim, weights = None
):
    if 9 <= mode <= 12:
        return get_new_omp_names_ret_values(
            names=names,
            values=ret_values,
            mode=mode,
        )
    all_quartets = {} # string to weight
    double_split_count = 0

    # for all characters
    for i, row in enumerate(ret_values):
        # weight = 1.0 if not use_original_weighting else float(row[1].iloc[2]) # morphological characters weighted > lexical & phonological characters
        name_to_states = {
            n: s for (n, s) in zip (names, row)
        }
        # row is a dictionary of language -> exhibit
        exhibits_state = dict()
        # exhibits_gene is state -> which languages have this state 
        for taxon, states in name_to_states.items():
            for c in states:
                if (mode != 13 and c == '0') or c == '?': # only consider known non-homoplastic states 
                    continue
                if c not in exhibits_state:
                    exhibits_state[c] = []

                exhibits_state[c].append(taxon)
        # keys: all non-homoplastic states with more than 2 languages exhibiting it 
        keys = [
            k 
            for (k, v) in exhibits_state.items() 
            if len(v) > 1
        ]
        quartets = {} # quartet (canonical string) -> dict (tuple) -> count
        for k1, k2 in combinations(keys, 2):
            # l: the lists of the languages exhibiting states i and j
            l1 = exhibits_state[k1]
            l2 = exhibits_state[k2]
            l1_set = set(l1) # this will be used to query to see if there is a REAL split
            l2_set = set(l2)
            l1p = list(combinations(l1, 2))
            l2p = list(combinations(l2, 2)) 
            all_q = [ # all possible quartets supported by this character
                (a, b, c, d) for (a, b) in l1p for (c, d) in l2p 
                if (a != c and a != d and b != c and b != d) # the conditional is so that you can't have things like AB|AC
                and (a not in l2_set) and (b not in l2_set)  # this is so that if a = 1, b = 1/2, c = 2, d = 2,
                and (c not in l1_set) and (d not in l1_set)  # ab|cd is not counted as a valid split.
            ]
            for q in all_q: 
                assert len(set(q)) == 4, f"""
                Bad quartet: character is {ret_values}, q = {q}, {k1=}, {k2=}, {l1=}, {l2=}
                {exhibits_state=}
                """
                sorted_form = get_sorted_tuple(q) # this is the canonical form of the quartet, depending only on what leaves it has
                canonical_form = get_canonical_tuple(q)
                if sorted_form not in quartets:
                    quartets[sorted_form] = {}
                addOne(quartets[sorted_form], canonical_form)

        # get most likely quartet for each four languages
        # pdb.set_trace() 
        for _, four_quartets in quartets.items():
            list_form = sorted([
                (frq, q) for (q, frq) in four_quartets.items()
            ], reverse=True) # a list of (frequency of the quartet, quartet) trees sorted in decreasing order of frequency
            # pdb.set_trace()
            most_common_cnt = list_form[0][0]
            most_common_quartets = list(filter(lambda x: x[0] == most_common_cnt, list_form)) # get just the most common quartets
            if(mode == 1 or mode == 3 or mode == 13):
                if len(most_common_quartets) > 1:
                    if(len(most_common_quartets) == 2):
                        double_split_count += 1
                        # print(f"Two: {most_common_quartets}, {name_to_states}")
                    continue
                returned_quartet = most_common_quartets[0][1]
                addOne(all_quartets, returned_quartet)
            elif(mode == 2): # deprecated but this was implemented already so it stays
                if len(most_common_quartets) >= 3:
                    continue
                for _, q in most_common_quartets:
                    returned_quartet = q
                    addOne(all_quartets, returned_quartet)
            elif(mode == 7):
                if len(most_common_quartets) > 1:
                    continue
                returned_quartet = most_common_quartets[0][1]
                rooted_quartets = get_rooted_quartets(returned_quartet)
                best_trees = best_rooted_quartets(rooted_quartets, { s: name_to_states[s] for s in most_common_quartets[0][1] })
                for tree in best_trees: 
                    addOne(all_quartets, tree.rooted_quartet())
            elif(mode == 8):
                if len(most_common_quartets) > 1:
                    if(len(most_common_quartets) == 2):
                        double_split_count += 1
                        # print(f"Two: {most_common_quartets}, {name_to_states}")
                    continue
                returned_quartet = most_common_quartets[0][1]
                addOne(all_quartets, returned_quartet, weights[i])


                
    # print(f"In {no_quartet_count} instances, two quartets were equally likely for a character & four leaves.")
    ret_dict = {
        'double_split_count': double_split_count
    }
    if do_filter:
        all_quartets = {
            q: w for q, w in all_quartets.items() if w > filter_lim
        }
    return (ret_dict, all_quartets)

def print_quartets(
        csv_path: str, 
        mode: int, 
        do_filter: bool = False,
        filter_lim: int = 0, # NOT USED! Here filtering is based on heavy bipartitions not quartet frequency
    ): 
    _, quartets = get_quartets(csv_path=csv_path, mode=mode)
    # print("HI!!!")
    if do_filter: 
        eprint("Filtering quartets based on R&T Heavy.")
        compatibility_filter = MonoCharacterCompatibilty(chars_csv_file="/projects/tallis/zxliu2/OneMostProb/example/z_rt_old/ie_dataset_heavy.csv")
    for q, w in quartets.items():
        if(type(q) == tuple and ((not do_filter) or compatibility_filter.quartet_compatible(*q))):
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
        do_filter: bool = False,
    ):
    _, quartets = get_quartets(csv_path=csv_path, mode=mode)
    if do_filter: 
        eprint("Filtering quartets based on R&T Heavy.")
        compatibility_filter = MonoCharacterCompatibilty(chars_csv_file="/projects/tallis/zxliu2/OneMostProb/example/z_rt_old/ie_dataset_heavy.csv")
    print(f"Found {len(quartets)} unique quartets.")
    with open(quartets_path, "w") as qf, open(counts_path, "w") as cf: 
        for q, w in quartets.items():
            if(type(q) == tuple and ((not do_filter) or compatibility_filter.quartet_compatible(*q))):
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

