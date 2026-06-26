#!/bin/bash
# Build ASTER (wastral + astral4) FROM SOURCE rather than downloading prebuilts.
# The upstream MacOS/Linux prebuilts are compiled with a recent deployment target
# (e.g. minos 15.0), so they fail to load on older OSes (dyld: Symbol not found).
# Building locally produces a binary matching this machine's OS/arch.
# See https://github.com/chaoszhang/ASTER/blob/master/tutorial/wastral.md
set -e
echo "Building ASTER from source"

rm -rf bin/ASTER
git clone --depth 1 https://github.com/chaoszhang/ASTER.git bin/ASTER --quiet
echo "Cloned ASTER"

# Makefile targets: `wastral` -> bin/wastral, `astral` -> bin/astral4.
# Each g++ line falls back from `-march=native -Ofast` to `-std=c++17 -O2`.
make -C bin/ASTER wastral astral
echo "ASTER built"

cp bin/ASTER/bin/wastral bin/wastral
cp bin/ASTER/bin/astral4 bin/astral4
rm -rf bin/ASTER
echo "Installed bin/wastral and bin/astral4"
