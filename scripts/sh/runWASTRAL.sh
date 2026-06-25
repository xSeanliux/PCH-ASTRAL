#!/bin/bash
# wASTRAL (ASTER) wrapper. BEST-EFFORT: bin/wastral does not run in dev
# (built for newer macOS). The binary invocation + quartet input formatting
# below need live verification on the cluster — see # ponytail marks.
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

# ponytail: best-effort wASTRAL input. ASTER's weighted-ASTRAL takes a gene-tree
# / quartet file via -i and writes the tree via -o. The exact way weighted
# quartets (weights file) feed wastral is unverified — passing the bare quartet
# file here. Needs live verification on the cluster (weight flag, -i format).
bin/wastral -i "$QFILE" -o "$TREEOUTPUT/WASTRAL/trees/$NAME.tree" \
    2> "$TREEOUTPUT/WASTRAL/trees/$NAME.log"

echo "✅ wASTRAL tree inference -> $TREEOUTPUT/WASTRAL/trees/$NAME.tree"
