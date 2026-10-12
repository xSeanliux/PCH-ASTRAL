#!/bin/bash
# BROOQS network inference: PCH-W quartets as gene trees plus the TOB-QMC tree of blobs
# (<output>/TOB_QMC/trees/<name>.tree, rooted on the outgroup); each polytomy becomes a
# cycle. Writes <output>/BROOQS/networks/<name>.net (eNewick, rooted on the outgroup);
# BrooqsRunner.execute then writes <name>.family.csv.
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
mkdir -p "$PCH_SCRATCH" "$TREEOUTPUT/BROOQS/logs" "$TREEOUTPUT/BROOQS/networks"

SCRATCH_QUARTET_PATH="$PCH_SCRATCH/tmp_quartet_$RUNID.txt"
TOB="$TREEOUTPUT/TOB_QMC/trees/$NAME.tree"
NET="$TREEOUTPUT/BROOQS/networks/$NAME.net"
rm -f "$NET"  # a failed run must not leave a stale network

read -r _ OUTGROUP < <(python3 -m scripts.py.model_graph --input "$INPUT") || exit 1
[[ "$OUTGROUP" != none ]] || { echo "Error: BROOQS needs an outgroup (simulation.outgroup_label)"; exit 1; }
echo "✅ outgroup $OUTGROUP"

[[ -f "$TOB" ]] || { echo "Error: no tree of blobs at $TOB (run tob_qmc first)"; exit 1; }
# Prefix test: tree-qmc --root writes the outgroup first.
[[ "$(<"$TOB")" == "($OUTGROUP,"* ]] || { echo "Error: tree of blobs $TOB is not rooted on $OUTGROUP"; exit 1; }

# PCH-W writes each quartet once per unit of weight; BROOQS reads repeats as counts.
python3 -m scripts.py.printQuartets -i "$INPUT" > "$SCRATCH_QUARTET_PATH" || exit 1
echo "✅ PCH-W quartet generation, $(wc -l < "$SCRATCH_QUARTET_PATH" | tr -d ' ') quartets"

# --rooted: never reroot (the default may reroot at an arbitrary leaf).
python3 bin/brooqs-src/count_quartets.py \
    -i "$SCRATCH_QUARTET_PATH" \
    -t "$TOB" \
    -o "$NET" \
    --rooted || exit
echo "✅ BROOQS network inference"
