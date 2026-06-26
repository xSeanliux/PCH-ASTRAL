#!/bin/bash
# wASTRAL (ASTER) wrapper. Verified to RUN (after build-from-source): wastral
# takes each PCH quartet as a 4-taxon gene tree via -i and per-tree weights via
# --treeweights, and emits a species tree.
# ponytail: OPEN QUESTION — passing the PCH quartet multiplicities via
# --treeweights produced output identical to unweighted on test data, so the
# correct way to weight PCH quartets in wASTRAL is unresolved (--treeweights vs
# repeating each quartet `weight` times vs branch support). Validate against the
# PCH methodology before trusting weighted results.
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

# Each quartet line is a 4-taxon gene tree (-i); weights go via --treeweights
# (see the OPEN QUESTION at the top re: whether this applies as intended).
bin/wastral -i "$QFILE" --treeweights "$WFILE" \
    -o "$TREEOUTPUT/WASTRAL/trees/$NAME.tree" \
    2> "$TREEOUTPUT/WASTRAL/trees/$NAME.log"

echo "✅ wASTRAL tree inference -> $TREEOUTPUT/WASTRAL/trees/$NAME.tree"
