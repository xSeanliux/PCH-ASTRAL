#!/bin/bash
# PhyloNet-MPL(FT): PCH-W quartets rooted on the outgroup plus the fixed pch_wastral
# tree in, one network with k = the dataset's contact event count out.
# Writes <output>/PHYLONET_MPL/networks/<name>.net (topology-only Rich newick).
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
PCH_SCRATCH="$(cd "$PCH_SCRATCH" && pwd)"  # absolute: PhyloNet runs elsewhere

NEXUS="$PCH_SCRATCH/tmp_phylonet_mpl_$RUNID.nex"
RESULT="$PCH_SCRATCH/tmp_phylonet_mpl_$RUNID.txt"

python3 -m scripts.py.phylonet_mpl_nexus --input "$INPUT" --output "$TREEOUTPUT" \
    --result "$RESULT" --procs "${PCH_PHYLONET_PROCS:-1}" > "$NEXUS" || exit 1
echo "✅ NEXUS: $(grep -c '^Tree gt' "$NEXUS") rooted quartets, $(grep -o 'InferNetwork_MPL (all) [0-9]*' "$NEXUS")"

# ponytail: no wall-clock cap here; the scheduler's job limit is the cap.
# PhyloNet writes logfile.txt to its cwd, so give each run its own. stdout
# echoes every gene tree id; keep it out of the log.
JAR="$PWD/bin/PhyloNet.jar"
mkdir -p "$PCH_SCRATCH/phylonet_mpl_$RUNID"
(cd "$PCH_SCRATCH/phylonet_mpl_$RUNID" && java -jar "$JAR" "$NEXUS" > /dev/null) || exit 1

# Best network = first newick in the result; strip lengths and inheritance
# probabilities (CmpNets wants topology only).
grep -m1 ';$' "$RESULT" | sed -E 's/:[^,();]*//g' > "$TREEOUTPUT/PHYLONET_MPL/networks/$NAME.net"
[[ -s "$TREEOUTPUT/PHYLONET_MPL/networks/$NAME.net" ]] || { rm -f "$TREEOUTPUT/PHYLONET_MPL/networks/$NAME.net"; echo "no network in $RESULT"; exit 1; }
cat "$RESULT"
echo "✅ PhyloNet-MPL(FT)"
