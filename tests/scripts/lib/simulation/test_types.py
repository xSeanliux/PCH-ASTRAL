from scripts.lib.simulation.types import SimulationConfigFactory
from scripts.lib.types import Polymorphism
import pytest
import os
from pathlib import Path


SIMULATION = Path(__file__).parent


def test_sim_factory_bad_dir():
    with pytest.raises(AssertionError) as e:
        _ = SimulationConfigFactory(base_config_path=Path("does_not_exist"))


def test_out_file_name(tmp_path: Path):
    tmp_dir = tmp_path / "tmp_base_config"
    os.mkdir(tmp_dir)
    scf = SimulationConfigFactory(
        base_config_path=tmp_dir,
        poly_level=Polymorphism.VERYHIGH,
        homoplasy_factor=123,
        min_tree_height=44,
        character_count=320,
    )
    assert scf._get_out_file_name() == "veryhigh_123_44_320.csv"


def test_base_config_does_not_exist():
    scf = SimulationConfigFactory(base_config_path=SIMULATION / "sample_base_config")
    with pytest.raises(AssertionError) as e:
        scf._to_polars_df()


def test_base_config_does_not_exist():
    scf = SimulationConfigFactory(base_config_path=SIMULATION / "sample_base_config")
    with pytest.raises(AssertionError) as e:
        scf._to_polars_df()
