#!/bin/bash
shopt -s expand_aliases # expand alias so that mb works
TREECOUNT=32
REPLICA_COUNT=4  # a number from 1 to 4
OS_TYPE='RedHat' # RedHat / OSX
DO_ASTRAL=false  # a(stral)
DO_ASTRAL4=false # A(stral4)
DO_MP4=false     # p(arsimony)
DO_GA=false      # g(ray & atkinson)
DO_COVARION=false   # c(ovarion)
DO_BIRTHDEATH=false # only used when covarion is selected, whether to do birth-death tree prior

# ASTRAL default modes
QT_MODE=10
BP_MODE=5

TARGETTREES=$TALLIS/OneMostProb/example/all_simulated_data/trees.txt
# list of allowed settings
E_FACTORS=("1" "2" "4") # evolution factor
H_FACTORS=("0" "0.01" "0.05" "0.2" "0.5") # homoplasy factor
C_FACTORS=("1" "3") # character factor
SETTINGS=(mod modhigh high veryhigh) # s 
RUNID=$(tr -dc A-Za-z0-9 </dev/urandom | head -c 13; echo) # random string so that runs don't use the same name (i.e. for temp files)
while getopts 'aAcDpgq:b:s:f:h:C:' o; do 
    echo $o' '$OPTARG
    case $o in 
        a) DO_ASTRAL=true;;
        A) DO_ASTRAL4=true;;
        c) DO_COVARION=true;;
        D) DO_BIRTHDEATH=true;; # only used with covarion
        p) DO_MP4=true;;
        g) DO_GA=true;;
        q) QT_MODE=$OPTARG;; # only used with ASTRAL and ASTRAL-IV
        b) BP_MODE=$OPTARG;; # only used with ASTRAL
        f) 
        if [[ ${E_FACTORS[@]} =~ $OPTARG ]]; then  
            echo "FOUND FACTOR "$OPTARG 
            E_FACTORS=($OPTARG)
        else 
            echo "EFACTOR NOT FOUND. USING ALL"
        fi ;;
        s)
        if [[ ${SETTINGS[@]} =~ $OPTARG ]]; then  
            echo "FOUND SETTING "$OPTARG 
            SETTINGS=($OPTARG)
        else 
            echo "POLY SETTING NOT FOUND. USING ALL"
        fi ;;
        h) if [[ ${H_FACTORS[@]} =~ $OPTARG ]]; then  
            echo "FOUND HFACTOR "$OPTARG 
            H_FACTORS=($OPTARG)
        else 
            echo "H_FACTOR NOT FOUND. USING ALL"
        fi ;;
        C) if [[ ${C_FACTORS[@]} =~ $OPTARG ]]; then  
            echo "FOUND CFACTOR "$OPTARG 
            C_FACTORS=($OPTARG)
        else 
            echo "C_FACTOR NOT FOUND. USING ALL"
        fi ;;
        *) echo "Unknown argument: "$o
    esac
done 

echo "ASTRAL: $DO_ASTRAL"
if $DO_ASTRAL; then 
    echo "QT MODE: $QT_MODE, BP MODE: $BP_MODE"
fi
echo "ASTRAL4: $DO_ASTRAL4"
if $DO_ASTRAL4; then 
    echo "QT MODE: $QT_MODE"
    if $DO_ASTRAL; then 
        echo "ASTRAL4 AND ASTRAL mode both enabled; this is not allowed. Exiting" 
        exit 1
    fi
fi
echo "MP4: $DO_MP4"
echo "COVARION: $DO_COVARION"
echo BIRTHDEATH: $DO_BIRTHDEATH
echo "GA: $DO_GA"
echo "Settings:"${SETTINGS[@]}
echo "Homoplasy Factors:"${H_FACTORS[@]}
echo "Evolution Factors:"${E_FACTORS[@]}
echo "Character Factors:"${C_FACTORS[@]}

