
cmake_minimum_required(VERSION 3.1)
project(MemoryTrackPass)
set(CMAKE_CXX_STANDARD 14)

find_package(LLVM REQUIRED CONFIG)
add_definitions(${LLVM_DEFINITIONS})
include_directories(${LLVM_INCLUDE_DIRS})
link_directories(${LLVM_LIBRARY_DIRS})


#add_library(DebugInfo STATIC DebugInfo.cpp)
add_library(MemoryTrackPass MODULE
    # List your source files here.
    MemoryTrackPass.cpp
    delayPass.cpp

)
target_link_libraries(MemoryTrackPass)

# Use C++11 to compile our pass (i.e., supply -std=c++11).
target_compile_features(MemoryTrackPass PRIVATE cxx_range_for cxx_auto_type)

# LLVM is (typically) built with no C++ RTTI. We need to match that;
# otherwise, we'll get linker errors about missing RTTI data.
set_target_properties(MemoryTrackPass PROPERTIES
    COMPILE_FLAGS "-fno-rtti"
)

# Get proper shared-library behavior (where symbols are not necessarily
# resolved when the shared library is linked) on OS X.
if(APPLE)
	set_target_properties(MemoryTrackPass PROPERTIES
        LINK_FLAGS "-undefined dynamic_lookup"
    )
endif(APPLE)
#mkdir build && cd build
#cmake -DCMAKE_CXX_FLAGS=-fno-rtti  -DCMAKE_CXX_COMPILER=clang++-11 -DCMAKE_C_COMPILER=clang-11 -DCMAKE_PREFIX_PATH=usr/lib/llvm-11/ ..
#make


