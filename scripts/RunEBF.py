#!/usr/bin/env python3
import os
import time,shutil
import argparse
import sys
import string, re, random
import xml.etree.cElementTree as ET
from xml.etree.ElementTree import ElementTree
from os import path
SEP = os.sep
EBF_SCRIPT_DIR = os.path.split(os.path.abspath(__file__))[0]
EBF_DIR = os.path.split(EBF_SCRIPT_DIR)[0]
OUTDIR = EBF_DIR + SEP + "Results"
EBF_SCRIPTS=EBF_DIR+SEP+"scripts"
EBF_CORPUS=OUTDIR+SEP+"CORPUS"
EBF_TESTCASE=EBF_DIR+SEP+"test-suite"
EBF_EXEX= OUTDIR+SEP+ "Executable-Dir" #Executable path
EBF_FUZZENGINE= EBF_DIR+SEP+"fuzzEngine"
EBF_LIB=EBF_DIR+SEP+ "lib"
EBF_INSTRAMENTATION=EBF_LIB+SEP+"libDelayPass.so "
EBF_BIN= EBF_DIR + SEP+"bin"
EBF_AFL_COMPILER=EBF_FUZZENGINE+SEP+"afl-2.52b"
EBF_LOG= OUTDIR+ SEP + "log-files"
AFL_DIR = OUTDIR+SEP+"AFL-Results"
witness_File=OUTDIR+SEP+"witness-File"
start_time=0
PROPERTY_FILE = ""
C_FILE = ""
STRATEGY_FILE=""
ARCHITECTURE=""
RUN_LOG = ""
CONCURRENCY = False
Tsanitizer = "-fsanitize=thread "
Usanitizer="-fsanitize=undefined "
Compiler=" clang-10 "
Optimization=" -O3 -g  "
Compile_Flag=" -Xclang -load -Xclang "
TIMEOUT = 180 # kill if fuzzer reaches 3m

def startLogging():
    global RUN_LOG,RUN_STATUS_LOG
    RUN_LOG = open(EBF_LOG + SEP + "run.log", 'w+')
    RUN_STATUS_LOG = open(EBF_LOG + SEP + "runError.log", 'w+')


def HeaderContent():
    print ("\n""\n"" EBF Hybrid Tool is running""\n""\n")
    versionInfo = EBF_DIR + SEP + "versionInfoFolder" + SEP + "versionInfo.txt"
    if (os.path.isfile(versionInfo)):
        displayCommand = "cat " + versionInfo
        print
        ("\n\n Version: ")
        os.system(displayCommand)
    else:
        exitMessage = "Version Info File Is Not EXIST."
        print (exitMessage)
        exit(0)
    if os.path.exists(OUTDIR):
        shutil.rmtree(OUTDIR)
    os.mkdir(OUTDIR)

def GenerateInitialSeedESBMC():
    global startTime, C_FILE, PROPERTY_FILE,STRATEGY_FILE,ARCHITECTURE,CONCURRENCY
    if os.path.exists(witness_File):
        shutil.rmtree(witness_File )
    os.mkdir(witness_File)
    if os.path.exists(EBF_LOG):
         shutil.rmtree(EBF_LOG)
    os.mkdir(EBF_LOG)
    print ("\n\n Generating Seed Inputs\n\n")
    InputGenerationPath = EBF_SCRIPTS+SEP+"GenerateInputsESBMC.py"
    if(not(os.path.isfile(InputGenerationPath))):
        message = "Generating Input file is Not Exists!! "
        print (message)
    concurrency_arg = " -c " if CONCURRENCY else ""
    EBFRunCmd = "python3 " + InputGenerationPath + concurrency_arg +" -p "+ PROPERTY_FILE + " -s " +STRATEGY_FILE + " -a "+ str(ARCHITECTURE)+" " + C_FILE + " 1> " + EBF_LOG + SEP + "runCompiESBMC.log" + " 2> " + EBF_LOG + SEP + "runErrorESBMC.log"
    os.system(EBFRunCmd)


