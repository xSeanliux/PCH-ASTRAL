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
            echo "The tree will be saved under [TREEOUTPUT]/SD/tree/[name].tree"
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
mkdir -p $TREEOUTPUT/SD/trees/
mkdir -p $TREEOUTPUT/SD/trees1/
mkdir -p $TREEOUTPUT/SD/logs/

# generate nexus file
NEXPATH=~/scratch/tmp_sd_$RUNID.nex
PARPATH=~/scratch/tmp_sd_$RUNID.par
>$NEXPATH
Rscript scripts/R/commandLineNex.R\
    -H $RUNID\
    -f $INPUT\
    -o $NEXPATH\
    -p 9 -m 1.0
# generate PAR file
echo "✅ TraitLab nexus files"
echo $PARPATH
python3 scripts/py/stochasticDolloParfile.py\
    -i "$NEXPATH"\
    -o "$PARPATH"\
    -d ~/scratch/\
    -n "$NAME-$RUNID"
echo "✅ TraitLab PAR files"
# Run TraitLab
touch $TREEOUTPUT/SD/logs/$NAME.log
cd TraitLab
matlab -nodisplay -nosplash -nodesktop -batch "startup; batchTraitLab(\"${PARPATH}\")" > $TREEOUTPUT/SD/logs/$NAME.log
echo "END;" >> ~/scratch/$NAME-$RUNID.nex # this is really stupid, TraitLab does not output an END block...
cd ..
echo "✅ TraitLab MCMC"
# get point estimate
>$TREEOUTPUT/SD/trees/$NAME.tree
Rscript $TALLIS/OneMostProb/scripts/R/consensusTree.R\
    -i ~/scratch/$NAME-$RUNID.nex\
    -m 4\
    -p 1\
    -o $TREEOUTPUT/SD/trees/$NAME.tree\
    --discard 50

mv ~/scratch/$NAME-$RUNID.nex $TREEOUTPUT/SD/trees1/$NAME.nex
echo "✅ MCC Consensus"

