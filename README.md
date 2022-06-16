# EBF
An Esemble Verification Tool for Finding Software Vulnerabilities in IoT Concurent programs


EBF is a tool that combines "Bounded Model Checking (BMC)" and AFL "Fuzzing" techniques to verify and detect security vulnerabilities in concurrent programs.
## SYSTEM REQUIREMENTS:
1. python v3
2. llvm clang 10

To Install clang-10 package for ubuntu-18.04:

` sudo apt-get install clang-tools-10
`
## INSTALLATION:
Clone EBF package and make sure SYSTEM REQUIREMENTS are correctly satisfied.

## SUPPORTING TOOLS:
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


## HOW TO RUN
Before running the tool for the first time, please log in as root and temporarily modify the core_pattern as:

` sudo echo core >/proc/sys/kernel/core_pattern
`

To run the tool:

`   ./scripts/RunEBF.py -a 32|64 -c -p property-file benchmark 
`

For example:

`    ./scripts/RunEBF.py -a 32 -p property-file/reach benchmarks/pthread/bigshot_p.c
`

A demonistration vedio of how to use the tool:

[EBF Demonistration](https://video.manchester.ac.uk/faculties/eb93b3a8b5a268cd92d4a041fcd72231/9c174f87-532a-487a-b4a1-a2f166fef270/)

Ps. The tool is still under development and it works perfectly on Ubuntu 18.4 running on macOS machine. Please, raise an issue if you have difficulty running the tool.
