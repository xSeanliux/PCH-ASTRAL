#!/bin/bash
# wASTRAL (ASTER) wrapper. VERIFIED end-to-end (build-from-source binary):
# each PCH quartet is a 4-taxon gene tree (-i); the per-quartet multiplicities are
# the gene-tree weights (--treeweights). MUST use --mode 4 (unweighted): the
# default hybrid mode (1) weights by branch support/length on the gene trees —
# which quartets don't have — and ignores --treeweights. Mode 4 applies the
# per-tree weights, and the weighted tree verifiably differs from the uniform one.
RUNID=""
INPUT=""
NAME=""
TREEOUTPUT=""
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -H|--runid) RUNID="$2"; shift ;;
        -i|--input) INPUT="$2"; shift ;;
        -o|--output) TREEOUTPUT="$2"; shift ;;
        -n|--name) NAME="$2"; shift ;;
        -h|--help)
            echo "Usage: $0 --runid R --input <csv> --name N --output <dir>"
            exit 0
            ;;
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
    shift
done

if [[ -z "$RUNID" || -z "$INPUT" || -z "$NAME" || -z "$TREEOUTPUT" ]]; then
    echo "Error: --runid, --input, --name, --output all required."
    exit 1
fi

PCH_SCRATCH="${PCH_SCRATCH:-$HOME/scratch}"
mkdir -p "$PCH_SCRATCH"
mkdir -p "$TREEOUTPUT/WASTRAL/trees"

# Weighted quartets: quartets -> stdout, weights -> stderr (line-aligned).
QFILE="$PCH_SCRATCH/tmp_wquartet_$RUNID.txt"
WFILE="$PCH_SCRATCH/tmp_wweight_$RUNID.txt"
python3 -m scripts.py.printQuartets -i "$INPUT" -w \
    > "$QFILE" 2> "$WFILE"
echo "✅ wASTRAL quartet generation, $(wc -l "$QFILE" | awk '{ print $1 }') quartets"

# --mode 4 (unweighted) so the PCH quartet weights in --treeweights are applied
# (hybrid mode would weight by support/length the quartets lack, ignoring them).
bin/wastral --mode 4 -i "$QFILE" --treeweights "$WFILE" \
    -o "$TREEOUTPUT/WASTRAL/trees/$NAME.tree" \
    2> "$TREEOUTPUT/WASTRAL/trees/$NAME.log"

echo "✅ wASTRAL tree inference -> $TREEOUTPUT/WASTRAL/trees/$NAME.tree"
