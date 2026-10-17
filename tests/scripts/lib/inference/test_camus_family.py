from pathlib import Path

import polars as pl

from scripts.lib.inference.runners.camus import camus_to_family


def test_camus_to_family_renames_losslessly(tmp_path: Path):
    raw = tmp_path / "d.csv"
    newick = "((A:1,(B)#H1:::0.6),(#H1:::0.4,C));"
    pl.DataFrame(
        {
            "Number of Branches": [1],
            "Quartet Satisfied Percent": [50.0],
            "Extended Newick": [newick],
        }
    ).write_csv(raw)
    assert camus_to_family(raw).rows() == [(1, newick, True, 50.0)]


def test_camus_to_family_counts_events_not_hybrids(tmp_path: Path):
    # -B emits one event as two hybrids (ADR 0001); edges_added stays CAMUS's k.
    raw = tmp_path / "d.csv"
    newick = "((((A,((B)#H2,#H1)),((C)#H1,#H2)),(D,E)),OUT);"
    pl.DataFrame(
        {
            "Number of Branches": [1],
            "Quartet Satisfied Percent": [50.0],
            "Extended Newick": [newick],
        }
    ).write_csv(raw)
    assert camus_to_family(raw)["edges_added"].to_list() == [1]
