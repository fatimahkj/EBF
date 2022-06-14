# EBF
An Esemble Verification Tool for Finding Software Vulnerabilities in IoT Concurent programs


EBF is a tool that combines CBMC "Bounded Model Checking (BMC)" and AFL "Fuzzing" techniques to verify and detect security vulnerabilities in concurrent programs.
## SYSTEM REQUIREMENTS:
1. python v3
2. llvm clang 10

To Install clang-10 package for ubuntu-18.04:

` sudo apt-get install clang-tools-10
`
## INSTALLATION:
Clone EBF package and make sure SYSTEM REQUIREMENTS are correctly satisfied.

## SUPPORTING TOOLS:
1. afl-2.52b (Fuzzing algorithm)

[AFL TOOL URL](http://lcamtuf.coredump.cx/afl/ )

 [AFL LICENSE ](http://lcamtuf.coredump.cx/afl/README.txt)
 
2. CBMC v 5.44.0 (For initial seed generation)

[CBMC TOOL URL](https://github.com/diffblue/cbmc)

[CBMC LICENSE ](https://github.com/diffblue/cbmc/blob/develop/LICENSE)

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
