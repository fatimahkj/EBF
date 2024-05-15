#!/usr/bin/env python3
import os
import os.path
from multiprocessing import Pool
from multiprocessing import Process, Event
import tempfile
import time, shutil, shlex
import argparse, subprocess
import sys, resource
import string, re, random
import xml.etree.cElementTree as ET
from xml.etree.ElementTree import ElementTree
from os import path
from datetime import datetime
from ast import literal_eval
from pathlib import Path
import hashlib

SEP = os.sep
EBF_SCRIPT_DIR = os.path.split(os.path.abspath(__file__))[0]
EBF_DIR = os.path.split(EBF_SCRIPT_DIR)[0]
OUTDIR = EBF_DIR + SEP + "EBF_Results"
EBF_WITNESS = EBF_DIR + SEP + "EBF_witness"
EBF_SCRIPTS = EBF_DIR + SEP + "scripts"
EBF_CORPUS = ''
EBF_TESTCASE = EBF_DIR + SEP + "test-suite"
EBF_EXEX = ''
EBF_FUZZENGINE = EBF_DIR + SEP + "fuzzEngine"
EBF_LIB = EBF_DIR + SEP + "lib"
EBFـINSTRUMENTATION = EBF_LIB + SEP + "libMemoryTrackPass.so "
EBF_SEEDـINSTRUMENTATION=EBF_LIB+SEP+'EBF_instrument'
EBF_BIN = EBF_DIR + SEP + "bin"
CBMC = EBF_BIN + SEP + 'cbmc-sv'
EBF_LOG = ''
AFL_DIR = ''
BMC_Engine=''
AflExexutableFile = ''
witness_DIR = ''
witness_DIR_reacherr=''
versionInfo = EBF_DIR + SEP + "versionInfoFolder" + SEP + "versionInfo.txt"
start_time = 0
PROPERTY_FILE = ""
C_FILE = ''
VERSION = ''
STRATEGY_FILE = ""
ARCHITECTURE = ""
RUN_LOG = ""
VALIDATOR_DIR = ""
VALIDATOR_PROP = ""
preprocessed_c_file = ""
CONCURRENCY = False
isValidateTestSuite = False
correction_witness = ''
Tsanitizer = " -fsanitize=thread  "
Usanitizer = " -fsanitize=address  "
Compiler = " clang-11 "
AFL_COMPILER_DIR = EBF_FUZZENGINE + SEP + "AFLplusplus"
AFL_Bin = AFL_COMPILER_DIR + SEP + "./afl-clang-fast"
AFL_FUZZ_Bin = AFL_COMPILER_DIR + SEP + "afl-fuzz "
Optimization = " -g  "
Compile_Flags = " -Xclang -load -Xclang "  # -std=gnu89
TIMEOUT_AFL = 50  # kill if fuzzer reaches 420 s
TIMEOUT_TSAN = 40#for esbmc 432, fuzzer 400 s and esbmc 9 m
timeout =650
seed = datetime.now().timestamp()
MAX_VIRTUAL_MEMORY = 10000000000  # 10 GB
pre_C_File = ''
PARALLEL_FUZZ = ''
found_event=Event()

# Define colors used in printing messages throughout the script.

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    Green = '\x1b[6;30;42m'
    EndG = '\x1b[0m'


# Create log files and open them for writing the verification engine outputs.
def startLogging():
    global RUN_LOG, RUN_STATUS_LOG
    RUN_LOG = open(EBF_LOG + SEP + "run.log", 'w+')
    RUN_STATUS_LOG = open(EBF_LOG + SEP + "runError.log", 'w+')


# print the header content once the tool starts.
def HeaderContent():
    global versionInfo, VERSION
    print(f"{bcolors.WARNING}\n\n ****************** Running EBF Hybrid Tool ****************** \n\n{bcolors.ENDC}")
    if os.path.exists(versionInfo):
        displayCommand = "cat " + versionInfo
        print("Version: ")
        os.system(displayCommand)
    else:
        exitMessage = " Version Info File Is Not EXIST."
        print(exitMessage)

# This function used to print log word when each stage is Done.
def printLogWord(logWord):
    print(logWord + "... " + f"{bcolors.OKGREEN}  Done{bcolors.ENDC}\n\n")

