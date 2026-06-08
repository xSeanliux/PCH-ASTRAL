#!/bin/bash
echo "LingPhyloSimulator cloning"
git clone https://github.com/marccanby/LingPhyloSimulator.git bin/LingPhyloSimulator --quiet
echo "LingPhyloSimulator cloned"

JAROUT="bin/LingPhyloSimulator/out"
BUILD="bin/LingPhyloSimulator/build"

mkdir -p $JAROUT $BUILD

javac -cp "bin/lingphylosimulator_jars/*"\
    -d $BUILD \
    bin/LingPhyloSimulator/Main/*.java \
    bin/LingPhyloSimulator/Simulator.java > /dev/null 2>&1

cp -R $BUILD/* $JAROUT
pushd $JAROUT > /dev/null

for j in ../../lingphylosimulator_jars/*.jar; do
  jar xf "$j"
done


jar cfe ../../LingPhyloSimulator.jar Simulator .

popd > /dev/null
rm -rf bin/LingPhyloSimulator

echo "LingPhyloSimulator installed, do java -jar bin/LingPhyloSimulator.jar --help"
