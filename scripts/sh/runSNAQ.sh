#!/bin/bash
# SNaQ network inference: PCH-W quartets as gene trees, the pch_wastral tree as start,
# hmax = the dataset's true reticulation count. Writes <output>/SNAQ/networks/<name>.net
# (Rich newick, rooted on the outgroup when compatible) plus SNaQ's .out/.log/.networks.
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
            echo "Environment:"
            echo "  PCH_SNAQ_PROCS    Julia workers, one SNaQ run each (default 1)"
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
    exit 1
fi

PCH_SCRATCH="${PCH_SCRATCH:-$HOME/scratch}"
mkdir -p "$PCH_SCRATCH" "$TREEOUTPUT/SNAQ/logs" "$TREEOUTPUT/SNAQ/networks"

SCRATCH_QUARTET_PATH="$PCH_SCRATCH/tmp_quartet_$RUNID.txt"
SCRATCH_START_PATH="$PCH_SCRATCH/tmp_start_$RUNID.tree"

# The paper sets hmax to the true reticulation count; simulated datasets only.
read -r HMAX OUTGROUP < <(python3 -m scripts.py.model_graph --input "$INPUT") || exit 1
[[ "$OUTGROUP" != none ]] || { echo "Error: SNaQ needs an outgroup (simulation.outgroup_label)"; exit 1; }
echo "✅ hmax $HMAX, outgroup $OUTGROUP"

# PCH-W writes each quartet once per unit of weight; SNaQ counts them into CFs.
python3 -m scripts.py.printQuartets -i "$INPUT" > "$SCRATCH_QUARTET_PATH" || exit 1
echo "✅ PCH-W quartet generation, $(wc -l < "$SCRATCH_QUARTET_PATH" | tr -d ' ') quartets"

python3 -m scripts.py.guide_tree --guide pch_wastral --input "$INPUT" --output "$TREEOUTPUT" \
    --outgroup "$OUTGROUP" > "$SCRATCH_START_PATH" || exit 1
echo "✅ start tree (pch_wastral)"

# 10 runs (SNaQ default; paper: 32), killed after 12 h (paper's limit).
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/../.." && pwd)"
JULIA_DEPOT_PATH="$REPO_ROOT/bin/julia-depot" JULIA_PROJECT="$REPO_ROOT/scripts/jl" \
    perl -e 'alarm shift; exec @ARGV' 43200 \
    "$REPO_ROOT/bin/julia" "$REPO_ROOT/scripts/jl/run_snaq.jl" \
    "$SCRATCH_QUARTET_PATH" "$SCRATCH_START_PATH" "$TREEOUTPUT/SNAQ/networks/$NAME" \
    "$HMAX" "$OUTGROUP" 10 "${PCH_SNAQ_PROCS:-1}"
rc=$?

echo "✅ SNaQ network inference"
exit $rc
