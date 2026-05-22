curl -o bin/astral3.zip https://github.com/smirarab/ASTRAL/raw/master/Astral.5.7.8.zip -L &&
    unzip -o bin/astral3.zip > /dev/null &&
    rm bin/astral3.zip && 
    echo "ASTRAL3 downloaded"

cp scripts/sh/installs/_astral3 bin/astral3 &&
    chmod +x bin/astral3 &&
    echo "Copied ASTRAL3 executable"
