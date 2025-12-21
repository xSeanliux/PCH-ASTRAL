#!/bin/bash
shopt -s expand_aliases # expand alias so that mb works
TREECOUNT=16
REPLICA_COUNT=4  # a number from 1 to 4
OS_TYPE='RedHat' # RedHat / OSX
DO_ASTRAL=false  # a(stral)
DO_MP4=false     # p(arsimony)
DO_GA=false      # g(ray & atkinson)

# ASTRAL default modes
QT_MODE=11
BP_MODE=5

TARGETTREES=data/trees.txt
# list of allowed settings
E_FACTORS=("0.8") # evolution factor
H_FACTORS=("0.1") # homoplasy factor
C_FACTORS=("0.25" "0.5" "1" "3") # character factor
SETTINGS=("no" "low" "high") # s 
RUNID=$(tr -dc A-Za-z0-9 </dev/urandom | head -c 13; echo) # random string so that runs don't use the same name (i.e. for temp files)
while getopts 'aApgq:b:s:f:h:C:' o; do 
    echo $o' '$OPTARG
    case $o in 
        a) DO_ASTRAL=true;;
        A) DO_ASTRAL4=true;;
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

echo "MP4: $DO_MP4"
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
                CSVS=data/simulated_data/$SETTING_NAME
                TREEOUTPUT=sim_outputs/$SETTING_NAME

                ASTRAL_VARIANT=ASTRAL\($QT_MODE,$BP_MODE\)
                ASTRAL_SCOREOUTPUT=$TREEOUTPUT/$ASTRAL_VARIANT/allscores.txt 
                MP4_SCOREOUTPUT=$TREEOUTPUT/MP4/allscores.txt
                GA_SCOREOUTPUT=$TREEOUTPUT/GA/allscores.txt

                # initialise tree output space

                for ((i=1;i<=$TREECOUNT;i++)); do # tree number
                    for ((r=1;r<=$REPLICA_COUNT;r++)); do # rep number
                        id=sim_tree$i"_"$r
                        pattern=$id.csv
                        CURRENT_TREE=`head -"$i" $TARGETTREES | tail -1`
                        FILE=$CSVS/$pattern
                        echo "Factor: $f; ID = $id: target is tree $i"
                        # generate quartets
                        
                        if $DO_GA; then 
                            if ! test -s $TREEOUTPUT/GA/trees1/$id.trees; then 
                                bash scripts/sh/runGA.sh\
                                    --runid $RUNID\
                                    --input $FILE\
                                    --output $TREEOUTPUT\
                                    --name $id

                                touch $GA_SCOREOUTPUT
                                echo $FILE >> $GA_SCOREOUTPUT
                                Rscript scripts/R/RFScorer.R -f newick -r $CURRENT_TREE -m 4 -p 0 -i $TREEOUTPUT/GA/trees/$id.tree >> $GA_SCOREOUTPUT
                            else
                                echo "skipping "$id
                            fi
                        fi
                        if $DO_MP4; then 
                            if ! test -s $TREEOUTPUT/MP4/trees/$id.trees; then # You can run this multiple times to continue where you left off
                                bash scripts/sh/runMP4.sh\
                                    --runid $RUNID\
                                    --input $FILE\
                                    --name $id\
                                    --output $TREEOUTPUT

                                touch $MP4_SCOREOUTPUT
                                echo $FILE >> $MP4_SCOREOUTPUT
                                Rscript scripts/R/RFScorer.R -f nexus -r $CURRENT_TREE -m 2 -p 0 -i $TREEOUTPUT/MP4/trees/$id.trees >> $MP4_SCOREOUTPUT
                                echo "✅ MP4 tree scoring" 
                            else 
                                echo "Skipping "$id
                            fi
                        fi
                        if $DO_ASTRAL; then # run ASTRAL 
                            if ! test -s $TREEOUTPUT/$ASTRAL_VARIANT/trees/$id.tree; then
                                scripts/sh/runASTRAL.sh\
                                    -H $RUNID\
                                    -i $FILE\
                                    -o $TREEOUTPUT\
                                    -q $QT_MODE\
                                    -b $BP_MODE\
                                    -n $id

                                touch $ASTRAL_SCOREOUTPUT
                                echo $FILE >> $ASTRAL_SCOREOUTPUT
                                if [ $QT_MODE != 4 ]; then 
                                    Rscript scripts/R/RFScorer.R -f newick -r $CURRENT_TREE -m 1 -p 0 -i $TREEOUTPUT/$ASTRAL_VARIANT/trees/$id.tree >> $ASTRAL_SCOREOUTPUT
                                else 
                                    Rscript scripts/R/RFScorer.R --prune r -f newick -r $CURRENT_TREE -m 1 -p 0 -i $TREEOUTPUT/$ASTRAL_VARIANT/trees/$id.tree >> $ASTRAL_SCOREOUTPUT
                                fi
                                echo "✅ Heuristic ASTRAL tree scoring" 
                                echo "Updated score at "$ASTRAL_SCOREOUTPUT
                                rm ~/scratch/tmp_quartet_$RUNID.txt
                                rm ~/scratch/tmp_bipartitions_$RUNID.bootstrap.trees
                            else 
                                echo "Heuristic ASTRAL: Skipping "$id
                            fi
                        fi
                    done
                done
            done
        done
    done
done
        
