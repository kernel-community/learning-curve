FLAT_DIR="./flattened"

if  [ ! -d $FLAT_DIR ]; then mkdir $FLAT_DIR; fi

rm -f ./flattened/*
brownie run flatten_contracts.py $1