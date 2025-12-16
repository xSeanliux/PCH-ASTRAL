#!~/.conda/envs/phylo/bin/python
import argparse
from pathlib import Path
from Bio import Phylo
from scripts.lib.quartet_scorer import QuartetScorer
from scripts.lib.getQuartets import get_quartets
from itertools import product
from io import StringIO
import pandas as pd 

OMP = Path(__file__).parent.parent.parent

E_FACTORS = [0.8]
H_FACTORS = [0.1]
C_FACTORS = [0.25, 1]
POLYMORPHISM = ["no", "high"]
QUARTETS = [10]
# 10 is +K, 11 for -K
N_TREES = 8
N_REPLICAS = 1

TREESTRS = open(OMP / "example" / "all_simulated_data" / "trees.txt", "r").readlines()
TREEOBJS = map(lambda s: Phylo.read(StringIO(s), "newick"), TREESTRS)
QUARTETSCORERS = [
    QuartetScorer(tree)
    for tree in TREEOBJS
]

data = []

for qmode, ef, hf, cf, poly, tree, rep in product(
    QUARTETS, E_FACTORS, H_FACTORS, C_FACTORS, POLYMORPHISM, range(1, N_TREES + 1), range(1, N_REPLICAS + 1)
):
    print(f"{poly}\t{hf}\t{ef}\t{cf}\t{tree}\t{rep}")
    scorer = QUARTETSCORERS[tree - 1]
    data_path = OMP / "example" / "simulated_data_theorypaper" / f"{poly}_{hf}_{ef}_{cf}"/ f"sim_tree{tree}_{rep}.csv"

    _, quartets = get_quartets( 
        csv_path = data_path,
        mode = qmode,
    )

    print(f"{len(quartets)} distinct quartets found with a total weight of {sum(quartets.values())}.")

    astral_log_path = OMP / "sim_outputs_theorypaper" / f"{poly}_{hf}_{ef}_{cf}" / f"ASTRAL({qmode},5)" / "logs"/ f"sim_tree{tree}_{rep}.log"

    with open(astral_log_path, "r") as af: 
        lines = af.readlines()
        fqsl = [
            line for line in lines if line.startswith("Final quartet score is:")
        ]
        assert len(fqsl) == 1
        astral_quartet_score = int(fqsl[0].strip().split()[-1])



    score = 0
    total_quartets = 0
    for q, w in quartets.items():
        total_quartets += w
        if scorer.test_quartet(q):
            score += w
        else: 
            print(f"FOUND INCOMPATIBLE: {q} <-> {TREESTRS[tree - 1]}")
            print(f"{poly}\t{hf}\t{ef}\t{cf}\t{tree}\t{rep}")
            input("Enter to ack")

    assert total_quartets == sum(quartets.values())
    
    data.append((
        len(quartets),
        total_quartets,
        score, 
        astral_quartet_score,
        score / total_quartets,
        astral_quartet_score / total_quartets,
        poly,
        hf,
        ef,
        cf,
        qmode,
        tree,
        rep,
    ))
    print(f"{score}\t{astral_quartet_score}\t{total_quartets} = {score / total_quartets:.4f} \t{astral_quartet_score / total_quartets:.4f}.")


df = pd.DataFrame(
    data,
    columns = [
        "distinct_quartets",
        "total_quartets",
        "gold_quartet_count",
        "astral_quartet_count",
        "gold_quartet_score",
        "astral_quartet_score",
        "polymorphism",
        "hf",
        "ef",
        "cf",
        "qmode",
        "tree",
        "replica"
    ]
)

df.to_csv(OMP / "sim_outputs_theorypaper" / "astral_stats" / "astral_stats_master.csv", index=False)