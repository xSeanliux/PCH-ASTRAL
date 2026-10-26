#!/bin/bash
# NetCS network inference: --quartets and the tob_qmc tree of blobs
# (<output>/TOB_QMC/trees/<input stem>.tree) in. Writes <output>/NETCS/networks/<name>.net:
# one eNewick line, rooted wherever NetCS left it; NetcsRunner.execute then reroots it
# on the outgroup if it can be.
RUNID=""
INPUT=""
TREEOUTPUT=""
NAME=""
QUARTETS=""
# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -H|--runid) RUNID="$2"; shift ;;
        -i|--input) INPUT="$2"; shift ;;
        -o|--output) TREEOUTPUT="$2"; shift ;;
        -n|--name) NAME="$2"; shift ;;
        -Q|--quartets) QUARTETS="$2"; shift ;;
        -h|--help)
            echo "Usage: $0 -H <runid> -i <input> -o <output> -n <name> -Q <quartets>"
            echo ""
            echo "Required:"
            echo "  -H, --runid        Run ID"
            echo "  -i, --input        Input characters CSV"
            echo "  -o, --output       Output dir"
            echo "  -n, --name         Run name; names the output files"
            echo "  -Q, --quartets     Quartet file, one per line per unit of weight"
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

if [[ -z "$RUNID" || -z "$INPUT" || -z "$NAME" || -z "$QUARTETS" || -z "$TREEOUTPUT" ]]; then
    echo "Error: --runid, --input, --name, --quartets and --output must be provided."
    echo "Use -h or --help for usage."
    exit 1
fi

PCH_SCRATCH="${PCH_SCRATCH:-$HOME/scratch}"
mkdir -p "$PCH_SCRATCH" "$TREEOUTPUT/NETCS/logs" "$TREEOUTPUT/NETCS/networks"

# Per dataset: named by the input stem; $NAME may carry a run suffix.
STEM="${INPUT##*/}"
TOB_PATH="$TREEOUTPUT/TOB_QMC/trees/${STEM%.*}.tree"
NET_PATH="$TREEOUTPUT/NETCS/networks/$NAME.net"
rm -f "$NET_PATH"  # a failed run must not leave a stale network

read -r _ OUTGROUP < <(python3 -m scripts.py.model_graph --input "$INPUT") || exit 1
[[ "$OUTGROUP" != none ]] || { echo "Error: NetCS needs an outgroup (simulation.outgroup_label)"; exit 1; }

[[ -f "$TOB_PATH" ]] || { echo "Error: no tree of blobs $TOB_PATH (run tob_qmc first)"; exit 1; }
echo "✅ outgroup $OUTGROUP"

# Never --root (segfault) or --quartets (aborts on these lines). NetCS keeps the
# tree of blobs' root when valid, else reroots and still exits 0.
bin/tree-qmc --network \
    -i "$QUARTETS" \
    --at "$TOB_PATH" \
    -o "$NET_PATH" \
    --override || exit
[[ -s "$NET_PATH" ]] || { echo "Error: NetCS wrote no network"; exit 1; }
echo "✅ NetCS network inference"
