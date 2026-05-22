from scripts.lib.bipartitions import ConstraintTrees, constraint_trees_from_dataset
from Bio.Phylo.BaseTree import Tree
from Bio.Phylo.NewickIO import parse
from io import StringIO


def tree_from_newick(newick: str) -> Tree:
    sio = StringIO(initial_value=newick)
    trees = list(parse(handle=sio))
    assert len(trees) == 1, f"expected one tree, got {len(trees)}"
    return trees[0]


def test_constraint_trees_write():
    newick_trees = [
        "(c,(d,e));",
        "((a,b));",
    ]
    ct = ConstraintTrees(trees=set(tree_from_newick(n) for n in newick_trees))
    print(ct.treeset)

    sio = StringIO()
    ct.write(sio)
    assert sio.getvalue().strip() == "\n".join(newick_trees)
