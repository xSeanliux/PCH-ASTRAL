from scripts.lib.types import Dataset, Character
from scripts.lib.utils import tree_to_newick, newick_to_tree
from scripts.lib.bipartitions import ConstraintTrees, constraint_trees_from_dataset
from Bio.Phylo.BaseTree import Tree
from Bio.Phylo.NewickIO import parse
from io import StringIO


def test_constraint_trees_write():
    newick_trees = [
        "((a,b));",
        "(c,(d,e));",
    ]
    ct = ConstraintTrees(trees=set(newick_to_tree(n) for n in newick_trees))
    print(ct.treeset)

    sio = StringIO()
    ct.write(sio)
    assert sio.getvalue().strip() == "\n".join(newick_trees)


def test_get_trees_from_dataset():
    ds = Dataset(
        names=["a", "b", "c", "d"],
        chrs=[
            Character(
                features={
                    "a": ["0"],
                    "b": ["0", "1"],
                    "c": ["0", "2"],
                    "d": ["0", "2"],
                },
                weight=1,
            )
        ],
    )
    constraints = constraint_trees_from_dataset(ds)
    newick_trees = ["((b),(a,c,d));", "((c,d),(a,b));"]
    assert set(tree_to_newick(t).strip() for t in constraints) == set(newick_trees)
