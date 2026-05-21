import polars as pl
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from collections import Counter

Quple = tuple[str, str, str, str]
Taxon = str
State = str


@dataclass(unsafe_hash=True)
class Quartet:
    _quartets: Quple

    @classmethod
    def normalise(cls, q: Quple) -> Quple:
        a, b, c, d = q
        if a > b:
            a, b = b, a
        if c > d:
            c, d = d, c
        if a > c:
            a, b, c, d = c, d, a, b
        return (a, b, c, d)

    def __str__(self):
        a, b, c, d = self._quartets
        return f"(({a},{b}),({c},{d}))"

    def __init__(self, q: Quple):
        self._quartets = self.normalise(q)

    @property
    def taxon_set(self) -> set[Taxon]:
        return set(self._quartets)


@dataclass
class Character:
    features: dict[Taxon, list[State]]
    weight: int


@dataclass
class Dataset:
    names: list[Taxon]
    chrs: list[Character]

    @staticmethod
    def _extract_names_and_chrs(
        df: pl.DataFrame,
    ) -> tuple[list[Taxon], list[Character]]:
        cols = df.columns
        assert cols[:3] == ["id", "feature", "weight"], (
            f"expect first three cols to be id, feature, weight but found {cols[:3]}"
        )
        df = df.with_columns(pl.all().cast(pl.String))
        names = cols[3:]
        chrs: list[Character] = []
        for row in df.iter_rows(named=True):
            weight = int(row["weight"])
            features = {
                k: str(v).split("/")
                for k, v in row.items()
                if k not in ["id", "feature", "weight"]
            }
            chrs.append(Character(features=features, weight=weight))
        return names, chrs

    @classmethod
    def from_path(cls, path: Path) -> "Dataset":
        assert path.is_file(), f"{path} is not a file."
        df = pl.read_csv(path)
        names, chrs = cls._extract_names_and_chrs(df)
        return Dataset(names=names, chrs=chrs)


class QuartetGenerationScheme(ABC):
    @abstractmethod
    def get_quartets(cls, dataset: Dataset) -> Counter[Quartet]: ...
