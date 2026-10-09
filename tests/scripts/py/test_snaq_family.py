from pathlib import Path

import polars as pl

from scripts.py.cli.schemata import NETWORK_FAMILY_SCHEMA
from scripts.py.snaq_family import snaq_to_family

BEST = "((A,(B)#H1:::0.8),(C,(D,#H1:::0.2)),OUT);"
OTHER = "((A,#H1:::0.3),(C,(D)#H1:::0.7),(B,OUT));"


def test_snaq_to_family(tmp_path: Path):
    networks = tmp_path / "d.networks"
    networks.write_text(
        "(OUT,(A,(B)#H1:::0.8),(C,(D,#H1:::0.2)));, with -loglik 1.5"
        " (best network found, remaining sorted by log-pseudolik; the smaller, the better)\n"
        f"{OTHER}, with -loglik 2.5\n"
        f"{OTHER}, with -loglik -1\n"
        "Problem found when optimizing branch lengths for some networks, ..."
    )
    best = tmp_path / "d.net"
    best.write_text(BEST + "\n")
    family = snaq_to_family(networks, best)
    assert list(family.schema.items())[:2] == list(NETWORK_FAMILY_SCHEMA.items())
    assert family.schema["neg_loglik"] == pl.Float64
    assert family["network_newick"].to_list() == [BEST, OTHER, OTHER]
    assert family["edges_added"].to_list() == [1, 1, 1]
    assert family["neg_loglik"].to_list() == [1.5, 2.5, None]
    assert family["is_best"].to_list() == [True, False, False]


def test_tree_has_no_networks_file(tmp_path: Path):
    best = tmp_path / "d.net"
    best.write_text("((A,B),(C,D),OUT);\n")
    family = snaq_to_family(tmp_path / "d.networks", best)
    assert family.rows() == [(0, "((A,B),(C,D),OUT);", None, True)]
