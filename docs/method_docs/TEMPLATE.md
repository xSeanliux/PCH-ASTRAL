<!--
Method doc template. Copy to docs/method_docs/<method>/README.md and fill every section;
delete a section only if it truly does not apply (say why in one line instead).
Example: docs/method_docs/snaq/README.md.

Rules:
- Every statement must match the code or a source you checked. Cite files (`path`) and
  functions (`name`) so readers can verify.
- Anything taken from a paper but not verified goes under "Unverified", never as fact.
- Brief: if removing a word loses nothing, remove it. Tables over prose for settings.
- Delete these comments when done.
-->

# <Method name>

<One paragraph: what the method is (full name, citation), what it infers (tree / network
class), and why we run it here (baseline for X, part of Y). End with: Method key: `<key>`.>

## What it computes

<!-- The algorithm, not our wrapper. One bullet each; omit what does not apply. -->

- **Input:** <what the tool consumes, e.g. quartets, CFs, a character matrix, gene trees>
- **Model:** <the model assumed, e.g. MSC, NMSC, parsimony, Mk>
- **Objective:** <what is optimised; which direction is better; the name of the reported score>
- **Search:** <exact / heuristic; moves; restarts or runs; what "best" means>
- **Output:** <tree or network; rooted, unrooted or semi-directed; branch lengths, γ, support>

## How we run it

<!-- Call tree from the runner down to the tool, one line per step, with the file that owns it. -->

```text
<Runner>.execute                               scripts/lib/inference/runners/<method>.py
└── run<METHOD>.sh <args>                      scripts/sh/run<METHOD>.sh
    ├── <step>                → <product>      <what it is / where it comes from>
    └── <tool call>                            <binary or package, pinned version>
└── <post-processing>         → <file>         <converter, if any>
```

<Caveats about our inputs versus the model's assumptions, e.g. PCH-W weights are not locus
counts. One short paragraph, or delete.>

## Configuration

```yaml
methods:
  <dependency>: {}       # if the method consumes another method's output
  <key>:
    <field>: <example>   # <one-line meaning>
```

| Field | Meaning |
|---|---|
| `<field>` | <meaning; allowed values; default; whether it is part of `config_hash`> |

Fixed choices, not configurable:

| Choice | Value | Why |
|---|---|---|
| <parameter> | <value> | <reason: paper, tool default, reproducibility, oracle, ...> |

## Normalising to the <tree | network> contract

<!--
Tree methods: point estimate = one newick (`get_point_estimate_path`); group estimate = tree
set, if any, and how the point estimate summarises it (`get_consensus_method`).
Network methods: point estimate + family CSV (`NETWORK_FAMILY_SCHEMA`, docs/SCHEMAS.md).
Say how the "best" is chosen and how the result is rooted, step by step, including the
edge cases (no result, ties, failed optimisation) and what the run status is then.
-->

**Point estimate: <rule in one phrase>.**

1. <step>
2. <edge case and outcome>

**Group estimate: <file>, <one row / tree per ...>.**

| Column | Value |
|---|---|
| `edges_added` | <how computed> |
| `network_newick` | <as written? which row holds the point estimate?> |
| `is_best` | <which row(s)> |
| `<extra>` | <method-specific score, null cases> |

Rejected alternatives:
- <option>: <why not>

## Scoring

<Which scorer reads which estimate (RF on the point estimate, or `network-score` on
`is_best` rows), what is stripped first, the reference, and what `guide_tree` holds.>

## Outputs

`<cond>/<METHOD>/<dir>/`, with `N` = <run name>:

| File | Writer | Content |
|---|---|---|
| `N.<ext>` | <tool / script / runner> | <content> |

The run log is at `<cond>/<METHOD>/logs/N.log`.

## Runtime

<Measured times with dataset size and settings, what dominates the cost, and the knobs that
help, e.g. `procs`. Only numbers you measured; say where.>

## Versus <the source paper>

| | Paper | Here |
|---|---|---|
| <setting> | <value> (<source you checked>) | <value> |

Unverified: <settings or results not yet checked against the paper>.

## References

- <Authors> (<year>). <Title>. *<Venue>* <volume>(<issue>): <pages>.
  [doi:<doi>](https://doi.org/<doi>)
- <Tool>, pinned at <version>: [<repo>](<url>)
