# Extract into bin/ so the jar lands at bin/Astral/astral.5.7.8.jar with its
# sibling bin/Astral/lib/ (the jar's manifest Class-Path is lib/*.jar, resolved
# relative to the jar). runASTRAL3.sh and _astral3 both read bin/Astral/.
curl -o bin/astral3.zip https://github.com/smirarab/ASTRAL/raw/master/Astral.5.7.8.zip -L &&
    unzip -o bin/astral3.zip -d bin/ > /dev/null &&
    rm bin/astral3.zip &&
    echo "ASTRAL3 downloaded"

cp scripts/sh/installs/_astral3 bin/astral3 &&
    chmod +x bin/astral3 &&
    echo "Copied ASTRAL3 executable"