# Create a command line needed from the user when starting the tool
def processCommandLineArguements():
    global C_FILE, PROPERTY_FILE, STRATEGY_FILE, ARCHITECTURE, category_property,CONCURRENCY, versionInfo, VERSION, OUTDIR, AFL_DIR, PARALLEL_FUZZ,BMC_Engine
    parser = argparse.ArgumentParser(prog="EBF", description="Tool for detecting concurrent and memory corruption bugs")
    parser.add_argument("-v", '--version', action='version', version='3.0.0')
    parser.add_argument("benchmark", nargs='?', help="Path to the benchmark")
    parser.add_argument('-p', "--propertyfile", required=True, help="Path to the property file")
    parser.add_argument("-a", "--arch", help="Either 32 or 64 bits", type=int, choices=[32, 64], default=32)
    parser.add_argument("-c", "--concurrency", help="Set concurrency flag", action='store_true')
    parser.add_argument("-m", "--parallel", help="Set fuzzengine parallel flag ", action='store_true')
    parser.add_argument( "-bmc", help="Set BMC engine", choices=["ESBMC", "CBMC", "CSEQ","DEAGLE"],
                        default="ESBMC")

    args = parser.parse_args()
    PROPERTY_FILE = args.propertyfile
    C_FILE = args.benchmark
    ARCHITECTURE = args.arch
    CONCURRENCY = args.concurrency
    PARALLEL_FUZZ = args.parallel
    BMC_Engine = args.bmc

    if C_FILE is None:
        exitMessage = " C File is not found. Please Rerun the Tool with Appropriate Arguments."
        sys.exit(exitMessage)
    if (not ((os.path.isfile(PROPERTY_FILE) == True) and (os.path.isfile(C_FILE) == True))):
        exitMessage = " Either C File or Property File is not found. Please Rerun the Tool with Appropriate Arguments."
        sys.exit(exitMessage)
    cFileName = os.path.basename(C_FILE)
    fileBase, fileExt = os.path.splitext(cFileName)
    if (not (fileExt == ".i" or fileExt == ".c")):
        message = " Invalid input file, The input file should be a .c or .i file"
        sys.exit(message)
    f = open(PROPERTY_FILE, 'r')
    property_file_content = f.read()
    f = open(PROPERTY_FILE, 'r')
    property_file_content = f.read()
    category_property = 0
    if "CHECK( init(main()), LTL(G valid-free) )" in property_file_content:
      category_property = "memory"
    elif "CHECK( init(main()), LTL(G ! overflow) )" in property_file_content:
      category_property = "overflow"
    elif "CHECK( init(main()), LTL(G ! call(reach_error())) )" in property_file_content:
      category_property = "reach"
    elif "CHECK( init(main()), LTL(G ! data-race) )" in property_file_content:
      category_property = "datarace"
    elif "CHECK( init(main()), LTL(G valid-memcleanup) )" in property_file_content:
      category_property = "memcleanup"
    else:
      print("Unsupported Property")
      exit(1)
        
    return args

# Create a random string used for testcases file. 
def getRandomAlphanumericString():
    letters_and_digits = string.digits
    result_str = ''.join((random.choice(letters_and_digits) for i in range(3)))
    return result_str
 

# This function will initialize all the Directory needed for EBF.
def initializeDir():
    global EBF_CORPUS, OUTDIR, EBF_LOG, EBF_EXEX, witness_DIR, AFL_DIR, C_FILE,witness_DIR_reacherr
    if os.path.isdir(OUTDIR):
        shutil.rmtree(OUTDIR)
    if not os.path.isdir(OUTDIR):
        os.mkdir(OUTDIR)
    if not os.path.isdir(OUTDIR):
        os.mkdir(OUTDIR)
    while True:
        tmpOutputFolder = OUTDIR + SEP + os.path.basename(C_FILE) + '_' + str(getRandomAlphanumericString())
        if not os.path.isdir(tmpOutputFolder):
            OUTDIR = tmpOutputFolder
            os.mkdir(OUTDIR)
            break
    EBF_CORPUS = OUTDIR + SEP + 'CORPUS' + '_' + os.path.basename(C_FILE) 
    if os.path.exists(EBF_CORPUS):
        shutil.rmtree(EBF_CORPUS)
    os.mkdir(EBF_CORPUS)
    witness_DIR = OUTDIR + SEP + 'witness-File' + '_' + os.path.basename(C_FILE) 
    if os.path.exists(witness_DIR):
        shutil.rmtree(witness_DIR)
    os.mkdir(witness_DIR)
    witness_DIR_reacherr=witness_DIR+SEP+'witness-File-reacherr'
    os.mkdir(witness_DIR_reacherr)
    EBF_EXEX = OUTDIR + SEP + "Executable-Dir" + '_' + os.path.basename(C_FILE)
    if os.path.exists(EBF_EXEX):
        shutil.rmtree(EBF_EXEX)
    os.mkdir(EBF_EXEX)
    EBF_LOG = OUTDIR + SEP + "log-files" + '_' + os.path.basename(C_FILE) 
    if os.path.exists(EBF_LOG):
        shutil.rmtree(EBF_LOG)
    os.mkdir(EBF_LOG)
    AFL_DIR = OUTDIR + SEP + "AFL-Results" + '_' + os.path.basename(C_FILE) 
    if os.path.exists(AFL_DIR):
        shutil.rmtree(AFL_DIR)
    os.mkdir(AFL_DIR)

