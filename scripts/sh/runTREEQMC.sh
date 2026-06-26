#!/bin/bash
# TREE-QMC wrapper. CLI + quartet format VERIFIED end-to-end (bin/TREE-QMC/tree-qmc
# --quartets accepts "((A,B),(C,D));weight" and emits a species tree).
RUNID=""
INPUT=""
NAME=""
TREEOUTPUT=""
NORM=2
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -H|--runid) RUNID="$2"; shift ;;
        -i|--input) INPUT="$2"; shift ;;
        -o|--output) TREEOUTPUT="$2"; shift ;;
        -n|--name) NAME="$2"; shift ;;
        --norm) NORM="$2"; shift ;;
        -h|--help)
            echo "Usage: $0 --runid R --input <csv> --name N --output <dir> [--norm <0|1|2>]"
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
mkdir -p "$TREEOUTPUT/TREEQMC/trees"

# Weighted quartets: quartets -> stdout ("((A,B),(C,D));"), weights -> stderr.
QFILE="$PCH_SCRATCH/tmp_qmcquartet_$RUNID.txt"
WFILE="$PCH_SCRATCH/tmp_qmcweight_$RUNID.txt"
python3 -m scripts.py.printQuartets -i "$INPUT" -w \
    > "$QFILE" 2> "$WFILE"

# tree-qmc quartet input is "((A,B),(C,D));weight" per line. The -w quartets carry
# a trailing ';'; strip it and append ';weight' from the line-aligned weights file.
# awk, not `paste -d''` — BSD paste (macOS) mishandles the empty delimiter.
QMCFILE="$PCH_SCRATCH/tmp_qmcinput_$RUNID.txt"
awk 'NR==FNR{q[NR]=$0; next} {sub(/;[ \t]*$/,"",q[FNR]); print q[FNR] ";" $0}' \
    "$QFILE" "$WFILE" > "$QMCFILE"
echo "✅ TREE-QMC quartet generation, $(wc -l "$QMCFILE" | awk '{ print $1 }') quartets"

bin/TREE-QMC/tree-qmc --quartets -i "$QMCFILE" \
    -o "$TREEOUTPUT/TREEQMC/trees/$NAME.tree" \
    --norm_atax "$NORM" \
    2> "$TREEOUTPUT/TREEQMC/trees/$NAME.log"

echo "✅ TREE-QMC tree inference -> $TREEOUTPUT/TREEQMC/trees/$NAME.tree"
