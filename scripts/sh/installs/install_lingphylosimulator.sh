#!/bin/bash
git clone https://github.com/marccanby/LingPhyloSimulator.git bin/LingPhyloSimulator --quiet

JAROUT="bin/LingPhyloSimulator/out"
BUILD="bin/LingPhyloSimulator/build"

javac -cp "bin/lingphylosimulator_jars/*":"bin/LingPhyloSimulator"\
    -d $BUILD \
    bin/LingPhyloSimulator/*.java 

pushd $JAROUT

for j in ../../lingphylosimulator_jars/*.jar; do
  jar xf "$j"
done

cp -R ../build/* .

jar cfe ../LingPhyloSimulator.jar Simulator .

popd
rm -rf bin/LingPhyloSimulator
