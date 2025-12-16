import sys 
import pandas as pd
from Bio import Phylo
import matplotlib.pyplot as plt
from enum import IntEnum

class QuartetType(IntEnum):
    ONEMOSTPROB = 1
    MP4 = 3
    LOSS_ROOTED = 4
    LOSS_UNROOTED = 5
    LOSS_CHRAGG = 6
    LOSS_ONEMOSTPROB = 7
    ONEMOSTPROB_WEIGHTS = 8
    EVANS_ONE_PLUS_K = 9
    EVANS_ALL_PLUS_K = 10
    EVANS_ALL_MINUS_K = 11
    EVANS_ONE_MINUS_K = 12
    ONEMOSTPROB_MINUS_K = 13

def make_sure_path_exists(path):
    path = '/'.join(path.split('/')[:-1])
    # print("PATH = ", path)
    Path(path).mkdir(parents=True, exist_ok=True)
def addOne(mp, k, v = 1):
    if k not in mp:
        mp[k] = 0
    mp[k] += v

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def get_values(csv_name):
    # e.g. ......./sim_tree1_1.csv
    df = pd.read_csv(csv_name)
    names = df.columns.values[3:]
    values = df.values[:, 3:]
    ret_values = []
    for row in values:
        ret_values.append(list(map(lambda e: str(e).split('/'), row)))
    return (names, ret_values)

def get_weights(csv_name):
    # e.g. ......./sim_tree1_1.csv
    df = pd.read_csv(csv_name)
    if 'weight' not in df:
        raise KeyError("Column 'weight' not found in DataFrame")
    
    weights = df['weight']
    
    # Check if all values are integers or can be safely cast to int
    if not all(isinstance(x, int) or (isinstance(x, float) and x.is_integer()) for x in weights):
        raise ValueError("All values in 'weight' must be integers or convertible to integers without loss.")
    
    return weights.astype(int)  # Ensure it's an integer Series

def flatten(iterable):
    # https://codereview.stackexchange.com/questions/201244/flatten-an-array-in-python
    # flattens a Python array (instead of a numpy one)
    print(type(iterable))
    try:
        iterator = iter(iterable)
        if type(iterable) == str:
            return iterable
    except TypeError:
        yield iterable
    else:
        for element in iterator:
            yield from flatten(element)
         
def get_list_of_clades(ptree: Phylo.BaseTree.TreeMixin):
    return list(map(lambda clade: list((map(lambda x: x.name, clade.find_elements(terminal=True)))), ptree.find_clades())) # a list of list of terminals that define each clade.

def clade_error(tree1: Phylo.BaseTree.TreeMixin, tree2: Phylo.BaseTree.TreeMixin):
    cladeset1 = set(map(lambda l: ';'.join(sorted(l)), get_list_of_clades(tree1))) # e.g. ["t1", "t0"] -> "t0;t1"
    cladeset2 = set(map(lambda l: ';'.join(sorted(l)), get_list_of_clades(tree2)))
    return cladeset1.symmetric_difference(cladeset2)

def draw_tree(tree_path, format, root, title="", fig = None, ax = None, idx = None, branch_labels = lambda c: "", label_func = lambda c: c.name):
    '''
    1. reads a tree from tree_path with format format
    2. roots the tree at root (e.g. HI or Anatolian) and removes all branch lengths (only topology is preserved)
    3. for each tree (e.g. for MP there may be multiple trees inferred), draws the tree with title title (all figures have the same title)
    4. shows the plot and returns the ax object
    '''
    assert not ((fig is None) ^ (ax is None)), "exactly one of fig and axe is None."
        
    if ax is None:
        fig, ax = plt.subplots()
    i = -1
    for tree in Phylo.parse(tree_path, format=format):
    # tree = next(Phylo.parse(tree_path, format=format))
        i += 1
        if idx is not None and idx != i:
            continue
        tree.root_with_outgroup(root)

        for c in tree.find_elements():
            c.confidence = None
            c.branch_length = None

        Phylo.draw(tree, axes=ax, do_show=False, branch_labels= branch_labels, label_func=label_func)
        ax.set_title(title)
        plt.show()
        yield fig, ax, tree