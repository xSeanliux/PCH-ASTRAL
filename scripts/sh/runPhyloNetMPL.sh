#!/bin/bash
# PhyloNet-MPL(FT): PCH-W quartets rooted on the outgroup plus the fixed pch_wastral
# tree in, networks with k = the dataset's contact event count out. Writes
# <output>/PHYLONET_MPL/networks/<name>.family.csv and <name>.net (best network)
# beside PhyloNet's raw <name>.result.
RUNID=""
INPUT=""
TREEOUTPUT=""
NAME=""
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -H|--runid) RUNID="$2"; shift ;;
        -i|--input) INPUT="$2"; shift ;;
        -o|--output) TREEOUTPUT="$2"; shift ;;
        -n|--name) NAME="$2"; shift ;;
        -h|--help)
            echo "Usage: $0 -H <runid> -i <input> -o <output> -n <name>"
            echo ""
            echo "Required:"
            echo "  -H, --runid        Run ID"
            echo "  -i, --input        Input characters CSV (a simulated dataset with an outgroup)"
            echo "  -o, --output       Output dir; holds the pch_wastral start tree"
            echo "  -n, --name         Run name; names the output files"
            echo ""
            echo "Environment:"
            echo "  PCH_PHYLONET_PROCS PhyloNet -pl processes (default 1)"
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

if [[ -z "$RUNID" || -z "$INPUT" || -z "$NAME" || -z "$TREEOUTPUT" ]]; then
    echo "Error: --runid, --input, --name and --output must be provided."
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
    --result "$RESULT" --procs "${PCH_PHYLONET_PROCS:-1}" > "$NEXUS" || exit 1
echo "✅ NEXUS: $(grep -c '^Tree gt' "$NEXUS") rooted quartets, $(grep -o 'InferNetwork_MPL (all) [0-9]*' "$NEXUS")"

# ponytail: no wall-clock cap here; the scheduler's job limit is the cap.
# PhyloNet logs every proposal to logfile.txt in its cwd (~150 MB/h): run in
# its own dir with that file sent to /dev/null. stdout echoes every gene tree
# id; keep it out of the log too.
JAR="$PWD/bin/PhyloNet.jar"
RUNDIR="$PCH_SCRATCH/phylonet_mpl_$RUNID"
mkdir -p "$RUNDIR" && ln -sf /dev/null "$RUNDIR/logfile.txt"
(cd "$RUNDIR" && java -jar "$JAR" "$NEXUS" > /dev/null) || exit 1

cat "$RESULT"
echo "✅ PhyloNet-MPL(FT)"

python3 -m scripts.py.phylonet_mpl_family --result "$RESULT" \
    --output "$PREFIX.family.csv" || exit 1
# Best network = the result's first newick, as written.
grep -m1 ';$' "$RESULT" > "$PREFIX.net" || exit 1
echo "✅ PhyloNet-MPL family CSV"
