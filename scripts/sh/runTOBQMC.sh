#!/bin/bash
# TOB-QMC tree-of-blobs inference: PCH-W quartets in, one tree out (polytomies are
# blobs; rooted on the outgroup, if any). Writes <output>/TOB_QMC/trees/<name>.tree.
RUNID=""
INPUT=""
TREEOUTPUT=""
NAME=""
ALPHA=""
SEARCH_3F1A=""
# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -H|--runid) RUNID="$2"; shift ;;
        -i|--input) INPUT="$2"; shift ;;
        -o|--output) TREEOUTPUT="$2"; shift ;;
        -n|--name) NAME="$2"; shift ;;
        -a|--alpha) ALPHA="$2"; shift ;;
        --3f1a) SEARCH_3F1A="--3f1a" ;;
        -h|--help)
            echo "Usage: $0 -H <runid> -i <input> -o <output> -n <name> [-a <alpha>] [--3f1a]"
            echo ""
            echo "Required:"
            echo "  -H, --runid        Run ID"
            echo "  -i, --input        Input characters CSV"
            echo "  -o, --output       Output dir"
            echo "  -n, --name         Run name; names the output files"
            echo ""
            echo "Optional:"
            echo "  -a, --alpha        QTT level; TREE-QMC default 1e-7"
            echo "  --3f1a             3-fix-1-alter min p-value search (TOB-QMC paper)"
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

if [[ -z "$RUNID" || -z "$INPUT" || -z "$NAME" || -z "$TREEOUTPUT" ]]; then
    echo "Error: --runid, --input, --name and --output must be provided."
    echo "Use -h or --help for usage."
    exit 1
fi

PCH_SCRATCH="${PCH_SCRATCH:-$HOME/scratch}"
mkdir -p "$PCH_SCRATCH"

mkdir -p "$TREEOUTPUT/TOB_QMC/logs"
mkdir -p "$TREEOUTPUT/TOB_QMC/trees"

SCRATCH_QUARTET_PATH="$PCH_SCRATCH/tmp_quartet_$RUNID.txt"

# PCH-W quartets, each once per unit of weight, as 4-taxon gene trees: TOB-QMC's
# hypothesis tests read quartet counts off its gene trees, so repeats are counts.
python3 -m scripts.py.printQuartets -i "$INPUT" > "$SCRATCH_QUARTET_PATH" || exit 1
echo "✅ PCH-W quartet generation, $(wc -l "$SCRATCH_QUARTET_PATH" | awk '{ print $1 }') quartets"

# The lookup fails on non-simulated data (or a broken registry): run unrooted.
LOOKUP_ERR="$PCH_SCRATCH/tmp_outgroup_$RUNID.err"
read -r _ OUTGROUP < <(python3 -m scripts.py.model_graph --input "$INPUT" 2>"$LOOKUP_ERR") \
    || echo "Warning: no outgroup, unrooted: $(tail -n 1 "$LOOKUP_ERR")"
[[ "$OUTGROUP" != none ]] || OUTGROUP=""

# -w f: unweighted, fast algorithm; same tree as -w n on PCH-W quartets (binary, so
# nothing to refine arbitrarily). --beta 0.95 and the 2n^2 bipartition-search cap stay
# at TREE-QMC's defaults. Needs a TREE-QMC built with R (install_w_tree_qmc.sh does).
bin/tree-qmc --blob ${OUTGROUP:+--root "$OUTGROUP"} ${ALPHA:+--alpha "$ALPHA"} $SEARCH_3F1A -w f \
    -i "$SCRATCH_QUARTET_PATH" \
    -o "$TREEOUTPUT/TOB_QMC/trees/$NAME.tree" \
    --override
rc=$?

echo "✅ TOB-QMC tree of blobs"
exit $rc
