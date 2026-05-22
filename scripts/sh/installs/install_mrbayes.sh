git clone --depth=1 https://github.com/NBISweden/MrBayes.git bin/mrbayes
REPO_ROOT=$PWD
pushd bin/mrbayes
./configure --prefix="$REPO_ROOT/bin" --quiet && echo "MrBayes configuration done" && 
make --silent &&
make install --silent && 
echo "MrBayes built"
popd

rm -rf bin/{mrbayes,bin,share}