def RunBMCEngine():
    global BMC_Engine
    logWord = "Generating Seed Inputs from "+ BMC_Engine
    print('\n\n')
    printLogWord(logWord)
    if BMC_Engine == 'CBMC':
        message = "\n\n CBMC is not supported in this version "
        print(message)
        exit(0)
    elif BMC_Engine =='ESBMC':
        GenerateInitialSeedBMC()
    elif BMC_Engine == 'CSEQ':
        message = "\n\n CSEQ is not supported in this version "
        print(message)
        exit(0)
    elif BMC_Engine == 'DEAGLE':
        message = "\n\n DEAGLE is not supported in this version "
        print(message)
        exit(0)

# This function is for assert 0 instrumentation, it will check first which category, we only support 
# reachability in this script. then we run the fusebmc instrumentation with appropriate flags to 
# get the goals and the number of the goals. 
# Then we pass the number of goals generated with the instrumented files (contains goal label).
def initial_analyze():
    global C_FILE,EBF_EXEX,category_property
    if category_property=="reach":
            #instrument the c file with _reach errors to generate seeds.
        print("\n\nInstrumenting the program with different goals")
        seeds_generation=EBF_SEEDـINSTRUMENTATION+SEP+'./FuSeBMC_instrument'
        seed_flags=" --add-labels --add-label-after-loop --add-goal-at-end-of-func "
        instrumented = os.path.splitext(os.path.basename(C_FILE))[0] + "_asserts.c"
        NumberOfGoals2='theGoalsFile.txt'
        if (not (os.path.isfile(seeds_generation))):
            message = "\n\n Instrumentation binary is NOT exists!! "
            print(message)
            exit(0)
        RunInstraForSeed=seeds_generation+' '+'--output '+instrumented+' ' +'--input'+' '+ C_FILE + ' '+seed_flags + ' --goal-output-file '+ NumberOfGoals2+' --check-concurrency ' 

        file = open(EBF_LOG + SEP + "runinstra.log", "w")
        file_err = open(EBF_LOG + SEP + "runErrorinstra.log", "w")
        try: 
            p = subprocess.run(RunInstraForSeed,stdout=file,stderr=file_err,shell=True,preexec_fn=limit_virtual_memory) #bufsize=1
            if path.exists(NumberOfGoals2):
                shutil.move(NumberOfGoals2,EBF_EXEX+SEP+NumberOfGoals2)
            if path.exists(instrumented):
                shutil.move(instrumented,EBF_EXEX+SEP+instrumented)
        except:
            print('we could not generate instrumentation files\n')
            exit(0)
        # opening the text file
        with open(EBF_EXEX+SEP+NumberOfGoals2,'r') as file:
    # reading each line    
            for line in file:
        # reading each word # number of goals       
                for word in line.split():         
                    GoalNumber=word
        # Adding elements to the List
        # using Iterator
        GoalList=[]
        for i in range(1, int(GoalNumber)+1):
            GoalList.append(i)
        print("\n\nFile contains ",GoalNumber, " goals")
        addGoals(EBF_EXEX+SEP+instrumented,GoalList)
    else:
        return



# This function will change each goal by reach_error function. 
# First, we will set the MAX time for all the goal to be run, 
# Second, we randomly chose the number of goal and change it to reach_error and save the file. 
# Third, we pass the file and the goal number associated with it to runBMCForSeedGenerationONLY Function.

def addGoals(instrumented_file,GoalList):
    Max_number_goals=GoalList
    seconds=150
    end_time = time.time() + seconds
    time_out=time.time() < end_time
    for i in range(len(GoalList)):
        if time.time() < end_time:
            goal_choice=random.choice(GoalList)
            goalword="GOAL_"+str(goal_choice)+":;"
            print("\n\nAdding reach error in goal ",goal_choice," to the file to generate BMC seeds ")
            reach_error_Cfile = os.path.splitext(os.path.basename(C_FILE))[0] + "_"+str(goal_choice)+"_reach.c"
            instrumented_reach_error=EBF_EXEX+SEP+reach_error_Cfile
            #print("file name ==",instrumented_reach_error)
            fin = open(instrumented_file, "rt")
            #output file to write the result to
            fout = open(instrumented_reach_error, "wt")
            #for each line in the input file
            for line in fin:
	        #read replace the string and write to output file
	            fout.write(line.replace(goalword, 'reach_error();'))
            #close input and output files
            fin.close()
            fout.close()
            GoalList.remove(goal_choice)
            runBMCForSeedGenerationONLY(instrumented_reach_error,goal_choice)
        else:
            print("\n\nWe exceed the time allocated for seed generation"+"\n\nWe are exiting the seed genertion")
            break
    

