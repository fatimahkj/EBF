# EBF
EBF (Ensemble Bounded Model Checking - Fuzzing) is a tool that combines "Bounded Model Checking (BMC)" and AFL "Fuzzing" techniques to verify and detect security vulnerabilities in concurrent programs. In contrast with portfolios, which simply run all possible techniques in parallel, EBF strives to obtain closer cooperation between them.
This goal is achieved in a black-box fashion. On the one hand, the model checkers are forced to provide seeds to the fuzzers by injecting additional vulnerabilities in the program under test. On the other hand, off-the-shelf fuzzers are forced to explore different interleavings by adding lightweight instrumentation and systematically re-seeding them.

To compile and run EBF, please refer to the following system requirements and installation instructions. We recommend starting by reading some of the publications to gain a clear understanding of what this tool can offer, as outlined in references [1](https://ieeexplore.ieee.org/stamp/stamp.jsp?arnumber=9955513) and [2](https://link.springer.com/chapter/10.1007/978-3-031-30820-8_33).


## Architecture:

The figure below illustrates the current EBF architecture. The tool takes a C/C++ program as input and employs the BMC engine to perform safety proving up to a  'k'  bound. Then, we inject errors into the program during (stage 2), generating seeds (inputs) extracted from the BMC engine used in the fuzzing phase (stage 3). Finally, the results are aggregated to produce the final verdict, along with the generation of a witness file.

<img width="1167" alt="Screenshot 2024-01-07 at 1 47 04 PM" src="https://github.com/fatimahkj/EBF/assets/47563480/bea4e63a-c8de-4ce7-a7af-1ebf40550215">


## Features:
EBF contains an open-source concurrency fuzzer that verifies concurrent programs by injecting delays controlled randomly by the fuzzer. EBF can find different concurrency-related and memory-related bugs, such as: 

**Memory-related**

- User-specified assertion failures

- Out-of-bounds array access

- Illegal pointer dereferences

- Memory leaks

**Concurrency-related**

- Deadlock 

- Data race

- Thread leak

## System Requirments:
1. python v3
2. llvm clang 11

To Install clang-11 package for ubuntu-18.04:

` sudo apt-get install clang-tools-11
`

3- To use Deagle you need bison and flex packages:

`sudo apt-get install -y bison`

`sudo apt-get -y install flex`

## Installation:
Clone EBF package and make sure SYSTEM REQUIREMENTS are correctly satisfied.

Then install the dependencies :

`EBF_LLVM_CONFIG=llvm-config-11 LLVM_CC=clang-11 LLVM_CXX=clang++-11 ./bootstrap.sh
`


## Supporting engines:
## A) Fuzzing engine:

1. afl++ (Apache License)

[AFL TOOL URL](https://github.com/AFLplusplus/AFLplusplus )

 
## B) BMC engine:
1. ESBMC (Apache License)

[ESBMC TOOL URL](https://github.com/esbmc/esbmc)

2. CBMC v 5.44.0 (BSD 4-Clause License)

[CBMC TOOL URL](https://github.com/diffblue/cbmc)

3. CSEQ (BSD 3-Clause License)

[CSEQ TOOL URL](http://www.southampton.ac.uk/~gp1y10/cseq/cseq.html)

4. Deagle (GPLv3)

[Deagle TOOL URL](https://github.com/thufv/Deagle)


## How to run
Before running the tool for the first time, please log in as root and temporarily modify the core_pattern as:

` sudo echo core >/proc/sys/kernel/core_pattern
`

To run the tool:

`   ./scripts/RunEBF.py -a 32|64 -c -p property-file benchmark 
`

For example:

`    ./scripts/RunEBF.py -a 32 -p property-file/reach benchmarks/pthread/bigshot_p.c
`

A demonstration video of how to use the tool:

[EBF Demonistration](https://video.manchester.ac.uk/faculties/eb93b3a8b5a268cd92d4a041fcd72231/9c174f87-532a-487a-b4a1-a2f166fef270/)

