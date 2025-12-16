#!/bin/bash
# Initialize variables with defaults
RUNID=""
INPUT=""
QUARTET=10
BIPARTITIONS=5
TREEOUTPUT=""
RUN_EXACT=""
NAME=""
THREADS=1
# Parse arguments

# OLD_PWD=$(pwd)
# cd $TALLIS/bin/ASTER
# make wastral
# cd $OLD_PWD

while [[ "$#" -gt 0 ]]; do
    case $1 in
        -H|--runid) RUNID="$2"; shift ;;
        -i|--input) INPUT="$2"; shift ;;
        -o|--output) TREEOUTPUT="$2"; shift ;;
        -n|--name) NAME="$2"; shift ;;
        -q|--quartet) QUARTET="$2"; shift ;;
        -t|--threads) THREADS="$2"; shift ;;
        -h|--help)
            echo "Usage: $0 -H <runid> -i <input> [-q <quartet>] [-x]"
            echo ""
            echo "Required:"
            echo "  -H, --runid           Run ID"
            echo "  -i, --input           Input file or value"
            echo ""
            echo "Optional:"
            echo "  -q, --quartet         Quartet value (default: 10)"
            echo "  -b, --bipartitions    Bipartitions value (default: 5)"
            echo "  -x, --exact           Enable exact mode (sets RUN_EXACT='-x')"
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
if [[ -z "$RUNID" || -z "$INPUT" ]]; then
    echo "Error: Both --runid and --input must be provided."
    echo "Use -h or --help for usage."
    exit 1
fi # Check required arguments

QUARTET_FILE=~/scratch/tmp_quartet_$RUNID.txt
QUARTET_WEIGHT_FILE=~/scratch/tmp_qweights_$RUNID.txt
python3 scripts/py/printQuartets.py\
    -i $INPUT\
    --waster \
    -q $QUARTET > $QUARTET_FILE 2> $QUARTET_WEIGHT_FILE
echo "✅ ASTRAL quartet generation, $(wc -l $QUARTET_FILE) quartets"
echo "✅ ASTRAL quartet generation, $(wc -l $QUARTET_WEIGHT_FILE) weights"

GUIDETREE=~/scratch/tmp_guidetrees_$RUNID.trees
python3 scripts/py/getResultBipartitions.py\
    -f $TREEOUTPUT\
    -n $NAME\
    -m -g > $GUIDETREE

echo "Guide Trees saved to "~/scratch/tmp_guidetrees_$RUNID.trees
echo "✅ ASTRAL-IV get guide trees" 

ASTRAL_VARIANT=ASTRAL4\($QUARTET\)
echo $TREEOUTPUT
echo $NAME

mkdir -p "$TREEOUTPUT/$ASTRAL_VARIANT/trees"
mkdir -p "$TREEOUTPUT/$ASTRAL_VARIANT/logs"

echo "" > "$TREEOUTPUT/$ASTRAL_VARIANT/trees/$NAME.tree"
echo Will output to $TREEOUTPUT/$ASTRAL_VARIANT/trees/$NAME.tree

ASTER/bin/wastral\
    -o "$TREEOUTPUT/$ASTRAL_VARIANT/trees/$NAME.tree"\
    -g "$GUIDETREE"\
    -i "$QUARTET_FILE"\
    -t "$THREADS"\
    --treeweights "$QUARTET_WEIGHT_FILE"\
    --mode 4\
    -R \
    > "$TREEOUTPUT/$ASTRAL_VARIANT/logs/$NAME.log" 2>&1

echo "✅ ASTRAL-IV tree inference"
