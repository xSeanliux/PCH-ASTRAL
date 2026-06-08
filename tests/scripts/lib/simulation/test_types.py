from scripts.lib.simulation.types import SimulationConfigFactory, CONFIG_SCHEMA_T
from scripts.lib.types import Polymorphism
import pytest
import os
from pathlib import Path
from polars.testing import assert_series_equal
import polars as pl


SIMULATION = Path(__file__).parent


def test_sim_factory_bad_dir():
    with pytest.raises(AssertionError) as e:
        _ = SimulationConfigFactory(base_config_path=Path("does_not_exist"))
    assert "Expected base_configs to be a directory" in str(e.value)


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

    assert "Could not find file at" in str(e.value)


def test_to_polars_df_raise_invalid_chr_count():
    scf = SimulationConfigFactory(
        base_config_path=SIMULATION / "sample_base_config",
        poly_level=Polymorphism.LOW,
        character_count=321,
    )
    with pytest.raises(AssertionError) as e:
        scf._to_polars_df()

    assert "Invalid character count" in str(e.value)


def test_to_polars_df_raise_invalid_tree_height():
    scf = SimulationConfigFactory(
        base_config_path=SIMULATION / "sample_base_config",
        poly_level=Polymorphism.LOW,
        min_tree_height=4,
    )
    with pytest.raises(AssertionError) as e:
        scf._to_polars_df()

    assert "Invalid min_tree_height" in str(e.value)


def test_to_polars_valid():
    scf = SimulationConfigFactory(
        base_config_path=SIMULATION / "sample_base_config",
        poly_level=Polymorphism.LOW,
        min_tree_height=6,
        homoplasy_factor=7122,
        character_count=640,
    )
    df = scf._to_polars_df()

    transposed = df.transpose(include_header=True, column_names="").cast(
        CONFIG_SCHEMA_T
    )
    assert transposed.select(pl.col("nchar")).sum().item() == 640
    assert_series_equal(
        transposed["h_factor"], pl.Series([7122.0] * len(transposed)), check_names=False
    )
    assert_series_equal(
        transposed["h_root"], pl.Series([7122.0] * len(transposed)), check_names=False
    )
    assert transposed.select(pl.col("height_factor")).min().item() == 6
