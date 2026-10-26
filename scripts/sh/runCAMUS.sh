#!/bin/bash
# CAMUS network inference: --quartets plus one rooted guide tree in, one
# network per k out. Writes CAMUS's raw <output>/<DIR>/networks/<name>.csv (also
# .log, .png); DIR is CAMUS, or CAMUS_BIDIRECTIONAL with -B. CamusRunner.execute
# converts it to <name>.family.csv.
# Initialize variables with defaults
RUNID=""
INPUT=""
TREEOUTPUT=""
NAME=""
QUARTETS=""
GUIDE=""
OUTGROUP=""
BIDIRECTIONAL=""
# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -H|--runid) RUNID="$2"; shift ;;
        -i|--input) INPUT="$2"; shift ;;
        -o|--output) TREEOUTPUT="$2"; shift ;;
        -n|--name) NAME="$2"; shift ;;
        -Q|--quartets) QUARTETS="$2"; shift ;;
        -g|--guide-tree) GUIDE="$2"; shift ;;
        -O|--outgroup) OUTGROUP="$2"; shift ;;
        -B|--bidirectional) BIDIRECTIONAL="-B" ;;
        -h|--help)
            echo "Usage: $0 -H <runid> -i <input> -o <output> -n <name> -Q <quartets> -g <guide> -O <outgroup> [-B]"
            echo ""
            echo "Required:"
            echo "  -H, --runid        Run ID"
            echo "  -i, --input        Input characters CSV"
            echo "  -o, --output       Output dir"
            echo "  -n, --name         Run name; names the output files"
            echo "  -Q, --quartets     Quartet file, one per line per unit of weight"
            echo "  -g, --guide-tree   Guide tree, e.g. pch_astral3 or true_tree"
            echo "                     (all: CAMUS_GUIDE_TREES in scripts/lib/model/guide_tree.py)"
            echo "  -O, --outgroup     Outgroup taxon; the guide tree is rooted on it"
            echo ""
            echo "Optional:"
            echo "  -B, --bidirectional  Pass CAMUS -B (bidirectional search)"
            echo ""
            echo "Environment:"
            echo "  PCH_CAMUS_PROCS    CAMUS parallel processes (default 1)"
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
if [[ -z "$RUNID" || -z "$INPUT" || -z "$NAME" || -z "$QUARTETS" || -z "$TREEOUTPUT" || -z "$GUIDE" || -z "$OUTGROUP" ]]; then
    echo "Error: --runid, --input, --name, --quartets, --output, --guide-tree and --outgroup must be provided."
    echo "Use -h or --help for usage."
    exit 1
fi

PCH_SCRATCH="${PCH_SCRATCH:-$HOME/scratch}"
mkdir -p "$PCH_SCRATCH"

# Two methods, two dirs: same run names never collide.
DIR=CAMUS
[[ -n "$BIDIRECTIONAL" ]] && DIR=CAMUS_BIDIRECTIONAL
mkdir -p "$TREEOUTPUT/$DIR/logs"
mkdir -p "$TREEOUTPUT/$DIR/networks"

SCRATCH_GUIDE_PATH="$PCH_SCRATCH/tmp_guide_$RUNID.tree"

python3 -m scripts.py.guide_tree --guide "$GUIDE" --input "$INPUT" --output "$TREEOUTPUT" \
    --outgroup "$OUTGROUP" \
    > "$SCRATCH_GUIDE_PATH" || exit 1
echo "✅ guide tree ($GUIDE), rooted on $OUTGROUP"

# No -t: CAMUS's default quartet filter applies.
bin/camus -n "${PCH_CAMUS_PROCS:-1}" $BIDIRECTIONAL \
    -o "$TREEOUTPUT/$DIR/networks/$NAME" \
    "$SCRATCH_GUIDE_PATH" \
    "$QUARTETS" || exit 1
echo "✅ CAMUS network inference"
