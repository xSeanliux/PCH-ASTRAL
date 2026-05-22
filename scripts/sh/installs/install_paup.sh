PAUP_URL=https://phylosolutions.com/paup-test/paup4a168_osx.gz

if [ $(uname) == "Darwin" ]; then
    PAUP_URL=https://phylosolutions.com/paup-test/paup4a168_osx.gz
    echo "OSX detected, requires OSX 10.8+"
else 
    if [ $(lsb_release -a) == *"Ubuntu"*]; then 
        PAUP_URL=https://phylosolutions.com/paup-test/paup4a169_ubuntu64.gz # ubuntu
        echo "Ubuntu detected"
    else 
        PAUP_URL=https://phylosolutions.com/paup-test/paup4a168_centos64.gz

        echo "Non-ubuntu (centos/redhat) detected."
    fi
fi;

curl -o bin/paup.gz $PAUP_URL -L && 
    gunzip bin/paup && 
    chmod +x bin/paup
    echo "paup installed"