for poly in ${SETTINGS[@]}; do
    for h_factor in ${H_FACTORS[@]}; do
        for e_factor in ${E_FACTORS[@]}; do
            for c_factor in ${C_FACTORS[@]}; do
                SETTING_NAME=$poly"_"$h_factor"_"$e_factor"_"$c_factor
                CSVS=$TALLIS/OneMostProb/example/all_simulated_data/$SETTING_NAME
                TREEOUTPUT=$TALLIS/OneMostProb/sim_outputs/$SETTING_NAME

                ASTRAL_VARIANT=ASTRAL\($QT_MODE,$BP_MODE\)
                if $DO_ASTRAL4; then 
                    ASTRAL_VARIANT=ASTRAL4\($QT_MODE\)
                fi 
                ASTRAL_SCOREOUTPUT=$TREEOUTPUT/$ASTRAL_VARIANT/allscores.txt 
                MP4_SCOREOUTPUT=$TREEOUTPUT/MP4/allscores.txt
                GA_SCOREOUTPUT=$TREEOUTPUT/GA/allscores.txt
                if $DO_BIRTHDEATH; then 
                    COV_VARIANT=COV-BD     
                else 
                    COV_VARIANT=COV
                fi
                COV_SCOREOUTPUT=$TREEOUTPUT/$COV_VARIANT/allscores.txt 
                # initialise tree output space
                mkdir -p $TREEOUTPUT
                if $DO_ASTRAL || $DO_ASTRAL4; then
                    echo "ASTRAL NOT SUPPORTED"; exit 0
                    mkdir -p $TREEOUTPUT/$ASTRAL_VARIANT/logs
                    mkdir -p $TREEOUTPUT/$ASTRAL_VARIANT/trees
                    >$ASTRAL_SCOREOUTPUT # set up score output
                fi
                if $DO_MP4; then
                    echo "MP4 NOT SUPPORTED"; exit 0
                    mkdir -p $TREEOUTPUT/MP4/trees
                    mkdir -p $TREEOUTPUT/MP4/scores
                    >$MP4_SCOREOUTPUT # set up score output
                fi
                if $DO_COVARION; then
                    echo "COVARION NOT SUPPORTED"; exit 0
                    mkdir -p $TREEOUTPUT/$COV_VARIANT/trees
                    mkdir -p $TREEOUTPUT/$COV_VARIANT/scores
                    >$COV_SCOREOUTPUT # set up score output
                fi
                if $DO_GA; then
                    mkdir -p $TREEOUTPUT/GA/trees
                    mkdir -p $TREEOUTPUT/GA/trees1
                    mkdir -p $TREEOUTPUT/GA/scores
                    >$GA_SCOREOUTPUT # set up score output
                fi

                for ((i=1;i<=$TREECOUNT;i++)); do # tree number
                    for ((r=1;r<=$REPLICA_COUNT;r++)); do # rep number
                        id=sim_tree$i"_"$r
                        pattern=$id.csv
                        CURRENT_TREE=`head -"$i" $TARGETTREES | tail -1`
                        FILE=$CSVS/$pattern
                        echo "Factor: $f; ID = $id: target is tree $i"
                        # generate quartets
                        if $DO_COVARION; then 
                            echo "COVARION NOT SUPPORTED"; exit 0
                            echo DO COV IS $DO_COVARION
                            if test -s $TREEOUTPUT/$COV_VARIANT/trees/$id.tree; then 
                                BD_FLAG=""
                                if [[ $COV_VARIANT == "COV-BD" ]]; then 
                                    BD_FLAG="--birthdeath"
                                fi
                                # scoring
                                echo $FILE >> $COV_SCOREOUTPUT
                                Rscript $TALLIS/OneMostProb/scripts/R/RFScorer.R\
                                    -f newick\
                                    -r $CURRENT_TREE\
                                    -m 1 -p 0\
                                    -i $TREEOUTPUT/$COV_VARIANT/trees/$id.tree >> $COV_SCOREOUTPUT
                                echo "✅ COV tree scoring" 
                                rm -rf $RUN_NAME'_path_sampling'
                            else
                                echo "skipping scoring "$id
                            fi
                        fi
                        if $DO_GA; then 
                            Rscript $TALLIS/OneMostProb/scripts/R/consensusTree.R\
                                -i $TREEOUTPUT/GA/trees1/$id.trees\
                                -m 4\
                                -p 1\
                                -o $TREEOUTPUT/GA/trees/$id.tree\
                                --discard 50

                            echo $FILE >> $GA_SCOREOUTPUT
                            Rscript $TALLIS/OneMostProb/scripts/R/RFScorer.R -f newick -r $CURRENT_TREE -m 4 -p 0 -i $TREEOUTPUT/GA/trees/$id.tree >> $GA_SCOREOUTPUT
                  
                        fi
                        if $DO_MP4; then 
                            if test -s $TREEOUTPUT/MP4/trees/$id.trees; then # You can run this multiple times to continue where you left off
                                echo $FILE >> $MP4_SCOREOUTPUT
                                Rscript $TALLIS/OneMostProb/scripts/R/RFScorer.R -f nexus -r $CURRENT_TREE -m 2 -p 0 -i $TREEOUTPUT/MP4/trees/$id.trees >> $MP4_SCOREOUTPUT
                                echo "✅ MP4 tree scoring" 
                            else 
                                echo "Skipping scoring "$id
                            fi
                        fi
                        if $DO_ASTRAL; then # run ASTRAL 
                            echo "ASTRAL NOT SUPPORTED"; exit 0
                            if test -s $TREEOUTPUT/$ASTRAL_VARIANT/trees/$id.tree; then
                                echo $FILE >> $ASTRAL_SCOREOUTPUT
                                if [ $QT_MODE != 4 ]; then 
                                    Rscript $TALLIS/OneMostProb/scripts/R/RFScorer.R -f newick -r $CURRENT_TREE -m 1 -p 0 -i $TREEOUTPUT/$ASTRAL_VARIANT/trees/$id.tree >> $ASTRAL_SCOREOUTPUT
                                else 
                                    Rscript $TALLIS/OneMostProb/scripts/R/RFScorer.R --prune r -f newick -r $CURRENT_TREE -m 1 -p 0 -i $TREEOUTPUT/$ASTRAL_VARIANT/trees/$id.tree >> $ASTRAL_SCOREOUTPUT
                                fi
                                echo "✅ Heuristic ASTRAL tree scoring" 
                                echo "Updated score at "$ASTRAL_SCOREOUTPUT
                                rm ~/scratch/tmp_quartet_$RUNID.txt
                                rm ~/scratch/tmp_bipartitions_$RUNID.bootstrap.trees
                            else 
                                echo "Heuristic ASTRAL: Skipping Scoring "$id
                            fi
                        fi
                        if $DO_ASTRAL4; then 
                            echo "ASTRAL4 NOT SUPPORTED"; exit 0
                            if [ -s "$TREEOUTPUT/$ASTRAL_VARIANT/trees/$id.tree" ] && grep -q '[^[:space:]]' "$TREEOUTPUT/$ASTRAL_VARIANT/trees/$id.tree"; then
                                echo $FILE >> $ASTRAL_SCOREOUTPUT
                                Rscript $TALLIS/OneMostProb/scripts/R/RFScorer.R -f newick -r $CURRENT_TREE -m 1 -p 0 -i $TREEOUTPUT/$ASTRAL_VARIANT/trees/$id.tree >> $ASTRAL_SCOREOUTPUT
                                echo "✅ ASTRAL-IV tree scoring" 
                            else 
                                echo "Skipping scoring "$id
                            fi
                        fi
                    done
                done
            done
        done
    done
done
        