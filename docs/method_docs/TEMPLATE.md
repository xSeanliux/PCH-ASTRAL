<!--
Method doc template for tree and network inference methods. Copy to
docs/method_docs/<method>/README.md and fill every section;
delete a section only if it truly does not apply (say why in one line instead).
Example (network): docs/method_docs/snaq/README.md.

Rules:
- Every statement must match the code or a source you checked. Cite files (`path`) and
  functions (`name`) so readers can verify.
- Anything taken from a paper but not verified goes under "Unverified", never as fact.
- Brief: if removing a word loses nothing, remove it. Tables over prose for settings.
- Delete these comments when done.
-->

# <Method name>

<One paragraph: what the method is (full name, citation), what it infers (a tree, or a
network and its class), and why we run it here (baseline for X, part of Y). End with:
Method key: `<key>`; kind: tree | network.>

## What it computes

<!-- The algorithm, not our wrapper. One bullet each; omit what does not apply. -->

- **Input:** <what the tool consumes, e.g. quartets, CFs, a character matrix, gene trees>
- **Model:** <the model assumed, e.g. MSC, NMSC, parsimony, Mk>
- **Objective:** <what is optimised; which direction is better; the name of the reported score>
- **Search:** <exact / heuristic; moves; restarts or runs; what "best" means>
- **Output:** <tree (rooted/unrooted, binary?) or network (class, rooted/semi-directed);
  branch lengths, support, γ>

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

## Normalising to the pipeline contract

<!--
Every runner reports a point estimate and, optionally, a group estimate (`Runner` in
scripts/lib/inference/runners/base.py). Keep the subsection for your method's kind and delete
the other. Either way, say how the "best" result is chosen and rooted, step by step, with the
edge cases (no result, ties, failed optimisation) and the run status then.
-->

### Tree method

**Point estimate: <one newick, e.g. the search's best tree or a consensus>.**
`get_point_estimate_path` → `point_estimate_newick` in the registry.

1. <how it is produced or chosen; rooting (rooted? on the outgroup?); polytomies>
2. <edge case and outcome>

**Group estimate: <tree set, e.g. MP4's equally parsimonious trees, GA's posterior sample; or
none>.** `get_group_estimate_path`, format <NEXUS / newick list>. The point estimate
summarises it by `get_consensus_method()` = <`MAJORITY` | `MCC` | `MAP` | `PASSTHROUGH` |
none> (<burn-in, thresholds>).

### Network method

**Point estimate: <rule in one phrase, e.g. the best network rootable on the outgroup>.**
`get_point_estimate_path`; omit it (`None`) if the method has no single pick.

1. <step>
2. <edge case and outcome; `is_point_estimate_optional`?>

**Group estimate: `N.family.csv`** (`NETWORK_FAMILY_SCHEMA`, docs/SCHEMAS.md), one row per
<network the tool reports>.

| Column | Value |
|---|---|
| `edges_added` | <how computed> |
| `network_newick` | <as written; which row holds the point estimate> |
| `is_best` | <which row(s); at most one per `edges_added`> |
| `<extra>` | <method-specific score; direction; null cases> |

### Rejected alternatives

- <option>: <why not>

## Scoring

<!-- Keep the line for your method's kind. -->

- Tree: `score` reads `point_estimate_newick` and compares it with the base tree via RF
  (`RFScorer.R`). <rooting / polytomy notes>
- Network: `network-score` reads the `is_best` rows, strips lengths and γ, and runs CmpNets
  `-m cluster` against the true network. `guide_tree` holds <the guide, or null>.

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
