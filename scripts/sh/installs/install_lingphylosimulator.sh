#!/bin/bash
git clone https://github.com/marccanby/LingPhyloSimulator.git bin/LingPhyloSimulator --quiet

CLASSPATH="bin/LingPhyloSimulator"
JAROUT="bin/LingPhyloSimulator/out"

for FILE in bin/lingphylosimulator_jars/*.jar; do
    CLASSPATH=$FILE:$CLASSPATH
    jar xf "$FILE"
done
echo $CLASSPATH

javac -cp $CLASSPATH -d $JAROUT bin/LingPhyloSimulator/*.java 


jar cfe bin/LingPhyloSimulator.jar Simulator $JAROUT/Simulator.class bin/LingPhyloSimulator/Main bin/lingphylosimulator_jars
# rm -rf bin/LingPhyloSimulator