from io import StringIO

import pytest
from Bio import Phylo

from scripts.lib.simulation.outgroup import (
    draw_lengths,
    graft_network,
    graft_outgroup,
)

TREE = "((t1:0.1,t2:0.2):0.3,(t3:0.1,t4:0.2):0.3)"
NETWORK = [
    TREE,
    "t1;(t3:0.1,t4:0.2);0.35;0.19",
    "t2;t3;0.4502;0.5",
]


def test_graft_makes_the_outgroup_sister_to_everything():
    tree = Phylo.read(StringIO(graft_outgroup(TREE + ";", "OUT", 0.05, 0.95)), "newick")
    ingroup, outgroup = tree.root.clades
    assert outgroup.name == "OUT" and outgroup.branch_length == 0.95
    assert ingroup.branch_length == 0.05
    assert {t.name for t in ingroup.get_terminals()} == {"t1", "t2", "t3", "t4"}


@pytest.mark.parametrize("terminator", ["", ";"])
def test_graft_keeps_the_terminator_it_was_given(terminator: str):
    grafted = graft_outgroup(TREE + terminator + "\n", "OUT", 0.05, 0.95)
    assert grafted == f"({TREE}:0.05,OUT:0.95){terminator}"


def test_graft_network_moves_each_contact_later_by_the_stem():
    stem = 0.05
    tree, *contacts = graft_network(NETWORK, "OUT", stem, 0.95)
    assert tree == graft_outgroup(TREE, "OUT", stem, 0.95)
    for before, after in zip(NETWORK[1:], contacts):
        a, b, time, strength = before.split(";")
        a2, b2, time2, strength2 = after.split(";")
        # Clades and strength untouched: the simulator matches clades by string.
        assert (a2, b2, strength2) == (a, b, strength)
        assert float(time2) == pytest.approx(float(time) + stem)
        # Each clade is still found in the grafted tree.
        assert a in tree and b in tree


def test_graft_network_rejects_a_malformed_contact_line():
    with pytest.raises(ValueError):
        graft_network([TREE, "t1;t2;0.4"], "OUT", 0.05, 0.95)


def test_draw_lengths_is_stable_and_in_range():
    stem, outgroup = draw_lengths(seed=7)
    assert (stem, outgroup) == draw_lengths(seed=7)
    assert 0.0 <= stem <= 0.1
    assert 0.9 <= outgroup <= 1.0
    assert draw_lengths(seed=8) != (stem, outgroup)
