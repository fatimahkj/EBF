#! /bin/bash

echo "Starting release generation for EBF"

echo "Building Pass"
mkdir -p build
cd build
cmake ../pass -DDCMAKE_CXX_COMPILER=$LLVM_CXX -DCMAKE_C_COMPILER=$LLVM_CC -DCMAKE_PREFIX_PATH=/usr/lib/llvm-11/
cmake --build .
cd ..

echo "Building Libs"
cd pass
gcc myFunctionslib.c -c -g -o mylibFunctions.o && ar rcs libmylibFunctions.a mylibFunctions.o
gcc myDelaylib.c -c -o mylib.o && ar rcs libmylib.a mylib.o
cd ..


echo "Building Directories"
mkdir -p fuzzEngine
mkdir -p bin



cd fuzzEngine
if [[ ! -d AFLplusplus ]]
then
    echo "Downloading and compiling AFL++"
    git clone --depth 1 https://github.com/AFLplusplus/AFLplusplus.git
    cd AFLplusplus
    LLVM_CONFIG=$EBF_LLVM_CONFIG CC=$LLVM_CC CXX=$LLVM_CXX make all -j
    sudo make install
    cd ../
fi
cd ../

if [[ ! -d bin/esbmc ]]
then
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

echo "Copying files"
cp build/libMemoryTrackPass.so ./lib
cp pass/*.a ./lib
chmod +x ./scripts/*
chmod +x ./lib/*
rm -rf build/
echo "Done"