def processCommandLineArguements():
    global C_FILE, PROPERTY_FILE,STRATEGY_FILE,ARCHITECTURE,CONCURRENCY
    parser = argparse.ArgumentParser(prog = "EBF", description = "Tool for detecting concurrent and memory corruption bugs")
    #parser.add_argument('--version', action ='version', version='1.0.0')
    parser.add_argument("benchmark", nargs='?', help="Path to the benchmark")
    parser.add_argument('-p', "--propertyfile", required=True, help="Path to the property file")
    parser.add_argument("-a", "--arch", help="Either 32 or 64 bits", type=int, choices=[32, 64], default=32)
    parser.add_argument("-s", "--strategy", help="ESBMC's strategy", choices=["kinduction", "falsi", "incr", "unwind"],
                        default="incr")
    parser.add_argument("-c", "--concurrency", help="Set concurrency flags", action='store_true')
    args = parser.parse_args()
    PROPERTY_FILE = args.propertyfile
    C_FILE = args.benchmark
    ARCHITECTURE=args.arch
    CONCURRENCY=args.concurrency
    STRATEGY_FILE = args.strategy
    if (not ((os.path.isfile(PROPERTY_FILE) == True) and (os.path.isfile(C_FILE) == True))):
        exitMessage = "Either C File or Property File is not found. Please Rerun the Tool with Appropriate Arguments."
        sys.exit(exitMessage)
    cFileName = os.path.basename(C_FILE)
    fileBase,fileExt = os.path.splitext(cFileName)
    # Validate input file name
    if (not (fileExt == ".i" or fileExt == ".c")):
        message = "Invalid input file, The input file should be a C file"
        sys.exit(message)
    # If file is .i copy it to .c
    if (fileExt == ".i"):
        shutil.copy(C_FILE, fileBase + ".c")
        C_FILE = fileBase + ".c"
    return args

def getRandomAlphanumericString():
    letters_and_digits = string.ascii_lowercase + string.digits
    result_str = ''.join((random.choice(letters_and_digits) for i in range(5)))
    return result_str

def ConvertInitialSeed():
    global EBF_DIR, EBF_TESTCASE,EBF_CORPUS,witness_File
    list = []
    if os.path.exists(EBF_CORPUS):
        shutil.rmtree(EBF_CORPUS)
    os.mkdir(EBF_CORPUS)
    testCaseName = os.path.splitext(os.path.basename(C_FILE))[0]
    testcase=witness_File + SEP + testCaseName+".c.graphml"
    if (not (os.path.isfile(testcase) == True)):
        print ("\n Procceding ...!")
        RandomSeed()
    else:
        testcase_xml=ET.parse(testcase)
        root = testcase_xml.getroot()
        for x in root:
            for child in x:
                for item in child:
                    if item.attrib['key'] == 'startline':
                        startLine = int(item.text)
                        # print ("startline", startLine)
                        # list.append(startLine)
                    elif item.attrib['key'] == 'assumption':
                        assumption = item.text
                        # assumption => threadid = %d;
                        _, right = assumption.split("=")
                        # right => %d;
                        left, _ = right.split(";")
                        # left => %d
                        list.append(left.strip())
                    if list is None:
                        sys.exit("There Is No Inputs Generated From ESBMC")
        count = 1
        for data in list:
            output = open(os.path.join(EBF_CORPUS, 'id-' + getRandomAlphanumericString()), "w")
            output.write(''.join(data))
            count += 1
            output.close()
def RandomSeed():
    global EBF_CORPUS
    if [f for f in os.listdir(EBF_CORPUS) if not f.startswith('.')] == []:
        print ("\n\n There is no Testcases generated From ESBMC... Proceed to random inputs!\n\n")
        randomlist = random.sample(range(0, 500), 10)
        cont = 1
        for data in randomlist:
            randNumber = open(os.path.join(EBF_CORPUS, 'id-' + getRandomAlphanumericString()), "w")
            randNumber.write(''.join(str(data)))
            cont += 1
            randNumber.close()
    else:
        print ("\n\n Done \n\n")

