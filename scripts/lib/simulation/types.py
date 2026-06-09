from scripts.lib.types import Polymorphism
from pathlib import Path
import polars as pl
import numpy as np
from polars.datatypes import (
    Int64,
    Float64,
    String,
)

CONFIG_SCHEMA_T: pl.Schema = pl.Schema(
    {
        "nchar": Int64,
        "weight": Int64,
        "sigma_dlc": Float64,
        "sigma_het": Float64,
        "dlc_is_individual": String,
        "height_factor": Int64,
        "alpha_trm_site": Int64,
        "beta_trm_site": Int64,
        "h_root": Float64,
        "h_factor": Float64,
        "birth_rate": Int64,
        "death_rate": Int64,
        "death_power": Int64,
    }
)


class SimulationConfigFactory:
    poly_level: Polymorphism = Polymorphism.HIGH
    character_count: int
    min_tree_height: int
    homoplasy_factor: float
    do_borrowing: bool
    base_configs: Path

    def __init__(
        self,
        base_config_path: Path,
        poly_level: Polymorphism = Polymorphism.HIGH,
        character_count: int = 320,
        min_tree_height: int = 4,
        homoplasy_factor: float = 0.1,
        do_borrowing: bool = False,
    ):
        assert base_config_path.is_dir(), (
            f"Expected base_configs to be a directory. Found {base_config_path=}"
        )
        self.base_configs = base_config_path
        self.poly_level = poly_level
        self.character_count = character_count
        self.min_tree_height = min_tree_height
        self.homoplasy_factor = homoplasy_factor
        self.do_borrowing = do_borrowing

    def update_params(
        self,
        base_config_path: Path | None = None,
        poly_level: Polymorphism | None = None,
        character_count: int | None = None,
        min_tree_height: int | None = None,
        homoplasy_factor: float | None = None,
        do_borrowing: bool | None = None,
    ):
        assert base_config_path is None or base_config_path.is_dir(), (
            f"Expected base_configs to be a directory. Found {base_config_path=}"
        )
        self.base_configs = base_config_path or self.base_configs
        self.poly_level = poly_level or self.poly_level
        self.character_count = character_count or self.character_count
        self.min_tree_height = min_tree_height or self.min_tree_height
        self.homoplasy_factor = homoplasy_factor or self.homoplasy_factor
        self.do_borrowing = do_borrowing or self.do_borrowing

    def _to_polars_df(self) -> pl.DataFrame:
        borrowing_str = "borrowing" if self.do_borrowing else "noborrowing"
        base_config_path = (
            self.base_configs / f"{self.poly_level.value}_{borrowing_str}.csv"
        )
        assert base_config_path.is_file(), (
            f"Could not find file at {str(base_config_path)}"
        )
        base_df = pl.read_csv(base_config_path)
        transposed = base_df.transpose(include_header=True, column_names="").cast(
            CONFIG_SCHEMA_T
        )

        # character transform
        base_chrs_gcd = np.gcd.reduce(transposed.select(pl.col("nchar")))
        base_chr_count = transposed.select(pl.col("nchar")).sum().item()
        assert (self.character_count * base_chrs_gcd) % base_chr_count == 0, (
            f"Invalid character count: {self.character_count}."
            f"Base config: {base_chrs_gcd=}, {base_chr_count=}"
            f"Would have to multiply nchar of every character class by {self.character_count // base_chrs_gcd} / {base_chr_count // base_chrs_gcd}."
        )
        tree_height_gcd = np.gcd.reduce(transposed.select(pl.col("height_factor")))
        base_min_tree_height = transposed.select(pl.col("height_factor")).min().item()
        # will multiply everything by self.min_tree_height / base_min_tree_height
        assert (self.min_tree_height * tree_height_gcd % base_min_tree_height) == 0, (
            f"Invalid min_tree_height: {self.min_tree_height}, {tree_height_gcd=}, {base_min_tree_height=}"
        )
        transposed = transposed.with_columns(
            ((pl.col("nchar") * self.character_count) // base_chr_count).alias("nchar"),
            (
                (pl.col("height_factor") * self.min_tree_height) // base_min_tree_height
            ).alias("height_factor"),
            pl.lit(self.homoplasy_factor).alias("h_factor"),
            pl.lit(self.homoplasy_factor).alias("h_root"),
            pl.col("column").alias("character_class"),
        ).drop(["column"])
        reconstructed = transposed.transpose(include_header=True)
        reconstructed = reconstructed.rename(reconstructed.to_dicts()[-1]).rename(
            {"character_class": ""}
        )
        reconstructed = reconstructed[:-1]

        return reconstructed

    def _get_out_file_name(self) -> str:
        return f"{self.poly_level.value}_{self.homoplasy_factor}_{self.min_tree_height}_{self.character_count}.csv"

    def to_csv(self, out_dir: Path) -> Path:
        assert out_dir.is_dir, f"{str(out_dir)} is not a directory"
        df = self._to_polars_df()
        out_path = out_dir / self._get_out_file_name()
        df.write_csv(
            out_path, quote_style="never"
        )  # never is necessary because first column name is empty string.
        return out_path
