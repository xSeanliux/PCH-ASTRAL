from pathlib import Path
import polars as pl
from scripts.lib.types import Dataset, Character

ds = Dataset.from_path(
    Path(
        "/Users/liusean/Desktop/Projects/Coding/Phylo/PCH-ASTRAL/data/rt_2025_poly_screened_lv_1.csv"
    )
)


def _is_phon(c: Character) -> bool:
    return c.feature[0] == "P"


def _is_morph(c: Character) -> bool:
    return c.feature[0] == "M"


def _is_lex(c: Character) -> bool:
    return not _is_morph(c) and not _is_phon(c)


def _is_poly(c: Character) -> bool:
    return any(len(z) > 1 for z in c.features.values())


def get_type(c: Character) -> str:
    if _is_morph(c):
        return "morphological"
    elif _is_phon(c):
        return "phonological"
    return "lexical"


features = [c.feature for c in ds.chrs]
is_phon = [_is_phon(c) for c in ds.chrs]
is_morph = [_is_morph(c) for c in ds.chrs]
is_lex = [_is_lex(c) for c in ds.chrs]
is_poly = [_is_poly(c) for c in ds.chrs]
type_chr = [get_type(c) for c in ds.chrs]

df = pl.DataFrame(
    data={
        "feature": features,
        # "is_phon": is_phon,
        # "is_morph": is_morph,
        # "is_lex": is_lex,
        "is_poly": is_poly,
        "character_type": type_chr,
    }
)

g = df.group_by(["character_type"]).agg(
    num_poly_characters=pl.col("is_poly").sum(),
    num_characters=pl.col("is_poly").len(),
)

breakpoint()
