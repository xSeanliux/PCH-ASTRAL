"""Tests for scripts.lib.utils.resolve_polytomies.

Proves resolve_polytomies *only* refines: output is binary, the leaf set is
unchanged, and every original bipartition survives (no taxon is moved). These
three together mean it resolves polytomies and does nothing else.
"""

from scripts.lib.utils import get_list_of_clades, newick_to_tree, resolve_polytomies


def _splits(tree) -> set[frozenset[str]]:
    """Every clade as its frozenset of leaf names."""
    return {frozenset(leaves) for leaves in get_list_of_clades(tree)}


def _is_binary(tree) -> bool:
    return all(len(c.clades) in (0, 2) for c in tree.find_clades())


def test_resolve_internal_polytomy():
    tree = newick_to_tree("((A,B,C),(D,E));")  # (A,B,C) is a polytomy
    before = _splits(tree)
    resolve_polytomies(tree)

    assert _is_binary(tree)
    # leaf set unchanged
    assert {c.name for c in tree.get_terminals()} == {"A", "B", "C", "D", "E"}
    # pure refinement: nothing removed
    assert before <= _splits(tree)


def test_resolve_root_polytomy():
    tree = newick_to_tree("(A,B,C,D,E);")  # star: root is one big polytomy
    before = _splits(tree)
    resolve_polytomies(tree)

    assert _is_binary(tree)
    assert {c.name for c in tree.get_terminals()} == {"A", "B", "C", "D", "E"}
    assert before <= _splits(tree)


def test_noop_on_binary_tree():
    tree = newick_to_tree("((A,B),(C,(D,E)));")  # already binary
    before = _splits(tree)
    resolve_polytomies(tree)
    assert _splits(tree) == before  # unchanged


def test_deterministic_given_seed():
    from scripts.lib.utils import tree_to_newick

    a = newick_to_tree("(A,B,C,D,E,F);")
    b = newick_to_tree("(A,B,C,D,E,F);")
    resolve_polytomies(a, seed=42)
    resolve_polytomies(b, seed=42)
    assert tree_to_newick(a) == tree_to_newick(b)


def test_refinement_adds_expected_node_count():
    # A degree-k node needs k-2 new internal nodes to become binary.
    tree = newick_to_tree("(A,B,C,D);")  # root degree 4 -> +2 internal nodes
    before = len(list(tree.find_clades()))
    resolve_polytomies(tree)
    after = len(list(tree.find_clades()))
    assert after - before == 2
