import sys
from pathlib import Path
from collections import defaultdict, Counter
from itertools import combinations
from typing import TextIO
import argparse

from scripts.lib.types import (
    Taxon,
    State,
    Quartet,
    QuartetGenerationScheme,
    Dataset,
)


class PCH_W(QuartetGenerationScheme):
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


class PCH_O(QuartetGenerationScheme):
    def get_quartets(cls, dataset: Dataset) -> Counter[Quartet]:
        quartets_w = PCH_W.get_quartets(dataset)
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


def print_quartets_for_astral3(quartets: Counter[Quartet], file: TextIO = sys.stdout):
    for q, w in quartets.items():
        file.write(f"{str(q)};\n" * w)


def print_quartets_for_wastral(
    quartets: Counter[Quartet],
    quartet_file: TextIO = sys.stdout,
    weight_file: TextIO = sys.stderr,
):
    for q, w in quartets.items():
        quartet_file.write(f"{str(q)};\n")
        weight_file.write(f"{w}\n")


def print_quartets_for_qfm(quartets: Counter[Quartet], file: TextIO = sys.stdout):
    for q, w in quartets.items():
        file.write(f"{str(q)};{w:.6f}\n")


def get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="PCH quartet generation",
        description="generates quartets from an input character file following the PCH-W quartet generation scheme. When format is astral3 or qfm outputs go to stderr; when format is qfm quartets output to stdout and weights go to stderr.",
    )
    parser.add_argument(
        "-i", "--input", action="store", required=True, help="input characters file"
    )
    parser.add_argument(
        "-f",
        "--format",
        action="store",
        required=True,
        choices=["astral3", "wastral", "qfm"],
        help="quartet output format.",
    )
    return parser


def main():
    parser = get_parser()
    args = parser.parse_args()
    quartet_fmt = args.format

    print(args.input)
    dataset = Dataset.from_path(path=Path(args.input))
    quartets = PCH_W.get_quartets(dataset)
    if quartet_fmt == "astral3":
        print_quartets_for_astral3(quartets)
    elif quartet_fmt == "wastral":
        print_quartets_for_wastral(quartets)
    elif quartet_fmt == "qfm":
        print_quartets_for_qfm(quartets)
    else:
        raise ValueError(f"Unknown format: {quartet_fmt}")


if __name__ == "__main__":
    main()
