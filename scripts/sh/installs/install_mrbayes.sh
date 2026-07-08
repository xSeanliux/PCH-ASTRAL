git clone --depth=1 https://github.com/NBISweden/MrBayes.git bin/mrbayes
REPO_ROOT=$PWD
pushd bin/mrbayes
./configure --prefix="$REPO_ROOT/bin" --quiet && echo "MrBayes configuration done" &&
make --silent &&
make install --silent &&
echo "MrBayes built"
popd

# `make install` (prefix=bin) writes the binary to bin/bin/mb. Hoist it to
# bin/mb — runGA.sh's default MB_EXEC — BEFORE pruning the staging dirs, or the
# `rm bin/bin` below would delete the binary we just built.
[ -x bin/bin/mb ] && mv bin/bin/mb bin/mb
rm -rf bin/{mrbayes,bin,share}
