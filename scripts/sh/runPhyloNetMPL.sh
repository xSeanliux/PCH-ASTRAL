#!/bin/bash
# PhyloNet-MPL(FT): PCH-W quartets rooted by the --guide-tree, plus that guide as start
# tree in, networks with k = the dataset's contact event count out. Writes PhyloNet's
# raw <output>/PHYLONET_MPL/networks/<name>.result; PhyloNetMPLRunner.execute then
# writes <name>.family.csv and <name>.net (best network).
RUNID=""
INPUT=""
TREEOUTPUT=""
NAME=""
GUIDE=""
PROCS=1
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -H|--runid) RUNID="$2"; shift ;;
        -i|--input) INPUT="$2"; shift ;;
        -o|--output) TREEOUTPUT="$2"; shift ;;
        -n|--name) NAME="$2"; shift ;;
        -g|--guide-tree) GUIDE="$2"; shift ;;
        -p|--procs) PROCS="$2"; shift ;;
        -h|--help)
            echo "Usage: $0 -H <runid> -i <input> -o <output> -n <name> -g <guide> [-p <procs>]"
            echo ""
            echo "Required:"
            echo "  -H, --runid        Run ID"
            echo "  -i, --input        Input characters CSV (a simulated dataset with an outgroup)"
            echo "  -o, --output       Output dir; holds the guide method's estimate"
            echo "  -n, --name         Run name; names the output files"
            echo "  -g, --guide-tree   Start tree and quartet rooting, e.g. pch_wastral or true_tree"
            echo "                     (all: PHYLONET_MPL_GUIDE_TREES in scripts/lib/model/guide_tree.py)"
            echo ""
            echo "Optional:"
            echo "  -p, --procs        PhyloNet -pl threads (default 1)"
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

if [[ -z "$RUNID" || -z "$INPUT" || -z "$NAME" || -z "$TREEOUTPUT" || -z "$GUIDE" ]]; then
    echo "Error: --runid, --input, --name, --output and --guide-tree must be provided."
    echo "Use -h or --help for usage."
    exit 1
fi

PCH_SCRATCH="${PCH_SCRATCH:-$HOME/scratch}"
mkdir -p "$PCH_SCRATCH" "$TREEOUTPUT/PHYLONET_MPL/networks"
# Absolute: PhyloNet runs elsewhere.
PCH_SCRATCH="$(cd "$PCH_SCRATCH" && pwd)"
PREFIX="$(cd "$TREEOUTPUT/PHYLONET_MPL/networks" && pwd)/$NAME"

NEXUS="$PCH_SCRATCH/tmp_phylonet_mpl_$RUNID.nex"
RESULT="$PREFIX.result"
rm -f "$RESULT"  # a stale one would pass for this run's

python3 -m scripts.py.phylonet_mpl_nexus --input "$INPUT" --output "$TREEOUTPUT" \
    --guide "$GUIDE" --result "$RESULT" --procs "$PROCS" > "$NEXUS" || exit 1
echo "✅ NEXUS: $(grep -c '^Tree gt' "$NEXUS") weighted rooted quartets, $(grep -o 'InferNetwork_MPL (all) [0-9]*' "$NEXUS")"

# ponytail: no wall-clock cap here; the scheduler's job limit is the cap.
# PhyloNet logs every proposal to logfile.txt in its cwd (~150 MB/h): run in
# its own dir with that file sent to /dev/null. stdout only echoes gene tree ids;
# errors go to stderr (the log), often with exit 0, so check the result exists.
# Scratch is kept on failure, removed on success.
JAR="$PWD/bin/PhyloNet.jar"
RUNDIR="$PCH_SCRATCH/phylonet_mpl_$RUNID"
mkdir -p "$RUNDIR" && ln -sf /dev/null "$RUNDIR/logfile.txt"
(cd "$RUNDIR" && java -jar "$JAR" "$NEXUS" > /dev/null) || exit 1
if [[ ! -s "$RESULT" ]]; then
    echo "❌ PhyloNet wrote no result; its error is above. NEXUS kept: $NEXUS"
    exit 1
fi

cat "$RESULT"
rm -rf "$RUNDIR" "$NEXUS"
echo "✅ PhyloNet-MPL(FT)"
