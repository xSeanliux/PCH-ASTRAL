import pandas as pd 
import functools 
import itertools
from shortuuid import uuid
from Bio import Phylo 
from typing import Tuple
from matplotlib import pyplot as plt

def set_tree_ids(tree: Phylo.BaseTree.TreeMixin):
    all_names = set()
    counter = 0

    def get_new_id(n: int = 3): # n is how many bytes to take the 
        nonlocal counter
        res = f"i{counter:03}"
        counter += 1
        return res

    for u in tree.find_clades():
        if not hasattr(u, 'id'):
            setattr(u, 'id', get_new_id())
        # print("Set id of", u, "to be", u.id)

def get_lcas(tree: Phylo.BaseTree.TreeMixin) -> dict[tuple[str, str], str]:
    lca = {}

    for u in tree.find_clades(terminal=False):
        for c1, c2 in itertools.combinations(u.clades, 2):
            for v, w in itertools.product(c1.get_terminals(), c2.get_terminals()):
                lca[(v.id, w.id)] = u.id
                lca[(w.id, v.id)] = u.id
    return lca

def get_dfs_order(tree: Phylo.BaseTree.TreeMixin) -> dict[str: tuple[int, int]]:
    ret = {}
    n = 0
    def dfs(u: Phylo.BaseTree.Clade, dep: int = 0):
        setattr(u, 'dep', dep)
        # print(f"{u.id} has dep {u.dep}")
        nonlocal n
        n += 1
        l = n
        setattr(u, 'l', n)
        for v in u.clades:
            setattr(v, 'parent', u.id)
            # print(f"{v.id} parent is {u.id}")
            dfs(v, dep=dep + 1)
        n += 1
        r = n
        setattr(u, 'r', n)
        ret[u.id] = (l, r)
    setattr(tree.root, 'parent', tree.root.id)
    dfs(tree.root)
    return ret

def is_in_clade(
        u: str, 
        v: str,
        dfs_order: dict[str: tuple[int, int]]
    ) -> bool:
    # if u is in v
    return dfs_order[v][0] <= dfs_order[u][0] and dfs_order[u][1] <= dfs_order[v][1]

def is_in_clade_mixin(
        u: Phylo.BaseTree.TreeMixin, 
        v: Phylo.BaseTree.TreeMixin,
    ) -> bool:
    return v.l <= u.l and u.r <= v.r

def validate_tree(
    tree: Phylo.BaseTree.TreeMixin,
): 
    expected_attrs = ['id', 'l', 'r', 'parent']
    for clade in tree.find_clades():
        for attr in expected_attrs:
            assert(hasattr(clade, attr)), f"{clade} does not have {attr} set."

def root_at_internal_node(tree):
    tree.root_with_outgroup(outgroup_targets = tree.get_nonterminals()[0])

def is_on_path(s: str, u: str, t: str, lca: str, dfs_order: dict[str: tuple[int, int]]):
    # checks to see if u is on the path from s to t
    # given that lca = lca(s, t)
    return (
        (is_in_clade(u, lca, dfs_order) and is_in_clade(s, u, dfs_order)) or 
        (is_in_clade(u, lca, dfs_order) and is_in_clade(t, u, dfs_order))
    )

def calculate_edge_support(
        tree: Phylo.BaseTree.TreeMixin,
        quartets: list[tuple[str, str, str, str]] 
    ) -> dict[tuple[str, str], list[Tuple]]:
    lca = get_lcas(tree)
    dfs_order = get_dfs_order(tree)
    validate_tree(tree)
    supported_edges = {}
    dep = {
        n.id: n.dep for n in tree.find_elements(target=Phylo.BaseTree.Clade)
    }
    parent = {
        n.id: n.parent for n in tree.find_elements(target=Phylo.BaseTree.Clade)
    }
    name_to_id = {
        n.name: n.id for n in tree.find_clades(terminal=True)
    }
    quartets = list(set(quartets))
    for q in quartets: 
        a, b, c, d = tuple(map(lambda taxon_name: name_to_id[taxon_name], q))
        v1 = lca[a, b]
        v2 = lca[c, d]
        if dep[v1] < dep[v2]:
            v1, v2 = v2, v1 
            a, b, c, d = c, d, a, b
        v = v1 
        if is_in_clade(c, v, dfs_order) or is_in_clade(d, v, dfs_order):
            continue
        u = parent[v]
        if(u == v):
            continue 
        if (
            is_on_path(c, u, d, v2, dfs_order) # if u is on the path from c to d
        ):
            supported_edges.setdefault((u,v), [])
            supported_edges[(u,v)].append(q)
    return supported_edges
        
