#!/bin/bash
# NetCS network inference: --quartets and --tree-of-blobs in. Writes
# <output>/NETCS/networks/<name>.net:
# one eNewick line, rooted wherever NetCS left it; NetcsRunner.execute then reroots it
# on the outgroup if it can be.
RUNID=""
INPUT=""
TREEOUTPUT=""
NAME=""
QUARTETS=""
TOB_PATH=""
# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -H|--runid) RUNID="$2"; shift ;;
        -i|--input) INPUT="$2"; shift ;;
        -o|--output) TREEOUTPUT="$2"; shift ;;
        -n|--name) NAME="$2"; shift ;;
        -Q|--quartets) QUARTETS="$2"; shift ;;
        -T|--tree-of-blobs) TOB_PATH="$2"; shift ;;
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

if [[ -z "$RUNID" || -z "$INPUT" || -z "$NAME" || -z "$QUARTETS" || -z "$TOB_PATH" || -z "$TREEOUTPUT" ]]; then
    echo "Error: --runid, --input, --name, --quartets, --tree-of-blobs and --output must be provided."
    echo "Use -h or --help for usage."
    exit 1
fi

PCH_SCRATCH="${PCH_SCRATCH:-$HOME/scratch}"
mkdir -p "$PCH_SCRATCH" "$TREEOUTPUT/NETCS/logs" "$TREEOUTPUT/NETCS/networks"

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
