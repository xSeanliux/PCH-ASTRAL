echo "Installing wTree-QMC"
git clone https://github.com/molloy-lab/TREE-QMC bin/TREE-QMC --quiet && echo "Cloned Tree QMC"
pushd bin/TREE-QMC/external/MQLib
make > /dev/null 2&> 1
cd ../../ && mkdir -p build && cd build
echo "wTree-QMC building..."
g++ -std=c++11 -O2 \
    -I ../external/MQLib/include \
    -I ../external/toms743 \
    -o tree-qmc \
    ../src/*.cpp \
    ../external/toms743/toms743.cpp \
    ../external/MQLib/bin/MQLib.a \
    -lm \
    -DVERSION=\"$(cat ../version.txt)\" \
    -w && 
    echo "wTree-QMC build finished"
popd

cp bin/TREE-QMC/build/tree-qmc bin/tree-qmc
# rm -rf bin/TREE-QMC