# This function will run ESBMC for seed generation only. It receives the file that contains the reach error.
# it will pass the directory where we saved the instrumented file
def runBMCForSeedGenerationONLY(reacherror_CFILE,goal_choice):
    #TODO you can make different wrapper for it. If you use ESBMC for the results and --compact-trace is affecting you can remove it.
    global startTime, PROPERTY_FILE, STRATEGY_FILE, ARCHITECTURE, CONCURRENCY, witness_DIR_reacherr,process,main_process,C_FILE
    InputGenerationPath = EBF_SCRIPTS + SEP + "esbmc-wrapper_ass.py"
    if (not (os.path.isfile(InputGenerationPath))):
        message = "Generating Input file is Not Exists!! "
        print(message)
    concurrency_arg = " -c " if CONCURRENCY else ""
    concurrency_arg = ' -c '
    STRATEGY_FILE = ' incr '
    EBFRunCmd = "python3 " + InputGenerationPath + concurrency_arg + " -p " + PROPERTY_FILE + " -s " + STRATEGY_FILE + " -a " + str(
        ARCHITECTURE) + " " + reacherror_CFILE +' -w ' + witness_DIR_reacherr+ " 1> " + EBF_LOG + SEP + "runCompiReacherrorBMC.log" + " 2> " + EBF_LOG + SEP + "runErrorReacherrorBMC_.log"
    os.system(EBFRunCmd)
    ConvertInitialSeed_reacherr(witness_DIR_reacherr,goal_choice)



# This Function will convert ESBMC witness file to seeds for AFL++ 
def ConvertInitialSeed_reacherr(witness_File_DIR,goal_choice):
    global EBF_DIR, EBF_TESTCASE, EBF_CORPUS, witness_DIR,C_FILE
    list = []
    testcase2 = witness_File_DIR + SEP + os.path.splitext(os.path.basename(C_FILE))[0] + "_"+str(goal_choice)+"_reach.c.graphml"
    if (not (os.path.isfile(testcase2) == True)):
        logWord = "Proceeding"
        printLogWord(logWord)
    else:
        testcase_xml = ET.parse(testcase2)
        root = testcase_xml.getroot()
        for x in root:
            for child in x:
                for item in child:
                    if item.attrib['key'] == 'startline':
                        startLine = int(item.text)
                    elif item.attrib['key'] == 'assumption':
                        assumption = item.text
                        try:
                            var, right = assumption.split("=")
                            strip1=var.strip()
                            if strip1=="threadid":
                                continue
                            left, _ = right.split(";")
                            Item=left.strip()
                            list.append(int(Item))
                        except:
                            pass
        if len(list) == 0:
            return
        #count = 1
        print("list",list)
        new_list=[]
        # Create bytearray
        # (sequence of values in binary form)
        # ASCII for A,B,C,D
        for item in list:
            bytesval=item.to_bytes(16, byteorder='big',signed=True) 
            new_list.append(bytesval) 
        #print("bytesvaltss",new_list)
        # Bytearray can be cast to bytes
        # Write bytes to file
        with open(os.path.join(EBF_CORPUS, 'id-' + getRandomAlphanumericString()), "wb") as output:
            output.write(bytesval)
            #count += 1



# This function run ESBMC to the original PUT without reach_error 
def GenerateInitialSeedBMC():
    global startTime, C_FILE, PROPERTY_FILE, STRATEGY_FILE, ARCHITECTURE, CONCURRENCY, witness_DIR

    logWord = "Generating Seed Inputs"
    print('\n\n')
    printLogWord(logWord)
    # Get the current working directory
    #this wrapper has set the time and memory internally
    InputGenerationPath = EBF_SCRIPTS + SEP + "esbmc-wrapper1.py"
    if (not (os.path.isfile(InputGenerationPath))):
        message = " Generating Input file is Not Exists!! "
        print(message)
    concurrency_arg = " -c " if CONCURRENCY else ""
    concurrency_arg = ' -c '
    STRATEGY_FILE = ' incr '
    EBFRunCmd = "python3 " + InputGenerationPath + concurrency_arg + " -p " + PROPERTY_FILE + " -s " + STRATEGY_FILE + " -a " + str(
        ARCHITECTURE) + ' -w ' + witness_DIR + " " + C_FILE + " 1> " + EBF_LOG + SEP + "runCompiBMC.log" + " 2> " + EBF_LOG + SEP + "runErrorBMC.log"
    os.system(EBFRunCmd)



# This function will convert ESBMC witness file to seeds for AFL
def ConvertInitialSeed(witness_DIR):
    global EBF_DIR, EBF_TESTCASE, EBF_CORPUS
    list = []
    testcase = witness_DIR + SEP + os.path.basename(C_FILE) + ".graphml"
    if (not (os.path.isfile(testcase) == True)):
        logWord = "Proceeding"
        printLogWord(logWord)
        RandomSeed()
    else:
        testcase_xml = ET.parse(testcase)
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
                        try:
                            var, right = assumption.split("=")
                            strip1=var.strip()
                            if strip1=="threadid":
                                continue
                            left, _ = right.split(";")
                            Item=left.strip()
                            list.append(int(Item))
                        except:
                            pass
        if len(list) == 0:
            return
        #count = 1
        print("list",list)
        new_list=[]
        # Create bytearray
        # (sequence of values in binary form)
        # ASCII for A,B,C,D
        for item in list:
            bytesval=item.to_bytes(16, byteorder='big',signed=True) 
            new_list.append(bytesval) 
        #print("bytesvaltss\n",new_list)
        # Bytearray can be cast to bytes
        # Write bytes to file
        with open(os.path.join(EBF_CORPUS, 'id-' + getRandomAlphanumericString()), "wb") as output:
            output.write(bytesval)

