#! /bin/bash

echo "Starting release generation for EBF"
rm -rf _release
mkdir _release

echo "Building Pass"
mkdir -p build
cd build
cmake ../pass -DDCMAKE_CXX_COMPILER=$LLVM_CXX -DCMAKE_C_COMPILER=$LLVM_CC -DCMAKE_PREFIX_PATH=/usr/lib/llvm-10/
cmake --build .
cd ..

echo "Building Libs"
cd pass
gcc libFunctions.c -c -g -o mylibFunctions.o && ar rcs libmylibFunctions.a mylibFunctions.o
gcc libFunctionsTSAN.c -c -g -o mylibFunctionsTSAN.o && ar rcs libmylibFunctionsTSAN.a mylibFunctionsTSAN.o
gcc mylib.c -c -o mylib.o && ar rcs libmylib.a mylib.o
cd ..

if [[ ! -d AFLplusplus ]]
then
    echo "Downloading and compiling AFL"
    git clone --depth 1 https://github.com/AFLplusplus/AFLplusplus.git
    cd AFLplusplus
    LLVM_CONFIG=$EBF_LLVM_CONFIG CC=$LLVM_CC CXX=$LLVM_CXX make -j4
    cd llvm_mode
    LLVM_CONFIG=$EBF_LLVM_CONFIG CC=$LLVM_CC CXX=$LLVM_CXX make -j4
    cd ../..
fi

echo "Copying files"
cd _release
mkdir lib
cp -r ../scripts ./scripts
cp ../build/libMemoryTrackPass.so ./lib
cp ../pass/*.a ./lib
cp -r ../versionInfoFolder ./versionInfoFolder
cp ../LICENSE .
cp ../README.md .
mkdir fuzzEngine
cp -r ../AFLplusplus ./fuzzEngine/afl-2.52b
chmod +x ./scripts/*
