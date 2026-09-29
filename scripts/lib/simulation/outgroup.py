"""Graft an outgroup onto a base tree or a network, so inferred trees can be rooted.

Branch lengths follow Willson & Warnow (Bioinformatics 2026), supplementary 1.1:
outgroup branch U(0.9, 1.0), ingroup stem U(0.0, 0.1).
"""

import random


def graft_outgroup(newick: str, name: str, stem_len: float, og_len: float) -> str:
    """Wrap `newick` so `name` is sister to everything, preserving the terminator."""
    s = newick.strip()
    term = ";" if s.endswith(";") else ""
    return f"({s.rstrip(';')}:{stem_len},{name}:{og_len}){term}"


def graft_network(
    lines: list[str], name: str, stem_len: float, og_len: float
) -> list[str]:
    """Graft line 1 (the base tree) and move each contact `stem_len` later.

    A contact line is `cladeA;cladeB;time;strength`. Time counts from the root,
    and the stem pushes the old root `stem_len` away from the new one. The clades
    are left as they are: they are substrings of the base tree, which the wrap
    does not alter.
    """
    out = [graft_outgroup(lines[0], name, stem_len, og_len)]
    for line in lines[1:]:
        clade_a, clade_b, time, strength = line.strip().split(";")
        out.append(f"{clade_a};{clade_b};{float(time) + stem_len};{strength}")
    return out


def draw_lengths(seed: int) -> tuple[float, float]:
    """(stem_len, og_len), deterministic in `seed`."""
    rng = random.Random(seed)
    return rng.uniform(0.0, 0.1), rng.uniform(0.9, 1.0)
