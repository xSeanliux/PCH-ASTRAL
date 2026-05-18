import polars as pl
from dataclasses import dataclass
from pathlib import Path
from enum import StrEnum
from abc import ABC, abstractmethod
from collections import defaultdict, Counter
from itertools import combinations

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

    @staticmethod
    def from_path(cls, path: Path) -> "Dataset":
        assert path.is_file(), f"{path} is not a file."
        df = pl.read_csv(path)
        names, chrs = cls._extract_names_and_chrs(df)
        return Dataset(names=names, chrs=chrs)


class QuartetGenerationScheme(ABC):
    @abstractmethod
    def get_quartets(cls, dataset: Dataset) -> Counter[Quartet]: ...


class PCH_ASTRAL_W(QuartetGenerationScheme):
    @classmethod
    def get_quartets(cls, dataset: Dataset) -> Counter[Quartet]:
        quartets: Counter[Quartet] = Counter()
        for chr in dataset.chrs:
            state_to_taxa: dict[State, set[Taxon]] = defaultdict(set)
            for t, ss in chr.features.items():
                for s in ss:
                    state_to_taxa[s].add(t)
            informative_states = [s for s, ts in state_to_taxa.items() if len(ts) > 1]
            for s1, s2 in combinations(informative_states, 2):
                t1s, t2s = state_to_taxa[s1], state_to_taxa[s2]
                # l: the set of taxa with state s1/s2 but not s2/s1
                l1 = t1s - t2s
                l2 = t2s - t1s
                quartets.update(
                    [
                        Quartet((a, b, c, d))
                        for a, b in combinations(l1, 2)
                        for c, d in combinations(l2, 2)
                    ]
                )
        return quartets


class PCH_ASTRAL_O(QuartetGenerationScheme):
    def get_quartets(cls, dataset: Dataset) -> Counter[Quartet]:
        quartets_w = PCH_ASTRAL_W.get_quartets(dataset)
        four_taxa_to_quartets: dict[set[Taxon], Counter[Quartet]] = defaultdict(Counter)
        quartets = Counter[Quartet]()
        for q, n in quartets_w.items():
            four_taxa_to_quartets[q.taxon_set].update({q: n})

        for _, quartet_counter in four_taxa_to_quartets.items():
            most_common = quartet_counter.most_common()
            if len(most_common) == 1:
                q, n = most_common[0]
                quartets[q] += n
            if most_common[0][1] > most_common[1][1]:
                q, n = most_common[0]
                quartets[q] += n
        return quartets


def main():
    print("GO")


if __name__ == "__main__":
    main()
