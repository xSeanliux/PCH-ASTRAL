#!/bin/bash
# CLI variant of runASTRAL.sh: writes into the folder named by -V (e.g.
# PCH_ASTRAL_3(11,5)). The runner (scripts/lib/inference/runners.py) is the
# single source of truth for that name. Legacy runASTRAL.sh is kept as-is for
# the old bash pipeline.
# Initialize variables with defaults
RUNID=""
INPUT=""
QUARTET=11
BIPARTITIONS=5
TREEOUTPUT=""
RUN_EXACT=""
NAME=""
ASTRAL_VARIANT=""
# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -H|--runid) RUNID="$2"; shift ;;
        -i|--input) INPUT="$2"; shift ;;
        -o|--output) TREEOUTPUT="$2"; shift ;;
        -n|--name) NAME="$2"; shift ;;
        -V|--variant) ASTRAL_VARIANT="$2"; shift ;;
        -q|--quartet) QUARTET="$2"; shift ;;       # accepted, unused
        -b|--bipartitions) BIPARTITIONS="$2"; shift ;;  # accepted, unused
        -x|--exact) RUN_EXACT="-x" ;;  # Store "-x" if present
        -h|--help)
            echo "Usage: $0 -H <runid> -i <input> -o <output> -n <name> -V <variant> [-x]"
            echo ""
            echo "Required:"
            echo "  -H, --runid           Run ID"
            echo "  -i, --input           Input file or value"
            echo "  -o, --output          Output dir"
            echo "  -n, --name            Dataset name"
            echo "  -V, --variant         Output folder name (e.g. PCH_ASTRAL_3(11,5))"
            echo ""
            echo "Optional:"
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
if [[ -z "$RUNID" || -z "$INPUT" || -z "$NAME" ]]; then
    echo "Error: --runid, --input and --name must be provided."
    echo "Use -h or --help for usage."
    exit 1
fi
if [[ -z "$ASTRAL_VARIANT" ]]; then
    echo "Error: --variant (-V) must be provided."
    exit 1
fi

PCH_SCRATCH="${PCH_SCRATCH:-$HOME/scratch}"
mkdir -p "$PCH_SCRATCH"

mkdir -p $TREEOUTPUT/$ASTRAL_VARIANT/logs
mkdir -p $TREEOUTPUT/$ASTRAL_VARIANT/trees

python3 -m scripts.py.printQuartets -i "$INPUT" > "$PCH_SCRATCH/tmp_quartet_$RUNID.txt"
echo "✅ ASTRAL quartet generation, $(wc -l "$PCH_SCRATCH/tmp_quartet_$RUNID.txt" | awk '{ print $1 }') quartets"

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

# -Xmx8g is a sane default; make configurable later.
java -Xmx8g -jar ASTRAL/Astral/astral.5.7.8.jar\
    -o $TREEOUTPUT/$ASTRAL_VARIANT/trees/$NAME.tree\
    -f "$PCH_SCRATCH/tmp_bipartitions_$RUNID.bootstrap.trees"\
    -i "$PCH_SCRATCH/tmp_quartet_$RUNID.txt"\
    -t 1\
    $RUN_EXACT
rc=$?

echo "✅ Heuristic ASTRAL tree inference"
exit $rc
