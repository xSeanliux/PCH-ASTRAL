#!/bin/bash

# Initialize variables
RUNID=""
INPUT=""
NAME=""
TREEOUTPUT=""

COV_VARIANT="COV"
USE_BIRTHDEATH=false
BD_FLAG=""

# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -H|--runid) RUNID="$2"; shift ;;
        -i|--input) INPUT="$2"; shift ;;
        -o|--output) TREEOUTPUT="$2"; shift ;;
        -n|--name) NAME="$2"; shift ;;
        -n|--name) NAME="$2"; shift ;;
        -b|--birthdeath) 
            COV_VARIANT=COV-BD
            USE_BIRTHDEATH=true
            BD_FLAG="--birthdeath"
            ;;
        -h|--help)
            echo "Usage: $0 -H <runid> -i <input> -n <name> -o <TREEOUTPUT>"
            echo "The tree will be saved under [TREEOUTPUT]/COV/tree/[name].trees"
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
if [[ -z "$RUNID" || -z "$INPUT" ]]; then
    echo "Error: Both --runid and --input must be provided."
    echo "Use -h or --help for usage."
    exit 1
fi

mkdir -p $TREEOUTPUT/$COV_VARIANT/trees
mkdir -p $TREEOUTPUT/$COV_VARIANT/scores

RUN_NAME=$(
    python3 $TALLIS/OneMostProb/scripts/py/binaryCovarion.py $INPUT tmp_cov_$RUNID $BD_FLAG
)
echo RUNNAME IS $RUN_NAME
# run beast on that xml file
beast -overwrite -threads 4 ~/scratch/$RUN_NAME.xml
# MCC consensus 

mkdir -p $TREEOUTPUT/$COV_VARIANT/trees

Rscript $TALLIS/OneMostProb/scripts/R/consensusTree.R\
    -i $RUN_NAME'_path_sampling'/step0/$RUN_NAME.nex\
    -m 4\
    -p 1\
    -o $TREEOUTPUT/$COV_VARIANT/trees/$NAME.tree\
    --discard 75
# cat $TREEOUTPUT/COV/trees/$NAME.tree