def runAFL():
    global EBF_EXEX,C_FILE,EBF_FUZZENGINE,EBF_NONDOT,OUTDIR,EBF_INSTRAMENTATION,EBF_AFL_COMPILER,AFL_DIR,RUN_LOG,TIMEOUT,start_time,Usanitizer
    if os.path.exists(EBF_EXEX):
         shutil.rmtree(EBF_EXEX)
    os.mkdir(EBF_EXEX)
    curTime = time.time()
    timeElapsed = curTime - start_time
    fuzzTime = float(TIMEOUT) - (timeElapsed) - 15
    if (not ((os.path.isfile(EBF_LIB+SEP+ "atomics.c") == True) and (os.path.isfile(EBF_LIB + SEP + "nondet.c") == True))):
        exitMessage = "Either atomics.c or nondet.c File doesn't exist in "+EBF_LIB+"!!"
        sys.exit(exitMessage)
    aflFlag=" AFL_BENCH_UNTIL_CRASH=1 "
    #aflFlag+="AFL_I_DONT_CARE_ABOUT_MISSING_CRASHES=1 "
    if os.path.exists(AFL_DIR):
        shutil.rmtree(AFL_DIR)
    os.mkdir(AFL_DIR)
    AFL_Bin=EBF_AFL_COMPILER+SEP+"./afl-clang-fast"
    AFL_FUZZ_Bin=EBF_AFL_COMPILER+SEP+"afl-fuzz "
    Executable=os.path.splitext(os.path.basename(C_FILE))[0]+ "_AFL"
    # TODO: os.system putenv
    SetAnv= "AFL_CC"
    if SetAnv in os.environ:
        pass
    else:
        if path.exists('/usr/bin/clang-10'):
            os.environ["AFL_CC"] = "/usr/bin/clang-10"
        else:
            print("Please set the environment \n export AFL_CC= clang-10")
            exit(0)

    RunAfl= AFL_Bin + Optimization + Usanitizer  + Compile_Flag + EBF_INSTRAMENTATION+ C_FILE + " " +  \
                                      " -lpthread " + "-L"+EBF_LIB+ SEP + " -lmylib " + ' -o '+ EBF_EXEX + SEP + Executable + " 1> " + EBF_LOG + SEP + "runCompi.log"+ " 2> " + EBF_LOG + SEP + "runAflError.log"

    RunAflwithNondot = AFL_Bin + Optimization + Usanitizer + Compile_Flag + EBF_INSTRAMENTATION + C_FILE + "  " \
                                       + EBF_LIB+SEP+ "nondet.c " + "" + " -lpthread " + "-L"+EBF_LIB+ SEP + " -lmylib " +' -o '+ EBF_EXEX + SEP + Executable + " 1> " + EBF_LOG + SEP + "runCompi.log" + " 2> " + EBF_LOG + SEP + "runAflError.log"
    RunAflwithatomics = AFL_Bin + Optimization + Usanitizer + Compile_Flag + EBF_INSTRAMENTATION + C_FILE + "  " \
                                       + EBF_LIB+SEP+ "atomics.c  " + "" + " -lpthread " + "-L"+EBF_LIB+ SEP + " -lmylib " + ' -o '+ EBF_EXEX + SEP + Executable + " 1> " + EBF_LOG + SEP + "runCompi.log" + " 2> " + EBF_LOG + SEP + "runAflError.log"

    RunAflwithBoth= AFL_Bin + Optimization + Usanitizer + Compile_Flag + EBF_LIB+ SEP + EBF_INSTRAMENTATION + C_FILE + " " \
                                       "  "  + EBF_LIB + SEP + "nondet.c " + "  " + EBF_LIB+SEP+ "atomics.c  " + "" + " -lpthread " + "-L"+EBF_LIB+ SEP + " -lmylib " + ' -o '+ EBF_EXEX + SEP + Executable + " 1> " + EBF_LOG + SEP + "runCompi.log" + " 2> " + EBF_LOG + SEP + "runAflError.log"

    print ("\n\n Compiling the instrumented code ...\n\n")
    AflExexutableFile= EBF_EXEX+SEP+Executable
    ExecuteAfl = aflFlag + " timeout -k 2s "+ str(int(fuzzTime)) + " " +AFL_FUZZ_Bin + " -i  " + EBF_CORPUS + " -o " + AFL_DIR + " -m none -t 3000+ -- " + AflExexutableFile + " 1> " + EBF_LOG + SEP + "runScreen.log"
    check_nondot= open(C_FILE, 'r')
    read = check_nondot.read()
    if '_VERIFIER_nondet' in read and '_VERIFIER_atomic' in read:
        os.system(RunAflwithBoth)
    elif '__VERIFIER_nondet' in read:
        os.system(RunAflwithNondot)
    elif '__VERIFIER_atomic' in read:
        os.system(RunAflwithatomics)
    else:
        os.system(RunAfl)
    check_nondot.close()
    SetAflenv()
    print ("\n\n Running Fuzz Engine ... \n\n")
    os.system(ExecuteAfl)
    print ("\n\n Done \n\n")


