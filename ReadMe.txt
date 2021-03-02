EBF: A Hybrid Verification Tool for Finding Software Vulnerabilities in IoT Cryptographic Protocols

EBF combines ESBMC "Bounded Model Checking (BMC)" and AFL "Fuzzing" techniques to verify and detect security vulnerabilities in concurrent applications and IoT Cryptographic Protocols.
EBF instrument the program under test using custom LLVM pass that track active threads and insert a delay function after instruction. 

SYSTEM REQUIREMENTS :
1) python v3
2) llvm clang 10
To Install clang-10 package for ubuntu-18.04:
 sudo apt-get install clang-tools-10

INSTALLATION:
Clone EBF package and make sure SYSTEM REQUIREMENTS are correctly satisfied.

SUPPORTING TOOLS:
a) afl-2.52b (Fuzzing algorithm)
   TOOL URL : http://lcamtuf.coredump.cx/afl/ 
   LICENSE  : http://lcamtuf.coredump.cx/afl/README.txt

b) ESBMC v 6.4.0 (For initial seed generation)
   TOOL URL : https://github.com/esbmc/esbmc
   LICENSE  : https://github.com/esbmc/esbmc/blob/master/COPYING





HOW TO RUN:
   Before running the tool for first time, please log in as root and temporarily modify as:

 sudo echo core >/proc/sys/kernel/core_pattern

   ./scripts/RunEBF.py -a 32|64 -c -s strategy -p property-file benchmark 


   eg. ./scripts/RunEBF.py -a 32 -s incr -p property-file/reach benchmarks/pthread/bigshot_p.c



Ps. The tool works perfectly on Ubuntu 18.4 running on macOS machine. Please, raise an issue if you have difficulty running the tool.
