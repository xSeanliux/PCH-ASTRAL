#!/bin/bash
# TOB-QMC tree-of-blobs inference: PCH-W quartets in, one unrooted tree out whose
# polytomies are blobs. Writes <output>/TOB_QMC/trees/<name>.tree.
RUNID=""
INPUT=""
TREEOUTPUT=""
NAME=""
# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -H|--runid) RUNID="$2"; shift ;;
        -i|--input) INPUT="$2"; shift ;;
        -o|--output) TREEOUTPUT="$2"; shift ;;
        -n|--name) NAME="$2"; shift ;;
        -h|--help)
            echo "Usage: $0 -H <runid> -i <input> -o <output> -n <name>"
            echo ""
            echo "Required:"
            echo "  -H, --runid        Run ID"
            echo "  -i, --input        Input characters CSV"
            echo "  -o, --output       Output dir"
            echo "  -n, --name         Run name; names the output files"
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

# ponytail: TREE-QMC defaults (--alpha 1e-7 --beta 0.95, bipartition search capped
# at 2n^2 subsets). Needs a TREE-QMC built with R (install_w_tree_qmc.sh does).
bin/tree-qmc --blob \
    -i "$SCRATCH_QUARTET_PATH" \
    -o "$TREEOUTPUT/TOB_QMC/trees/$NAME.tree" \
    --override
rc=$?

echo "✅ TOB-QMC tree of blobs"
exit $rc
