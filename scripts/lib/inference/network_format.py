"""Contact network file -> Rich newick for PhyloNet.

`net{h}-{t}.txt`: line 1 the base tree, then one `cladeA;cladeB;time;strength`
line per contact event. Each event becomes two contact edges, one per direction
(docs/adr/0001), so a single-direction estimate cannot score 0 when h >= 1.
"""

import re

_LENGTH = re.compile(r":[-+0-9.eE]+")


def _wrap(tree: str, clade: str, wrapped: str) -> str:
    # Anchor on newick delimiters so `t2` never matches inside `t26`.
    pattern = re.compile(rf"(?<=[(,]){re.escape(clade)}(?=[:,)])")
    tree, n = pattern.subn(lambda _: wrapped, tree)
    if n != 1:
        raise ValueError(f"clade {clade!r} matched {n} times, want 1")
    return tree


def contact_network_to_rich_newick(text: str) -> str:
    """Line 1 of `text` is the base tree; each later line a contact event."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    tree = lines[0].rstrip(";")
    events: list[tuple[float, str, str]] = []
    for line in lines[1:]:
        a, b, time, _strength = line.split(";")
        events.append((float(time), a, b))
    # Earliest first: an ancestor branch's event wraps before a descendant's
    # clade is looked up, and the descendant is still an exact substring.
    for i, (_, a, b) in enumerate(sorted(events), start=1):
        tree = _wrap(tree, a, f"(({a})#H{2 * i},#H{2 * i - 1})")
        tree = _wrap(tree, b, f"(({b})#H{2 * i - 1},#H{2 * i})")
    return _LENGTH.sub("", tree) + ";"
