import shutil

import pytest

from scripts.lib.inference.scoring import score

pytestmark = pytest.mark.skipif(
    shutil.which("Rscript") is None, reason="Rscript not installed"
)

TREE = "((t1,t2),(t3,t4),t5);"


def test_identical_trees_zero_rates() -> None:
    r = score(TREE, TREE)
    assert r.fn_rate == 0.0
    assert r.fp_rate == 0.0


def test_discordant_estimate_has_fn() -> None:
    estimate = "((t1,t3),(t2,t4),t5);"
    r = score(estimate, TREE)
    assert r.fn_rate > 0