# This function will create a random numbers if ESBMC failed to do (if we activate the assert 0 this almost rare to happen)
def RandomSeed():
    global EBF_CORPUS, seed
    # TODO: Make each file contains 100 value
    if [f for f in os.listdir(EBF_CORPUS) if not f.startswith('.')] == []:
        print("There is no Testcases generated From BMC ..Proceed to random inputs!\n\n")
       # random.seed(seed)
        #randomlist = random.sample(range(0, 5000), 15)
        size = 10000
        some_bytes = os.urandom(size) 
        num_files = 1
        file_count = 1
        while file_count <= num_files:
            new_folder = 'id-' + str(file_count)
            with open(os.path.join(EBF_CORPUS, new_folder), mode="wb") as binary_file:
                # Write bytes to file
                binary_file.write(some_bytes)
            file_count += 1

# This function will check if the seeds are dublicated and remove the sublicated files
def corpusContentChecking():
    global EBF_CORPUS
    print("check if there is duplicated files")
    filelist = os.listdir(EBF_CORPUS)
    unique_files = dict()
    for file in filelist:
        file_path = Path(os.path.join(EBF_CORPUS, file))
        Hash_file = hashlib.md5(open(file_path, 'rb').read()).hexdigest()
        # Converting all the content of
        # our file into md5 hash
        try:
            if Hash_file not in unique_files:
                unique_files[Hash_file] = file_path
            else:
            # If file hash has already #
            # been added we'll simply delete that file
                os.remove(file_path)
        except:
            pass

# This function will run AFL++ with the pass and runtime library
def runAFL():
    global EBF_EXEX, C_FILE,category_property ,OUTDIR, EBFـINSTRUMENTATION, AFL_DIR, RUN_LOG, TIMEOUT_AFL, start_time, AFL_COMPILER_DIR, preprocessed_c_file, pre_C_File, AFL_Bin, AFL_FUZZ_Bin, AflExexutableFile
    if category_property=='reach':
        extention_format=os.path.splitext(os.path.basename(C_FILE))[1]
        pre_C_File = EBF_DIR + SEP + "input"+extention_format
        preprocessed_c_file = "cat " + C_FILE + " | sed -e 's/\<__inline\>//g' >  preprocessed1 "
        preprocessed_c_file2 = "cat  preprocessed1 | sed -e 's/\<inline\>//g' > " + pre_C_File 
        os.system(preprocessed_c_file)
        os.system(preprocessed_c_file2)
        os.remove('preprocessed1')
        curTime = time.time()
        timeElapsed = curTime - start_time
        fuzzTime = float(TIMEOUT_AFL) - (timeElapsed) - 60
        if (not ((os.path.isfile(EBF_LIB + SEP + "libmylib.a") == True) and (
                os.path.isfile(EBF_LIB + SEP + "libmylibFunctions.a") == True))):
            exitMessage = " Either libmylib.a or libmylibFunctions.a File doesn't exist in " + EBF_LIB + "!!"
            sys.exit(exitMessage)
        aflFlag = "AFL_BENCH_UNTIL_CRASH=1 AFL_I_DONT_CARE_ABOUT_MISSING_CRASHES=1 AFL_SKIP_CPUFREQ=1 "
        if os.path.exists(AFL_DIR):
            shutil.rmtree(AFL_DIR)
        os.mkdir(AFL_DIR)
        Executable = os.path.splitext(os.path.basename(C_FILE))[0] + "_AFL"
        SetAnv = "AFL_CC"
        if SetAnv in os.environ:
            pass
        else:
            if path.exists('/usr/bin/clang-11'):
                os.environ["AFL_CC"] = "/usr/bin/clang-11"
            else:
                print(" Please set the environment \n export AFL_CC= clang-11")
                os.environ["AFL_CC"] = "/usr/bin/clang-11"
        AflExexutableFile = EBF_EXEX + SEP + Executable
        RunAfl = " AFL_LLVM_THREADSAFE_INST=1 " + AFL_Bin + Optimization + Compile_Flags + EBFـINSTRUMENTATION + pre_C_File + " " + \
                 " -lpthread " + "-L" + EBF_LIB + SEP + " -lmylib -lmylibFunctions " + ' -o ' + EBF_EXEX + SEP + Executable + " 1> " + EBF_LOG + SEP + "AflCompile.log" + " 2> " + EBF_LOG + SEP + "AflCompileError.log"
        os.system(RunAfl)
        PARALLEL_FUZZ=''
        if PARALLEL_FUZZ:
            creatingPOol()
        else:
            logWord = "Invoking Fuzz Engine"
            printLogWord(logWord)
            ExecuteAfl = aflFlag + " timeout -k 2s " + str(
                TIMEOUT_AFL) + " " + AFL_FUZZ_Bin + " -i  " + EBF_CORPUS + " -o " + AFL_DIR + " -m none -t 3000+ -- " + AflExexutableFile + ' ' + " 1> " + EBF_LOG + SEP + "AflRun.log" + " 2> " + EBF_LOG + SEP + "AflrunError.log"
            SetAflenv()
            os.system(ExecuteAfl)
        with open(EBF_LOG + SEP + "AflrunError.log", 'r') as f:
            print("ErrorLog")
            out = f.read()
            print(out)
        with open(EBF_LOG + SEP + "AflRun.log", 'r') as f:
            print("Log")
            out = f.read()
            print(out)
        logWord = "Compiling the instrumented code"
        printLogWord(logWord)
    else:
        return


