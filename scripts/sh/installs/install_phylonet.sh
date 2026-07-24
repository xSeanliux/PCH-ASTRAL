#!/bin/bash
# Download the PhyloNet jar into bin/PhyloNet.jar. Run via `java -jar
# bin/PhyloNet.jar cmd.nex`. Used for network scoring (CalGTProb). bin/ is
# git-ignored; this is the canonical way to (re)produce it.
set -euo pipefail

PHYLONET_VERSION="${PHYLONET_VERSION:-3.8.5}"
URL="https://github.com/NakhlehLab/PhyloNet/releases/download/${PHYLONET_VERSION}/PhyloNet.jar"

mkdir -p bin
curl -Lo bin/PhyloNet.jar "$URL"
echo "PhyloNet ${PHYLONET_VERSION} installed -> bin/PhyloNet.jar"
