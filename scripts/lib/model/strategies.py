from enum import IntEnum, StrEnum


class BipartitionStrategy(StrEnum):
    BINARY_CHARACTER = "binary_character"
    MP4_TREES = "mp4_trees"
    GA_TREES = "ga_trees"


class NormalisationStrategy(IntEnum):
    # Values are TREE-QMC --norm_atax args; only 0 and 2 valid for quartet input.
    N0 = 0
    N2 = 2
