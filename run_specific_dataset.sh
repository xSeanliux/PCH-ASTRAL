#!/bin/bash
shopt -s expand_aliases # expand alias so that mb works
OS_TYPE='RedHat' # RedHat / OSX
DO_ASTRAL=false  # a(stral)
DO_MP4=false     # p(arsimony)
DO_GA=false      # g(ray & atkinson)

# ASTRAL default modes
QT_MODE=11
BP_MODE=5
ASTRAL_EXACT_FLAG=""

RUNID=$(tr -dc A-Za-z0-9 </dev/urandom | head -c 13; echo) # random string so that runs don't use the same name (i.e. for temp files)

FILE=""
TREEOUTPUT="."
NAME="output"
while getopts 'apgxn:q:b:i:o:' o; do 
    echo $o' '$OPTARG
    case $o in 
        i) FILE=$OPTARG;;
        o) TREEOUTPUT=$OPTARG;;
        n) NAME=$OPTARG;;
        a) DO_ASTRAL=true;;
        p) DO_MP4=true;;
        g) DO_GA=true;;
        q) QT_MODE=$OPTARG;; # only used with ASTRAL and ASTRAL-IV
        b) BP_MODE=$OPTARG;; # only used with ASTRAL
        x) ASTRAL_EXACT_FLAG="-x";;
        *) echo "Unknown argument: <"$o">";;
    esac
done 

echo "ASTRAL: $DO_ASTRAL"
if $DO_ASTRAL; then 
    echo "QT MODE: $QT_MODE, BP MODE: $BP_MODE"
fi

echo "MP4: $DO_MP4"
echo "GA: $DO_GA"

ASTRAL_VARIANT=ASTRAL\($QT_MODE,$BP_MODE\)

if $DO_GA; then 
    bash scripts/sh/runGA.sh\
        --runid $RUNID\
        --input $FILE\
        --output $TREEOUTPUT\
        --name $NAME
fi
if $DO_MP4; then 
    bash scripts/sh/runMP4.sh\
        --runid "$RUNID"\
        --input "$FILE"\
        --name "$NAME"\
        --output "$TREEOUTPUT"
fi
if $DO_ASTRAL; then # run ASTRAL 
    scripts/sh/runASTRAL.sh\
        -H "$RUNID"\
        -i "$FILE"\
        -o $TREEOUTPUT\
        -q $QT_MODE\
        -b $BP_MODE\
        -n "$NAME" $ASTRAL_EXACT_FLAG
    rm ~/scratch/tmp_quartet_$RUNID.txt
    rm ~/scratch/tmp_bipartitions_$RUNID.bootstrap.trees
fi