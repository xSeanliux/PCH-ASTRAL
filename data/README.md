# The `data/` folder
This folder contains all the data used in our simulation studies and our Indo-European analysis. 

### Simulation Data
The simulation data is composed of three parts: 
- The configuration files used to generate the simulation data (under `configs/`),
- The model trees (one per line in `trees.txt`), and
- The screened simulated character data themselves (in `simulated_data`).

The character data was simulated using [LingPhyloSimulator](https://github.com/marccanby/LingPhyloSimulator/). The seed used for each 

Each replica is under a folder with format `{poly}_{homoplasy-factor}_{evolution-factor}_{character-factor}`. Model trees should be placed under `data/simulated_data/trees.txt`, and should have one tree in newick format per line, in order. For example, one replica could have the path `data/simulated_data/high_0.1_0.8_0.5/sim_tree16_1.csv`.  This means that 
- The polymorphism is high
- The homoplasy factor is 0.1
- The evolution factor (or tree height) is scaled by 0.8.
- The character factor is 3, so there are 0.5 * 320 = 160 characters.
- The dataset was simulated down model tree 16 (i.e., the 16th line of `trees.txt` is the model tree), and was replica 1.

#### (Optional) How our data was generated 
We used the following script to generate our simulation character datasets from the configs in `configs`: 
```bash
CONFIGS=data/configs
JAROUT=... # path to LingPhyloSimulator/out
TARGETTREES=data/trees.txt
SIMOUT=data/simulated_data

# First build LingPhyloSimulator
javac -cp $CLASSPATH -d $JAROUT PATH_TO_LINGPHYLOSIMULATOR/LingPhyloSimulator/*.java 
cd $JAROUT
echo "Done compiling"
jar cvfe Simulator.jar Simulator Simulator.class ../Main ../lib
# Looping through each configuration 
cd $JAROUT/..
SETTINGS=(verylow low high)
H_FACTORS=(0.1)
# E_FACTORS=(1 2)
E_FACTORS=(0.8)
C_FACTORS=(0.25 0.5 1 3)

str_hash() {
  local s="$1"
  printf "%d\n" "0x$(printf "%s" "$s" | md5 | cut -c1-7)"
}

touch current_tree.txt
for cfactor in ${C_FACTORS[@]}; do
    for hfactor in ${H_FACTORS[@]}; do
        for efactor in ${E_FACTORS[@]}; do
            for setting in ${SETTINGS[@]}; do # setting is the setting
                datasetname=$setting"_"$hfactor"_"$efactor"_"$cfactor
                mkdir -p $SIMOUT/$datasetname
                for ((i=1;i<=$TREECOUNT;i++)); do # i: the tree number
                    head -"$i" $TARGETTREES | tail -1 > current_tree.txt # this line gets the ith tree
                    echo $(<current_tree.txt)
                    for ((c=1;c<=$REPLICAS;c++)); do # c: seed (replicas)
                        echo $i
                        paramfile=$CONFIGS/$datasetname.csv # file name
                        outputfile=$SIMOUT/$datasetname/sim_tree$i'_'$c.csv
                        touch $outputfile
                        seed=$(str_hash "$datasetname-$i-$c")
                        echo "seed is ${seed}"
                        java -cp $JAROUT/Simulator.jar:$CLASSPATH Simulator --simulate \
                            --tree $(<current_tree.txt)\
                            --sim-params-file $paramfile \
                            --sim-output-file $outputfile \
                            --sim-char-class PolymorphicCharacterClass \
                            --seed ${seed}\
                            --no-print 
                    done
                done
                echo "Finished $setting"
            done
        done
    done
done
rm current_tree.txt
```
### Indo-European Data 
All our Indo-European data can be found in `rt_2025_poly_screened_lv_1.csv`. The column `weight` is `50` for starred characters and `1` otherwise.