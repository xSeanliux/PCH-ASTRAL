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
from scripts.lib.model.strategies import QuartetGenerationStrategy


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


class PCH_W_N(QuartetGenerationScheme):
    """
    This is PCH-W-N. The N stands for Network, and reflects the fact that this method is meant to be an input to Networks.
    PCH-W-N only differs in one place from PCH-W: ab|cd is still a split if ab and cd share a state. This is done so that we are able to capture
    phylogenetic _network_ signal, as opposed to attempting to capture purely tree signal as is with PCH-W.
    """

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
                quartets.update(
                    [
                        Quartet((a, b, c, d))
                        for a, b in combinations(t1s, 2)
                        for c, d in combinations(t2s, 2)
                        if not {a, b} & {c, d}  # a quartet needs four taxa
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


STRATEGY_TO_SCHEME: dict[QuartetGenerationStrategy, type[QuartetGenerationScheme]] = {
    QuartetGenerationStrategy.PCH_W: PCH_W,
    QuartetGenerationStrategy.PCH_W_N: PCH_W_N,
}


def print_quartets_for_astral3(quartets: Counter[Quartet], file: TextIO = sys.stdout):
    """Write each quartet once per count, in sorted order.

    :param quartets: Quartet counts.
    :param file: Output stream.
    """
    for q, w in sorted(quartets.items()):
        file.write(f"{str(q)};\n" * w)


def print_quartets_for_wastral(
    quartets: Counter[Quartet],
    quartet_file: TextIO = sys.stdout,
    weight_file: TextIO = sys.stderr,
):
    """Write sorted quartets and their counts to line-paired streams.

    :param quartets: Quartet counts.
    :param quartet_file: Stream for quartets.
    :param weight_file: Stream for counts.
    """
    for q, w in sorted(quartets.items()):
        quartet_file.write(f"{str(q)};\n")
        weight_file.write(f"{w}\n")


def print_quartets_for_qfm(quartets: Counter[Quartet], file: TextIO = sys.stdout):
    """Write ``quartet;count`` lines, in sorted order.

    :param quartets: Quartet counts.
    :param file: Output stream.
    """
    for q, w in sorted(quartets.items()):
        file.write(f"{str(q)};{w:.6f}\n")


def get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="PCH quartet generation",
        description="generates quartets from an input character file following the PCH-W quartet generation scheme. Quartets go to stdout (astral3: repeated per weight; qfm: `quartet;weight`); in wastral mode weights go to stderr.",
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
