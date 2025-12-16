#!/bin/bash
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
fi

ASTRAL_VARIANT=ASTRAL\("$QUARTET","$BIPARTITIONS"\)
mkdir -p $TREEOUTPUT/$ASTRAL_VARIANT/logs
mkdir -p $TREEOUTPUT/$ASTRAL_VARIANT/trees

python3 scripts/py/printQuartets.py\
    -i $INPUT\
    -q $QUARTET > ~/scratch/tmp_quartet_$RUNID.txt
echo "✅ ASTRAL quartet generation, $(wc -l ~/scratch/tmp_quartet_$RUNID.txt | awk '{ print $1 }') quartets"

ASTRAL_VARIANT=ASTRAL\($QUARTET,$BIPARTITIONS\)
echo $TREEOUTPUT
echo $NAME
echo $RUN_EXACT

if [[ $RUN_EXACT == "-x" ]]; then 
    echo "Running in exact mode. No bipartitions used." 
    touch ~/scratch/tmp_bipartitions_$RUNID.bootstrap.trees
else : 

    python3 scripts/py/getResultBipartitions.py\
        -f $TREEOUTPUT\
        -n $NAME\
        -m -g > ~/scratch/tmp_bipartitions_$RUNID.bootstrap.trees

    echo "Bipartitions saved to "~/scratch/tmp_bipartitions_$RUNID.bootstrap.trees
    echo "✅ Heuristic ASTRAL Get bipartitions" 
fi

echo "" > $TREEOUTPUT/$ASTRAL_VARIANT/trees/$NAME.tree
echo TEST, will output to $TREEOUTPUT/$ASTRAL_VARIANT/trees/$NAME.tree

java -jar -Xmx512g ASTRAL/Astral/astral.5.7.8.jar\
    -o $TREEOUTPUT/$ASTRAL_VARIANT/trees/$NAME.tree\
    -f ~/scratch/tmp_bipartitions_$RUNID.bootstrap.trees\
    -i ~/scratch/tmp_quartet_$RUNID.txt\
    -t 1\
    $RUN_EXACT\
    > /dev/null 2> $TREEOUTPUT/$ASTRAL_VARIANT/logs/$NAME.log # Run ASTRAL in default mode

echo "✅ Heuristic ASTRAL tree inference"
