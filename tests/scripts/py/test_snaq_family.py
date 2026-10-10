import os
import subprocess
from pathlib import Path

import polars as pl
import pytest

from scripts.py.cli.schemata import NETWORK_FAMILY_SCHEMA
from scripts.py.snaq_family import snaq_to_family

REPO = Path(__file__).parents[3]
BEST = "((A,(B)#H1:::0.8),(C,(D,#H1:::0.2)),OUT);"
OTHER = "((A,#H1:::0.3),(C,(D)#H1:::0.7),(B,OUT));"
NETWORKS = (
    "(OUT,(A,(B)#H1:::0.8),(C,(D,#H1:::0.2)));, with -loglik 1.5"
    " (best network found, remaining sorted by log-pseudolik; the smaller, the better)\n"
    f"{OTHER}, with -loglik 2.5\n"
    f"{OTHER}, with -loglik -1\n"
    "Problem found when optimizing branch lengths for some networks, ..."
)
# sim_2_1_1 of experiments/snaq_smoke: the best puts OUT below #H15; the runner-up roots.
SIM_2 = (
    "(t7,t5,(t6,(t8,((t13)#H13,((t16,(t29,(t30,#H13))),((t2,(t1,(OUT)#H15)),(t3,#H15)))))));"
    ", with -loglik 2574.1 (best network found, ...)\n"
    "(OUT,#H15,(t1,(t2,((((((t7,t5),t6),t8),(t13)#H13),(t16,(t29,(t30,#H13)))),(t3)#H15))));"
    ", with -loglik 3261.6\n"
)


def _family(
    tmp_path: Path, networks: str | None, best: str, choice: str
) -> pl.DataFrame:
    if networks is not None:
        (tmp_path / "d.networks").write_text(networks)
    (tmp_path / "d.net").write_text(best + "\n")
    (tmp_path / "d.choice").write_text(choice + "\n")
    return snaq_to_family(
        tmp_path / "d.networks", tmp_path / "d.net", tmp_path / "d.choice"
    )


def test_best_is_chosen(tmp_path: Path):
    family = _family(tmp_path, NETWORKS, BEST, "0 true")
    assert list(family.schema.items())[:3] == list(NETWORK_FAMILY_SCHEMA.items())
    assert family.schema["neg_loglik"] == pl.Float64
    assert family["network_newick"].to_list() == [BEST, OTHER, OTHER]
    assert family["edges_added"].to_list() == [1, 1, 1]
    assert family["neg_loglik"].to_list() == [1.5, 2.5, None]
    assert family["is_best"].to_list() == [True, False, False]
    assert family["is_rooted_on_outgroup"].to_list() == [True, None, None]


def test_alternative_is_chosen(tmp_path: Path):
    family = _family(tmp_path, NETWORKS, BEST, "1 true")
    assert family["network_newick"].to_list()[:2] == [NETWORKS.split(", with")[0], BEST]
    assert family["is_best"].to_list() == [False, True, False]
    assert family["is_rooted_on_outgroup"].to_list() == [None, True, None]


def test_unrootable_keeps_snaqs_best(tmp_path: Path):
    family = _family(tmp_path, NETWORKS, BEST, "0 false")
    assert family["is_best"].to_list() == [True, False, False]
    assert family["is_rooted_on_outgroup"].to_list() == [False, None, None]


def test_tree_has_no_networks_file(tmp_path: Path):
    family = _family(tmp_path, None, "((A,B),(C,D),OUT);", "0 true")
    assert family.rows() == [(0, "((A,B),(C,D),OUT);", True, None, True)]


@pytest.mark.skipif(not (REPO / "bin" / "julia").exists(), reason="needs bin/julia")
@pytest.mark.parametrize(
    "networks, choice",
    [(SIM_2, "1 true"), (SIM_2.splitlines()[0], "0 false")],
    ids=["runner-up", "none-rootable"],
)
def test_run_snaq_choose(tmp_path: Path, networks: str, choice: str):
    (tmp_path / "d.networks").write_text(networks + "\n")
    env = os.environ | {
        "JULIA_DEPOT_PATH": str(REPO / "bin" / "julia-depot"),
        "JULIA_PROJECT": str(REPO / "scripts" / "jl"),
    }
    run_snaq = REPO / "scripts" / "jl" / "run_snaq.jl"
    subprocess.run(
        [REPO / "bin" / "julia", run_snaq, "--choose", tmp_path / "d", "OUT"],
        env=env,
        check=True,
    )
    assert (tmp_path / "d.choice").read_text().strip() == choice
    assert (
        (tmp_path / "d.net")
        .read_text()
        .startswith("(OUT," if choice == "1 true" else "(t7,")
    )
