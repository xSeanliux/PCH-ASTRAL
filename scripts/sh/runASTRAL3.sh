#!/bin/bash
# CLI variant of runASTRAL.sh: writes into PCH_ASTRAL_3(Q,B) instead of
# ASTRAL(Q,B). Legacy runASTRAL.sh is kept as-is for the old bash pipeline.
# Quartet-based methods follow the PCH_<METHOD>(<params>) folder convention.
# Initialize variables with defaults
RUNID=""
INPUT=""
QUARTET=11
BIPARTITIONS=5
TREEOUTPUT=""
RUN_EXACT=""
NAME=""
# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -H|--runid) RUNID="$2"; shift ;;
        -i|--input) INPUT="$2"; shift ;;
        -o|--output) TREEOUTPUT="$2"; shift ;;
        -n|--name) NAME="$2"; shift ;;
        -q|--quartet) QUARTET="$2"; shift ;;
        -b|--bipartitions) BIPARTITIONS="$2"; shift ;;
        -x|--exact) RUN_EXACT="-x" ;;  # Store "-x" if present
        -h|--help)
            echo "Usage: $0 -H <runid> -i <input> [-q <quartet>] [-b <bipartitions>] [-x]"
            echo ""
            echo "Required:"
            echo "  -H, --runid           Run ID"
            echo "  -i, --input           Input file or value"
            echo ""
            echo "Optional:"
            echo "  -q, --quartet         Quartet value (default: 11)"
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
fi

PCH_SCRATCH="${PCH_SCRATCH:-$HOME/scratch}"
mkdir -p "$PCH_SCRATCH"

ASTRAL_VARIANT=PCH_ASTRAL_3\("$QUARTET","$BIPARTITIONS"\)
mkdir -p $TREEOUTPUT/$ASTRAL_VARIANT/logs
mkdir -p $TREEOUTPUT/$ASTRAL_VARIANT/trees

python3 -m scripts.py.printQuartets -i "$INPUT" > "$PCH_SCRATCH/tmp_quartet_$RUNID.txt"
echo "✅ ASTRAL quartet generation, $(wc -l "$PCH_SCRATCH/tmp_quartet_$RUNID.txt" | awk '{ print $1 }') quartets"

ASTRAL_VARIANT=PCH_ASTRAL_3\($QUARTET,$BIPARTITIONS\)
echo $TREEOUTPUT
echo $NAME
echo $RUN_EXACT

if [[ $RUN_EXACT == "-x" ]]; then
    echo "Running in exact mode. No bipartitions used."
    touch "$PCH_SCRATCH/tmp_bipartitions_$RUNID.bootstrap.trees"
else :

    python3 -m scripts.py.getResultBipartitions\
        -f "$TREEOUTPUT"\
        -n "$NAME"\
        -m -g > "$PCH_SCRATCH/tmp_bipartitions_$RUNID.bootstrap.trees"

    echo "Bipartitions saved to $PCH_SCRATCH/tmp_bipartitions_$RUNID.bootstrap.trees"
    echo "✅ Heuristic ASTRAL Get bipartitions"
fi

echo "" > $TREEOUTPUT/$ASTRAL_VARIANT/trees/$NAME.tree
echo TEST, will output to $TREEOUTPUT/$ASTRAL_VARIANT/trees/$NAME.tree

java -jar -Xmx512g ASTRAL/Astral/astral.5.7.8.jar\
    -o $TREEOUTPUT/$ASTRAL_VARIANT/trees/$NAME.tree\
    -f "$PCH_SCRATCH/tmp_bipartitions_$RUNID.bootstrap.trees"\
    -i "$PCH_SCRATCH/tmp_quartet_$RUNID.txt"\
    -t 1\
    $RUN_EXACT\
    > /dev/null 2> $TREEOUTPUT/$ASTRAL_VARIANT/logs/$NAME.log # Run ASTRAL in default mode

echo "✅ Heuristic ASTRAL tree inference"
