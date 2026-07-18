#!/bin/bash
# CLI variant of runASTRAL.sh: writes into the folder named by -V (e.g.
# PCH_W_W_TREE_QMC). The runner (scripts/lib/inference/runners.py) is the
# single source of truth for that name.
# Initialize variables with defaults
RUNID=""
INPUT=""
TREEOUTPUT=""
NAME=""
VARIANT=""
NORMALISATION="2"
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
            echo "Usage: $0 -H <runid> -i <input> -o <output> -n <name> -V <variant> [-x]"
            echo ""
            echo "Required:"
            echo "  -H, --runid           Run ID"
            echo "  -i, --input           Input file or value"
            echo "  -o, --output          Output dir (required)"
            echo "  -n, --name            Dataset name"
            echo "  -V, --variant         Output folder name (e.g. PCH_W_W_TREE_QMC)"
            echo ""
            echo "Optional:"
            echo "  -N, --normalisation         Normalisation scheme (default 2, also takes 0)"
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
if [[ "$NORMALISATION" != "n0" && "$NORMALISATION" != "n2" ]]; then 
    echo "Normalisation scheme (-N, --normalisation) must be n0 or n2, found $NORMALISATION"
    exit 1
fi 

PCH_SCRATCH="${PCH_SCRATCH:-$HOME/scratch}"
mkdir -p "$PCH_SCRATCH"

mkdir -p "$TREEOUTPUT/$VARIANT/logs"
mkdir -p "$TREEOUTPUT/$VARIANT/trees"

SCRATCH_QUARTET_PATH="$PCH_SCRATCH/tmp_quartet_$RUNID.txt"

python3 -m scripts.lib.pch --input "$INPUT" --format qfm > "$SCRATCH_QUARTET_PATH" || exit 1
echo "✅ PCH-W quartet generation, $(wc -l "$SCRATCH_QUARTET_PATH" | awk '{ print $1 }') quartets"

bin/tree-qmc -i "$SCRATCH_QUARTET_PATH" \
    -o "$TREEOUTPUT/$ASTRAL_VARIANT/trees/$NAME.tree" \
    --norm_atax $NORMALISATION

echo "✅ W TREE QMC tree inference"
exit $rc
