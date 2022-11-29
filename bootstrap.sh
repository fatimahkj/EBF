#! /bin/bash

echo "Starting release generation for EBF"

echo "Deleting existing folders"
    rm -rf bin/Deagle
    rm -rf fuzzEngine
    rm -rf bin/esbmc

if [[ ! -d bin/Deagle ]]
then
    echo "Downloading and compiling Deagle"
    echo "Make sure you have bison and flex installed"
    cd bin
    git clone https://github.com/thufv/Deagle.git
    cd Deagle/src
    make 
    cd ../../..
fi
if [[ ! -d fuzzEngine ]]
then
    mkdir fuzzEngine
    cd fuzzEngine
    echo "Downloading and compiling AFL++"
    git clone --depth 1 https://github.com/AFLplusplus/AFLplusplus.git
    cd AFLplusplus
    LLVM_CONFIG=$EBF_LLVM_CONFIG CC=$LLVM_CC CXX=$LLVM_CXX make -j4
    cd ../..
fi
if [[ ! -d bin/esbmc ]]
    echo "Downloading and compiling ESBMC."
    cd bin
    chmod +x ESBMC-Linux.sh 
    sh ./ESBMC-Linux.sh --skip-license 
    mv bin/esbmc .
    rm -rf bin
    rm -rf license
    rm README
    rm release-notes.txt
    cd ../
fi