def creatingPOol():
    global found_event,AFL_DIR

    with Pool(3) as p:  # choose appropriate level of parallelism
        # choose appropriate command and argument, can be fetched from sys.argv if needed
       # t1 = time.time()
        exit_codes = p.map(ParallelFuzzing, [('-M', 'fuzzer01', 'AflRun.log'), ('-S', 'fuzzer02', 'AflRun1.log'),('-S', 'fuzzer03', 'AflRun2.log')])
        found_event.wait()
        for subb, diree, files in os.walk(AFL_DIR):
            if subb == AFL_DIR + SEP + 'fuzzer01/crashes' or subb == AFL_DIR + SEP + 'fuzzer02/crashes' or subb == AFL_DIR + SEP + 'fuzzer03/crashes':
                 crashingTestList = os.listdir(subb)
                 if len(crashingTestList) != 0:

                     crashingTestList.sort(reverse=True)
                     for t in crashingTestList:
                         if (t.startswith("id:")):
                            p.terminate()
        p.close()
        p.join()



def limit_virtual_memory():
    # The tuple below is of the form (soft limit, hard limit). Limit only
    # the soft part so that the limit can be increased later (setting also
    # the hard limit would prevent that).
    # When the limit cannot be changed, setrlimit() raises ValueError.
    resource.setrlimit(resource.RLIMIT_AS, (MAX_VIRTUAL_MEMORY, resource.RLIM_INFINITY))


# This function will run AFL if we set it to parallel fuzring.
def ParallelFuzzing(inputs):
    global EBF_EXEX, C_FILE, OUTDIR, EBFـINSTRUMENTATION, AFL_DIR, RUN_LOG, TIMEOUT_AFL, start_time, AFL_COMPILER_DIR, preprocessed_c_file, pre_C_File, AFL_Bin, AFL_FUZZ_Bin, AflExexutableFile,found_event
    logWord = "Invoking Parrallel Fuzzing"
    printLogWord(logWord)
    (nodes, outdir, logfile1) = inputs

    print("Starting node :{} with outdir {} and logfile {}".format(nodes, outdir, logfile1))
    ExecuteAfl = " AFL_BENCH_UNTIL_CRASH=1 AFL_I_DONT_CARE_ABOUT_MISSING_CRASHES=1 AFL_SKIP_CPUFREQ=1 " + " timeout -k 2s " + str(
        TIMEOUT_AFL) + " " + AFL_FUZZ_Bin + " -i  " + EBF_CORPUS + " -o " + AFL_DIR + ' ' + nodes + ' ' + outdir + " -m none -t 3000+ -- " + AflExexutableFile + '  ' + " 1> " + EBF_LOG + SEP + logfile1 + " 2> " + EBF_LOG + SEP + "AflrunError.log"
    final = subprocess.Popen("{}".format(ExecuteAfl), shell=True, universal_newlines=True,
                             preexec_fn=limit_virtual_memory)
    final.communicate()
    found_event.set()

def SetAflenv():
    global RUN_STATUS_LOG
    checkAflErrors = open(EBF_LOG + SEP + "AflCompileError.log")
    readAFLErr = checkAflErrors.read()
    if "undefined symbol" in readAFLErr:
        RUN_STATUS_LOG.write("Please check the logs! something went wrong with the fuzzer ")
        RUN_STATUS_LOG.write("EBF EXITING !!!\n ")
        displayresults = "cat " + EBF_LOG + SEP + "runError.log"
        RUN_STATUS_LOG.close()
        os.system(displayresults)
        exit(0)


