#!/bin/bash

# Initialize variables
MB_EXEC=bin/bin/mb # CHANGE ME to where your MrBayes is!!!!
if [[ -z "$MB_EXEC" ]]; then
  echo "Error: MB_EXEC is not set" >&2
  exit 1
fi

if [[ ! -x "$MB_EXEC" ]]; then
  echo "Error: MB_EXEC='$MB_EXEC' does not exist or is not executable" >&2
  exit 1
fi

RUNID=""
INPUT=""
NAME=""
TREEOUTPUT=""

# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -H|--runid) RUNID="$2"; shift ;;
        -i|--input) INPUT="$2"; shift ;;
        -o|--output) TREEOUTPUT="$2"; shift ;;
        -n|--name) NAME="$2"; shift ;;
        -h|--help)
            echo "Usage: $0 -H <runid> -i <input> -n <name> -o <TREEOUTPUT>"
            echo "The tree will be saved under [TREEOUTPUT]/GA/trees/[name].trees"
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

mkdir -p $TREEOUTPUT/GA/trees
mkdir -p $TREEOUTPUT/GA/trees1
mkdir -p $TREEOUTPUT/GA/scores

>~/scratch/tmp_mb_$RUNID.nex
Rscript scripts/R/commandLineNex.R -H $RUNID -f $INPUT -o ~/scratch/tmp_mb_$RUNID.nex --resolve-poly 4 --morph-weight 1.0
echo "✅ GA nexus files"
$MB_EXEC ~/scratch/tmp_mb_$RUNID.nex # > tmp_mb_out_$RUNID.txt 2> tmp_mb_log_$RUNID.txt


    
echo "✅ GA sampling"
mv Bayes_out_$RUNID.t $TREEOUTPUT/GA/trees1/$NAME.trees 

# MCC consensus, discard first 50%
Rscript scripts/R/consensusTree.R\
    -i $TREEOUTPUT/GA/trees1/$NAME.trees\
    -m 4\
    -p 1\
    -o $TREEOUTPUT/GA/trees/$NAME.tree\
    --discard 50

rm Bayes_out_$RUNID.* # tmp_mb*