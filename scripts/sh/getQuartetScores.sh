#!/bin/bash
TREE_A=/projects/illinois/eng/cs/warnow/zxliu2/QuartetMethods/rt_2025_poly/MP4/trees/consensus.tree
TREE_C="/projects/illinois/eng/cs/warnow/zxliu2/OneMostProb/outputs/rt_poly_2025/ASTRAL(11,5)/trees/output.tree"
TREE_3=/projects/illinois/eng/cs/warnow/zxliu2/OneMostProb/rt_2025_poly/ASTRAL\(1,5\)/trees/.tre
TREE_2=/projects/illinois/eng/cs/warnow/zxliu2/OneMostProb/rt_2025_poly/MP4/trees/canby_tree_2.tree
TREE_4=/projects/illinois/eng/cs/warnow/zxliu2/OneMostProb/outputs/rt_poly_2025/GA/trees/output.tree

total_quartets () {
    echo $1 | grep -oP '\d+(?= trees read from )'
    # $(echo "$text" | grep -oP '(?<=Final score is: )\d+')
}

satisfied_quartets() {
    echo $1 | grep -oP "(?<=Final quartet score is: )\d+"
}

normalised_score() {
   echo $1 | grep -oP "(?<=Final normalized quartet score is: )0.\d\d\d\d" 
}

echo DATASET        TREE A      TREE C      TREE 4
for dataset in $TALLIS/OneMostProb/example/rt_2025_poly/rt_2025_poly_screened_lv_*.csv; do
    filename=$(basename "$dataset" .${path##*.})
    lv=$(echo $filename | grep -oP "lv_\d")
    TREE_A_OUTPUT=$(bash $TALLIS/OneMostProb/score_tree.sh\
    $TREE_A $dataset 2>&1)

    TREE_C_OUTPUT=$(bash $TALLIS/OneMostProb/score_tree.sh\
    $TREE_C $dataset 2>&1)
    # echo $TREE_A_OUTPUT
    TREE_4_OUTPUT=$(bash $TALLIS/OneMostProb/score_tree.sh\
    $TREE_4 $dataset 2>&1)

    TREE_A_TOT=$(total_quartets "$TREE_A_OUTPUT")
    TREE_A_SAT=$(satisfied_quartets "$TREE_A_OUTPUT")
    TREE_A_NOR=$(normalised_score "$TREE_A_OUTPUT")
    TREE_C_TOT=$(total_quartets "$TREE_C_OUTPUT")
    TREE_C_SAT=$(satisfied_quartets "$TREE_C_OUTPUT")
    TREE_C_NOR=$(normalised_score "$TREE_C_OUTPUT")
    TREE_4_TOT=$(total_quartets "$TREE_4_OUTPUT")
    TREE_4_SAT=$(satisfied_quartets "$TREE_4_OUTPUT")
    TREE_4_NOR=$(normalised_score "$TREE_4_OUTPUT")
    # echo $lv    $TREE_A_SAT/$TREE_A_TOT     $TREE_C_SAT/$TREE_C_TOT $TREE_2_SAT/$TREE_2_TOT
    echo $lv    $TREE_A_NOR     $TREE_C_NOR     $TREE_4_NOR
done