def runTSAN():
    global Tsanitizer, EBF_EXEX, C_FILE, EBF_LOG, EBF_LIB, EBFـINSTRUMENTATION, TIMEOUT_TSAN, start_time
    curTime = time.time()
    timeElapsed = curTime - start_time
    ExecutableTsan = os.path.splitext(os.path.basename(C_FILE))[0] + "_TSAN"
    CompileTasan = Compiler + Optimization + Tsanitizer + " " + C_FILE + "  -lpthread " + EBF_LIB + SEP + "atomics.c " + EBF_LIB + SEP + "nondet_rand.c " + ' -o ' + EBF_EXEX + SEP + ExecutableTsan + " 1> " + EBF_LOG + SEP + "TsanCompile.log" + " 2> " + EBF_LOG + SEP + "TasanCompileError.log"
    TSANExexutableFile = EBF_EXEX + SEP + "./" + ExecutableTsan
    RunTsan = " timeout -k 2s " + str(
        TIMEOUT_TSAN) + " " + TSANExexutableFile + " 1> " + EBF_LOG + SEP + "TsanRun.log" + " 2> " + EBF_LOG + SEP + "TsanRunError.log"
    os.system(CompileTasan)
    os.system(RunTsan)
    logWord = "Runing Sanitizer"
    printLogWord(logWord)

def check_if_reach_error():
    for file in os.listdir(witness_DIR):
        if file.startswith("witnessInfoAFL-"):
            file_path = f"{witness_DIR}/{file}"
            check=open(file_path,'r')
            read=check.read()
            if "REACH_ERROR END" in read:
                return False


def AnalaysResults():
    global RUN_LOG, AFL_DIR, RUN_STATUS_LOG
    PARALLEL_FUZZ=''
    if PARALLEL_FUZZ:
        get_current=os.getcwd()
        os.chdir(EBF_LOG)
        for file in os.listdir():
            if file.startswith("AflRun"):
                file_path = f"{EBF_LOG}/{file}"
                checkLog = open(file_path, 'r')
                read1 = checkLog.read()
                if 'outright crash' in read1:
                    if check_if_reach_error() == False:
                        RUN_LOG.write("False(outright)\n")
                    else:
                        RUN_LOG.write("unknown\n")
                os.chdir(get_current)
                return
        os.chdir(get_current)
        crashDir = AFL_DIR
        logWord = "Checking logs"
        printLogWord(logWord)
        crashingTestList = os.listdir(crashDir)
        for subdir, dirs, files in os.walk(crashDir):
            if '.DS_Store' in files:
                crashDir.remove('.DS_Store')
                print('.DS_Store has been removed')
        for subb, diree, files in os.walk(crashDir):
            if subb == crashDir + SEP + 'fuzzer01/crashes' or subb == crashDir + SEP + 'fuzzer02/crashes' or subb == crashDir + SEP + 'fuzzer03/crashes':
                crashingTestList = os.listdir(subb)
                if len(crashingTestList) != 0:
                    crashingTestList.sort(reverse=True)
                    # ''.join(sorted(subb))
                    for t in crashingTestList:
                        if (t.startswith("id:")):
                            RUN_LOG.write("False(reach)\n")
                            return
        RUN_LOG.write("UNKNOWN\n")
        return

    else:
        checkLog = open(EBF_LOG + SEP + "AflRun.log", 'r')
        read1 = checkLog.read()
        crashDir = AFL_DIR + SEP + "default/crashes"
        if (not os.path.exists(crashDir)):
            return
        crashingTestList = os.listdir(crashDir)
        if '.DS_Store' in crashingTestList:
            crashingTestList.remove('.DS_Store')
        if 'outright crash' in read1:
            if check_if_reach_error() == False:
                RUN_LOG.write("False(outright)\n")
            else:
                RUN_LOG.write("unknown\n")
            return
        if len(crashingTestList) != 0:
            crashingTestList.sort(reverse=True)
            logWord = "Checking logs"
            printLogWord(logWord)
            for t in crashingTestList:
                if (t.startswith("id:")):
                    RUN_LOG.write("False(reach)\n")
                    break
        else:
            RUN_LOG.write("UNKNOWN\n")


def AnalaysResultsBMC():
    checkBMC = open(EBF_LOG + SEP + "runCompiBMC.log", 'r')
    read2 = checkBMC.read()
    if "FALSE_REACH" in read2:
        if "FALSE" in read2 and "reason for conflict" in read2:
            RUN_LOG.write("UNKNOWN\n")
        else:
            RUN_LOG.write("False(reach)\n")
    elif "TRUE" in read2:
        RUN_LOG.write(" true\n")
    elif "FALSE_OVERFLOW" in read2:
        RUN_LOG.write(" False(overflow)\n")
    else:
        RUN_LOG.write("UNKNOWN\n")

def TSANConfirm():
    runTSAN()
    checkTSAN = open(EBF_LOG + SEP + "TsanRunError.log", "r")
    read3 = checkTSAN.read()
    if "thread leak" in read3:
        return True

    return False

