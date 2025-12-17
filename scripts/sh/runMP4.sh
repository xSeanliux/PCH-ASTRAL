#!/bin/bash

# Initialize variables
RUNID=""
INPUT=""
NAME=""
TREEOUTPUT=""

OS_TYPE='RedHat' # RedHat / OSX

# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -H|--runid) RUNID="$2"; shift ;;
        -i|--input) INPUT="$2"; shift ;;
        -n|--name) NAME="$2"; shift ;;
        -o|--output) TREEOUTPUT="$2"; shift ;;
        -h|--help)
            echo "Usage: $0 -H <runid> -i <input> -n <name> -o <TREEOUTPUT>"
            echo "The tree will be saved under [TREEOUTPUT]/MP4/[name].trees"
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

if [[ $OS_TYPE = "RedHat" ]]; then 
    PAUP_PATH=scripts/bin/paup4a168_centos64
elif [[ $OS_TYPE = "OSX" ]]; then 
    PAUP_PATH=scripts/bin/paup
else 
    echo "PAUP_PATH could not be set (OSTYPE ="$OS_TYPE" may be invalid )"
fi
chmod a+x $PAUP_PATH

# Check required arguments
if [[ -z "$RUNID" || -z "$INPUT" ]]; then
    echo "Error: Both --runid and --input must be provided."
    echo "Use -h or --help for usage."
    exit 1
fi

mkdir -p $TREEOUTPUT/MP4/trees
mkdir -p $TREEOUTPUT/MP4/scores
mkdir -p $TREEOUTPUT/MP4/logs
>~/scratch/tmp_mp4_$RUNID.nex
Rscript scripts/R/commandLineNex.R\
    -H $RUNID\
    -f $INPUT\
    -o ~/scratch/tmp_mp4_$RUNID.nex\
    -p 3 -m 1.0

echo "✅ MP4 nexus files"
$PAUP_PATH -n ~/scratch/tmp_mp4_$RUNID.nex 
mv ~/scratch/paup_out_$RUNID.trees $TREEOUTPUT/MP4/trees/$NAME.trees # If we run lots of instances of this script in parallel, paup_out might be overwritten so we can't have that
mv ~/scratch/paup_out_$RUNID.scores $TREEOUTPUT/MP4/scores/$NAME.scores

# maj consensus
Rscript scripts/R/consensusTree.R\
    -i $TREEOUTPUT/MP4/trees/$NAME.trees\
    -m 2\
    -p 1\
    -o $TREEOUTPUT/MP4/trees/$NAME-maj.tree

echo "✅ MP4 tree inference" 
