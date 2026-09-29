#!/bin/bash
# CAMUS network inference: PCH-W quartets plus one rooted guide tree in, one
# network per k out. Writes <output>/CAMUS/networks/<name>.csv (also .log, .png).
# Initialize variables with defaults
RUNID=""
INPUT=""
TREEOUTPUT=""
NAME=""
GUIDE=""
# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -H|--runid) RUNID="$2"; shift ;;
        -i|--input) INPUT="$2"; shift ;;
        -o|--output) TREEOUTPUT="$2"; shift ;;
        -n|--name) NAME="$2"; shift ;;
        -g|--guide-tree) GUIDE="$2"; shift ;;
        -h|--help)
            echo "Usage: $0 -H <runid> -i <input> -o <output> -n <name> -g <guide>"
            echo ""
            echo "Required:"
            echo "  -H, --runid        Run ID"
            echo "  -i, --input        Input characters CSV"
            echo "  -o, --output       Output dir"
            echo "  -n, --name         Run name; names the output files"
            echo "  -g, --guide-tree   Guide tree: astral3, wastral or true_tree"
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
if [[ -z "$RUNID" || -z "$INPUT" || -z "$NAME" || -z "$TREEOUTPUT" || -z "$GUIDE" ]]; then
    echo "Error: --runid, --input, --name, --output and --guide-tree must be provided."
    echo "Use -h or --help for usage."
    exit 1
fi

PCH_SCRATCH="${PCH_SCRATCH:-$HOME/scratch}"
mkdir -p "$PCH_SCRATCH"

mkdir -p "$TREEOUTPUT/CAMUS/logs"
mkdir -p "$TREEOUTPUT/CAMUS/networks"

SCRATCH_QUARTET_PATH="$PCH_SCRATCH/tmp_quartet_$RUNID.txt"
SCRATCH_GUIDE_PATH="$PCH_SCRATCH/tmp_guide_$RUNID.tree"

# PCH-W writes each quartet once per unit of weight; CAMUS counts repeats.
python3 -m scripts.py.printQuartets -i "$INPUT" > "$SCRATCH_QUARTET_PATH" || exit 1
echo "✅ PCH-W quartet generation, $(wc -l "$SCRATCH_QUARTET_PATH" | awk '{ print $1 }') quartets"

python3 -m scripts.py.guide_tree --guide "$GUIDE" --input "$INPUT" --output "$TREEOUTPUT" \
    > "$SCRATCH_GUIDE_PATH" || exit 1
echo "✅ guide tree ($GUIDE), rooted"

# No -t: CAMUS's default quartet filter applies.
bin/camus -n "${PCH_CAMUS_PROCS:-1}" \
    -o "$TREEOUTPUT/CAMUS/networks/$NAME" \
    "$SCRATCH_GUIDE_PATH" \
    "$SCRATCH_QUARTET_PATH"
rc=$?

echo "✅ CAMUS network inference"
exit $rc