def displayOutcome():
    global RUN_LOG, witness_DIR
    i = 0
    AFL_Results = "unknown"
    ESBMC_Results="unknown"
    RUN_LOG.close()

    with open(EBF_LOG + SEP + "run.log", "r") as f:
        for line in f:
            word = line.strip()
            if word:
                if i == 0:
                    if word == 'False(reach)':
                        AFL_Results = "False"
                    elif word == 'False(outright)':
                        AFL_Results = "outright crash"
                elif i == 1:
                    if word == 'False(reach)':
                        ESBMC_Results = "False"
                    elif word == 'true':
                        ESBMC_Results = 'true'
                    elif word == 'False(overflow)':
                        ESBMC_Results = 'False(overflow)'


            i += 1
    print("Results from afl ", f"{bcolors.OKBLUE}" + AFL_Results + f"{bcolors.ENDC}", "and from BMC_Results",f"{bcolors.OKBLUE}" + ESBMC_Results + f"{bcolors.ENDC}\n\n")
    # if esbc true and Afl unknown then true
    if ESBMC_Results == 'true':
        print(f"{bcolors.OKGREEN}VERIFICATION TRUE\n\n{bcolors.ENDC}")
        #if afl is false and bmc did not say its a true then it false
    elif ESBMC_Results == "False" or  AFL_Results == "False" or AFL_Results == "outright crash":
        print(f"{bcolors.FAIL}FALSE(reach)\n\n{bcolors.ENDC}")
    elif ESBMC_Results == 'False(overflow)':
        print(f"{bcolors.FAIL}FALSE(overflow)\n\n{bcolors.ENDC}")
    else:
        print(f"{bcolors.WARNING}UNKNOWN\n\n {bcolors.ENDC}")


# This function will check the log and decide which witness type should be returned. 

def correction_witness():
    global RUN_LOG
    i = 0
    ESBMC_Results = 0
    AFL_Results = 0
    RUN_LOG.close()
    with open(EBF_LOG + SEP + "run.log", "r") as f:
        for line in f:
            word = line.strip()
            if word:
                if i == 0:
                    if word == 'False(reach)':
                        AFL_Results = 1
                    elif word == 'False(outright)':
                        AFL_Results = 3
                elif i == 1:
                    if word == 'False(reach)':
                        ESBMC_Results = 1
                    elif word == 'true':
                        ESBMC_Results = 2
                    elif word == 'False(overflow)':
                        ESBMC_Results = 3
            i += 1
    if ESBMC_Results == 2:
        f.close()
        return True
    elif AFL_Results == 1 or AFL_Results == 3 or ESBMC_Results == 1 or ESBMC_Results == 3:
        f.close()
        return False
    else:
        f.close()
        return True


# This function will move the files that contains witness info to the witness directory.
def witnessFile_pre():
    global witness_DIR, correction_witness
    Source = os.getcwd()
    # Moves every witness into the Results folder
    for file in os.listdir(Source):
        if file.startswith("witnessInfoAFL-"):
            with open(file) as infile, open(os.path.join(witness_DIR, file), "w") as outfile:
                copy = False
                for line in infile:
                    if line.strip() == "BEGIN":
                        bucket = []
                        copy = True
                    elif line.strip() == "REACH_ERROR END":
                        for strings in bucket:
                            outfile.write( strings + '\n')
                        outfile.write('REACH_ERROR END\n')
                        copy = False
                    elif copy:
                        bucket.append(line.strip())
            os.remove(file)
        if file.startswith("nondetInputs-"):
            shutil.move(os.path.join(Source, file), os.path.join(witness_DIR, file))
        

# This function will decide the type of witness and run WitnessFile.py which will generate the witness
def witnessFile():
    a = ''
    global witness_DIR, correction_witness
    witnessFileGeneration = EBF_SCRIPTS + SEP + "WitnessFile.py"
    if (not (os.path.isfile(witnessFileGeneration))):
        message = " Generating witness file is Not Exists!! "
        print(message)
    witness_type = "--witnessType=correct " if correction_witness() else "--witnessType=violation "
    WitnessRunCmd = "python3 " + witnessFileGeneration + " -p " + PROPERTY_FILE + " -a " + str(
        ARCHITECTURE) + " " + ' ' + C_FILE + ' ' + witness_type + ' -w ' + witness_DIR + ' -l ' + EBF_LOG + ' -bmc '+ BMC_Engine
    os.system(WitnessRunCmd)


# Defining main function
def main():
    global start_time
    start_time = time.time()
    processCommandLineArguements()
    initializeDir()
    HeaderContent()
    initial_analyze()
    RunBMCEngine()
    ConvertInitialSeed(witness_DIR)
    RandomSeed()
    startLogging()
    corpusContentChecking()
    runAFL()
    #runTSAN()
    witnessFile_pre()
    AnalaysResults()
    AnalaysResultsBMC()
    witnessFile()
    displayOutcome()
    shutil.move(pre_C_File, EBF_EXEX)
    end_time = time.time()
    elapsed_time = (end_time - start_time)
    hours, rem = divmod(elapsed_time, 3600)
    minutes, seconds = divmod(rem, 60)
    print("{:0>2}:{:0>2}:{:05.2f}".format(int(hours), int(minutes), seconds))


if __name__ == "__main__":
    main()