def SetAflenv():
    global RUN_STATUS_LOG
    checkAflErrors=open(EBF_LOG+SEP+"runAflError.log")
    readAFLErr=checkAflErrors.read()
    if "undefined symbol" in readAFLErr:
        RUN_STATUS_LOG.write("\n\n Please check the logs! something went wrong with the fuzzer\n ")
        RUN_STATUS_LOG.write("\n EBF EXITING !!!\n ")
        displayresults = "cat " + EBF_LOG + SEP + "runError.log"
        RUN_STATUS_LOG.close()
        os.system(displayresults)
        exit(0)
    #elif "d" in readAFLErr:
        #RUN_STATUS_LOG.write("\n\n Please login as root and type the following command \n then exit, then run the EBF again!! \n ")

def runTSAN():
    global Tsanitizer,EBF_EXEX,C_FILE,EBF_LOG,EBF_LIB,EBF_INSTRAMENTATION
    print ("\n Runing Sanitizer ...")
    ExecutableTsan=os.path.splitext(os.path.basename(C_FILE))[0]+ "_TSAN"
    CompileTasan= Compiler+ Optimization+ Tsanitizer + Compile_Flag +EBF_INSTRAMENTATION + C_FILE + "  -lpthread "+ "-L"+EBF_LIB+ SEP + " -lmylib " + ' -o ' + EBF_EXEX + SEP + ExecutableTsan+ " 1> " + EBF_LOG + SEP + "runTsanCompi.log" + " 2> " + EBF_LOG + SEP + "runTasanCompileError.log"
    TSANExexutableFile = EBF_EXEX + SEP + "./"+ExecutableTsan
    CompileTsanWithatomics=Compiler+ Optimization+ Tsanitizer + Compile_Flag + EBF_INSTRAMENTATION + C_FILE  + " " + EBF_LIB+SEP+ "atomics.c  "+"  -lpthread "+ "-L"+EBF_LIB+ SEP + " -lmylib " + ' -o ' + EBF_EXEX + SEP + ExecutableTsan+ " 1> " + EBF_LOG + SEP + "runTsanCompi.log" + " 2> " + EBF_LOG + SEP + "runTasanCompileError.log"
    CompileTsanWithNondot=Compiler+ Optimization + Tsanitizer +  Compile_Flag + EBF_INSTRAMENTATION + C_FILE+ " " + EBF_LIB+SEP+ "nondet.c  "+" -lpthread  "+ "-L"+EBF_LIB+ SEP + " -lmylib " + ' -o ' + EBF_EXEX + SEP + ExecutableTsan+ " 1> " + EBF_LOG + SEP + "runTsanCompi.log" + " 2> " + EBF_LOG + SEP + "runTasanCompileError.log"
    CompileTsanWithBoth=Compiler+ Optimization+ Tsanitizer + Compile_Flag + EBF_INSTRAMENTATION + C_FILE  + " " + EBF_LIB+SEP+ "nondet.c  "+ " " + EBF_LIB+SEP+ "atomics.c  " + " -lpthread  "+ "-L"+EBF_LIB+ SEP + " -lmylib " + ' -o ' + EBF_EXEX + SEP + ExecutableTsan+ " 1> " + EBF_LOG + SEP + "runTsanCompi.log" + " 2> " + EBF_LOG + SEP + "runTasanCompileError.log"
    RunTsan="time timeout -k 2s 120 " + TSANExexutableFile +" 1> " + EBF_LOG + SEP + "runTsan.log"+ " 2> " + EBF_LOG + SEP + "runTsanError.log"
    check_nondot = open(C_FILE, 'r')
    read = check_nondot.read()
    if '_VERIFIER_nondet' in read and '_VERIFIER_atomic' in read:
        os.system(CompileTsanWithBoth)
    elif '__VERIFIER_nondet' in read:
        os.system(CompileTsanWithNondot)
    elif '__VERIFIER_atomic' in read:
        os.system(CompileTsanWithatomics)
    else:
        os.system(CompileTasan)
    check_nondot.close()
    os.system(RunTsan)
    print ("\n\n Done \n\n")


