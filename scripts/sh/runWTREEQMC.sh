#!/bin/bash
# CLI variant for weighted TREE-QMC: generates PCH-W quartets, then infers a
# tree with TREE-QMC. Writes into the folder named by -V (e.g. PCH_W_W_TREE_QMC);
# the runner (scripts/lib/inference/runners/w_tree_qmc.py) is the single source
# of truth for that name.
# Initialize variables with defaults
RUNID=""
INPUT=""
TREEOUTPUT=""
NAME=""
VARIANT=""
NORMALISATION="2"  # TREE-QMC --norm_atax; only 0 and 2 valid for quartet input
# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -H|--runid) RUNID="$2"; shift ;;
        -i|--input) INPUT="$2"; shift ;;
        -o|--output) TREEOUTPUT="$2"; shift ;;
        -n|--name) NAME="$2"; shift ;;
        -V|--variant) VARIANT="$2"; shift ;;
        -N|--normalisation) NORMALISATION="$2"; shift ;;
        -h|--help)
            echo "Usage: $0 -H <runid> -i <input> -o <output> -n <name> -V <variant> [-N <0|2>]"
            echo ""
            echo "Required:"
            echo "  -H, --runid           Run ID"
            echo "  -i, --input           Input characters CSV"
            echo "  -o, --output          Output dir"
            echo "  -n, --name            Dataset name"
            echo "  -V, --variant         Output folder name (e.g. PCH_W_W_TREE_QMC)"
            echo ""
            echo "Optional:"
            echo "  -N, --normalisation   --norm_atax scheme, 0 or 2 (default 2)"
            exit 0
            ;;
        *)
            echo "Unknown parameter passed: $1"
            echo "Use -h or --help for usage"
            exit 1
            ;;
    esac
    shift
done

# Check required arguments
if [[ -z "$RUNID" || -z "$INPUT" || -z "$NAME" || -z "$TREEOUTPUT" ]]; then
    echo "Error: --runid, --input, --name and --output must be provided."
    echo "Use -h or --help for usage."
    exit 1
fi
if [[ -z "$VARIANT" ]]; then
    echo "Error: --variant (-V) must be provided."
    exit 1
fi
if [[ "$NORMALISATION" != "0" && "$NORMALISATION" != "2" ]]; then
    echo "Normalisation (-N, --normalisation) must be 0 or 2, found $NORMALISATION"
    exit 1
fi

PCH_SCRATCH="${PCH_SCRATCH:-$HOME/scratch}"
mkdir -p "$PCH_SCRATCH"

mkdir -p "$TREEOUTPUT/$VARIANT/logs"
mkdir -p "$TREEOUTPUT/$VARIANT/trees"

SCRATCH_QUARTET_PATH="$PCH_SCRATCH/tmp_quartet_$RUNID.txt"

# PCH-W quartets in qfm format `((A,B),(C,D));weight` — TREE-QMC's default quartet format.
python3 -m scripts.lib.pch --input "$INPUT" --format qfm > "$SCRATCH_QUARTET_PATH" || exit 1
echo "✅ PCH-W quartet generation, $(wc -l "$SCRATCH_QUARTET_PATH" | awk '{ print $1 }') quartets"

bin/tree-qmc --quartets \
    -i "$SCRATCH_QUARTET_PATH" \
    -o "$TREEOUTPUT/$VARIANT/trees/$NAME.tree" \
    --norm_atax "$NORMALISATION" \
    --override
rc=$?

# PCH-W emits no quartet for a taxon that shares no informative state with another,
# so that taxon is absent from the tree. Warn when the leaf set is short of the input
# — a taxon-incomplete tree scores wrongly against the full model tree.
# ponytail: leaf count = commas+1 (no internal node labels); good enough to flag drift.
TREE_FILE="$TREEOUTPUT/$VARIANT/trees/$NAME.tree"
if [[ $rc -eq 0 && -s "$TREE_FILE" ]]; then
    N_TAXA=$(head -1 "$INPUT" | awk -F, '{ print NF - 3 }')
    N_LEAVES=$(($(tr -cd ',' < "$TREE_FILE" | wc -c) + 1))
    if [[ "$N_LEAVES" -ne "$N_TAXA" ]]; then
        echo "⚠️  tree has $N_LEAVES leaves but input has $N_TAXA taxa — PCH-W dropped uninformative taxa"
    fi
fi

echo "✅ weighted TREE-QMC tree inference"
exit $rc
