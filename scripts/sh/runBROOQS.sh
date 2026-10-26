#!/bin/bash
# BROOQS network inference: --quartets as gene trees plus the --tree-of-blobs
# (rooted on the outgroup); each polytomy becomes a cycle. Writes
# <output>/BROOQS/networks/<name>.net (eNewick, rooted on the outgroup).
RUNID=""
INPUT=""
TREEOUTPUT=""
NAME=""
QUARTETS=""
TOB=""
# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -H|--runid) RUNID="$2"; shift ;;
        -i|--input) INPUT="$2"; shift ;;
        -o|--output) TREEOUTPUT="$2"; shift ;;
        -n|--name) NAME="$2"; shift ;;
        -Q|--quartets) QUARTETS="$2"; shift ;;
        -T|--tree-of-blobs) TOB="$2"; shift ;;
        -h|--help)
            echo "Usage: $0 -H <runid> -i <input> -o <output> -n <name> -Q <quartets> -T <tree of blobs>"
            echo ""
            echo "Required:"
            echo "  -H, --runid        Run ID"
            echo "  -i, --input        Input characters CSV"
            echo "  -o, --output       Output dir"
            echo "  -n, --name         Run name; names the output files"
            echo "  -Q, --quartets     Quartet file, one per line per unit of weight"
            echo "  -T, --tree-of-blobs  tob_qmc tree of blobs"
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

if [[ -z "$RUNID" || -z "$INPUT" || -z "$NAME" || -z "$QUARTETS" || -z "$TOB" || -z "$TREEOUTPUT" ]]; then
    echo "Error: --runid, --input, --name, --quartets, --tree-of-blobs and --output must be provided."
    echo "Use -h or --help for usage."
    exit 1
fi

PCH_SCRATCH="${PCH_SCRATCH:-$HOME/scratch}"
mkdir -p "$PCH_SCRATCH" "$TREEOUTPUT/BROOQS/logs" "$TREEOUTPUT/BROOQS/networks"

NET="$TREEOUTPUT/BROOQS/networks/$NAME.net"
rm -f "$NET"  # a failed run must not leave a stale network

read -r _ OUTGROUP < <(python3 -m scripts.py.model_graph --input "$INPUT") || exit 1
[[ "$OUTGROUP" != none ]] || { echo "Error: BROOQS needs an outgroup (simulation.outgroup_label)"; exit 1; }
echo "✅ outgroup $OUTGROUP"

[[ -f "$TOB" ]] || { echo "Error: no tree of blobs at $TOB (run tob_qmc first)"; exit 1; }

# --rooted: never reroot (the default may reroot at an arbitrary leaf).
brooqs \
    -i "$QUARTETS" \
    -t "$TOB" \
    -o "$NET" \
    --rooted || exit
echo "✅ BROOQS network inference"
