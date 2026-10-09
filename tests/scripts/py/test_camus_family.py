from pathlib import Path

import polars as pl

from scripts.py.camus_family import camus_to_family


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
    assert camus_to_family(raw).rows() == [(1, newick, 50.0)]