def AnalaysResults():
    global RUN_LOG,AFL_DIR,RUN_STATUS_LOG
    print ("\n\n checking logs ...\n\n")
    checkLog = open(EBF_LOG + SEP + "runScreen.log", 'r')
    read1 = checkLog.read()
    if "echo core" in read1:
        RUN_STATUS_LOG.write("\n Please login as root and type the following command \n then exit, then run the EBF again!! \n")
        RUN_STATUS_LOG.write("\n echo core >/proc/sys/kernel/core_pattern\n")
        displayresults = "cat " + EBF_LOG + SEP + "runError.log"
        RUN_STATUS_LOG.close()
        os.system(displayresults)
        exit(0)
    crashDir = AFL_DIR + SEP + "crashes"
    if (not os.path.exists(crashDir)):
        return
    crashingTestList = os.listdir(crashDir)
    if '.DS_Store' in crashingTestList:
        crashingTestList.remove('.DS_Store')
    if len(crashingTestList)==0:
        RUN_LOG.write(" \n VERIFICATION TRUE\n ")
    crashingTestList.sort(reverse=True)
    for t in crashingTestList:
        if (t.startswith("id:")):
            RUN_LOG.write(" \n VERIFICATION FAILED FROM AFL\n ")
            break
    checkESBMC = open(EBF_LOG + SEP + "runCompiESBMC.log", 'r')
    read2 = checkESBMC.read()
    if "VERIFICATION FAILED" in read2:
        RUN_LOG.write("\n VERIFICATION FAILED\n")
    elif "VERIFICATION SUCCESSFUL" in read2:
        RUN_LOG.write("\n VERIFICATION TRUE\n ")
    elif "Timeout" in read2:
        RUN_LOG.write("\n Timeout \n")
    else:
        RUN_LOG.write("\n Error running ESBMC .. Please check run log!\n ")
    checkTSAN = open(EBF_LOG+SEP+"runTsanError.log","r" )
    read3=checkTSAN.read()
    if "data race" in read3 or "thread leak" in read3:
        RUN_LOG.write("\n VERIFICATION FAILED\n")
    else:
        RUN_LOG.write("\n VERIFICATION TRUE\n ")
    RUN_LOG.close()

def displayOutcome():
    global RUN_LOG
    AnalaysResults()
    outcome=open(EBF_LOG + SEP + "run.log","r")
    read4=outcome.read()
    if "VERIFICATION FAILED" in read4:
        print ("\n VERIFICATION FAILED\n\n")
    elif "VERIFICATION TRUE" in read4:
        print ("\n VERIFICATION TRUE\n\n")
    else:
        print ("\n Err.. Check logs!!\n\n")

# Defining main function
def main():
   global start_time
   start_time = time.time()
   processCommandLineArguements()
   HeaderContent()
   GenerateInitialSeedESBMC()
   ConvertInitialSeed()
   RandomSeed()
   startLogging()
   runAFL()
   runTSAN()
   displayOutcome()
   end_time = time.time()
   elapsed_time=(end_time - start_time)
   hours, rem = divmod(elapsed_time, 3600)
   minutes, seconds = divmod(rem, 60)
   print("\n\n{:0>2}:{:0>2}:{:05.2f}".format(int(hours), int(minutes), seconds))
if __name__ == "__main__":
   main()






