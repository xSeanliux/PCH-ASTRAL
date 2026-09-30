import pytest

from scripts.lib.inference.network_format import contact_network_to_rich_newick

SIX = "((((A:1,B:1):1,C:1):1,(D:1,E:1):1):1,OUT:1)"


def test_six_taxon_reference():
    # The case measured in spec/camus/scoring.md.
    text = SIX + "\nB;C;0.5;0.3\n"
    assert (
        contact_network_to_rich_newick(text)
        == "((((A,((B)#H2,#H1)),((C)#H1,#H2)),(D,E)),OUT);"
    )


def test_base_tree_alone_strips_lengths():
    assert contact_network_to_rich_newick(SIX + ";\n") == "((((A,B),C),(D,E)),OUT);"


def test_subtree_clade_is_matched_without_its_length():
    text = SIX + "\n(A:1,B:1);D;0.5;0.3\n"
    assert (
        contact_network_to_rich_newick(text)
        == "((((((A,B))#H2,#H1),C),(((D)#H1,#H2),E)),OUT);"
    )


def test_two_contacts_on_one_branch_nest_earliest_outermost():
    # Listed later, happens earlier: sorted by time, so the t=0.2 event wraps outside.
    text = SIX + "\nB;C;0.8;0.3\nB;D;0.2;0.3\n"
    out = contact_network_to_rich_newick(text)
    assert out == "((((A,((((B)#H4,#H3))#H2,#H1)),((C)#H3,#H4)),(((D)#H1,#H2),E)),OUT);"


def test_leaf_clade_does_not_match_a_longer_label():
    tree = "(((t2:1,t26:1):1,t1:1):1,OUT:1)"
    out = contact_network_to_rich_newick(tree + "\nt2;t1;0.5;0.3\n")
    assert out == "(((((t2)#H2,#H1),t26),((t1)#H1,#H2)),OUT);"


def test_missing_clade_raises():
    with pytest.raises(ValueError, match="matched 0"):
        contact_network_to_rich_newick(SIX + "\nZ;C;0.5;0.3\n")
