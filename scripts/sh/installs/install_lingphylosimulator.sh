#!/bin/bash
git clone https://github.com/marccanby/LingPhyloSimulator.git bin/LingPhyloSimulator --quiet

CLASSPATH=""
JAROUT=bin/out

for FILE in bin/LingPhyloSimulator/lib/*.jar; do
    CLASSPATH=$FILE:$CLASSPATH
done
echo $CLASSPATH

javac -cp $CLASSPATH -d $JAROUT bin/LingPhyloSimulator/*.java 

# rm -rf bin/LingPhyloSimulator