import polars
from dataclasses import dataclass
from pathlib import Path

Quple = tuple[str, str, str, str]
Taxon = str
State = str


@dataclass
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


@dataclass
class Character:
    features: dict[Taxon, list[State]]
    weight: int


@dataclass
class Dataset:
    names: list[Taxon]
    chrs: list[Character]


def main():
    print("GO")


if __name__ == "__main__":
    main()
