echo "Installing ASTER"
if [ $(uname) == "Darwin" ]; then
    if [ $(uname -m) == "arm64" ]; then 
        WASTRAL_URL="https://github.com/chaoszhang/ASTER/archive/refs/heads/MacOS.zip"
        echo "darwin (osx) arm64 detected"
    elif [ $(uname -m) == "x86_64"]; then
        WASTRAL_URL="https://github.com/chaoszhang/ASTER/archive/refs/heads/MacOSx86.zip"
        echo "darwin (osx) x86"
    fi; 
else 
    WASTRAL_URL="https://github.com/chaoszhang/ASTER/archive/refs/heads/Linux.zip"
    echo "linux"
fi;

curl -o bin/aster.zip $WASTRAL_URL -L &&
    unzip -o bin/aster.zip -d bin/ > /dev/null &&
    rm bin/aster.zip && 
    echo "ASTER downloaded"

cp bin/ASTER*/bin/{astral4,../../}
cp bin/ASTER*/bin/{wastral,../../}

rm -rf bin/ASTER*