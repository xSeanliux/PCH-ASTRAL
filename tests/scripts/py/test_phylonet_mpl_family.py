from pathlib import Path

import pytest

from scripts.py.cli.schemata import NETWORK_FAMILY_SCHEMA
from scripts.py.phylonet_mpl_family import phylonet_mpl_to_family

BEST = "(O:0.12,((D:0.12)#H1:0.10::0.69,(C:0.33,(A:1.7,(B:0.13,#H1:0.06::0.31):0.8):1.2):2.8):11.4);"
OTHER = "(O:4.2,((C:1.1)#H1:2.3::0.35,(D:1.1,((B:0.5,A:1.4):0.2,#H1:2.9::0.64):1.4):2.2):3.6);"


def test_phylonet_mpl_to_family(tmp_path: Path):
    result = tmp_path / "d.result"
    # PhyloNet's layout: leading blank line, no trailing newline.
    result.write_text(
        f"\nInferred Network #1:\n{BEST}\nTotal log probability: -22.27\n"
        f"Inferred Network #2:\n{OTHER}\nTotal log probability: -24.27"
    )
    family = phylonet_mpl_to_family(result)
    assert list(family.schema.items())[:3] == list(NETWORK_FAMILY_SCHEMA.items())
    assert family.rows() == [(1, BEST, True, -22.27), (1, OTHER, False, -24.27)]


def test_empty_result_raises(tmp_path: Path):
    result = tmp_path / "d.result"
    result.write_text("")
    with pytest.raises(ValueError, match="no network"):
        phylonet_mpl_to_family(result)
