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
EBF_INSTRAMENTATION = EBF_LIB + SEP + "libMemoryTrackPass.so "
EBF_BIN = EBF_DIR + SEP + "bin"
CBMC = EBF_BIN + SEP + 'cbmc-sv'
DEAGLE= EBF_BIN+SEP+'Deagle'
CSEQ= EBF_BIN+SEP+'cseq'
EBF_LOG = ''
AFL_DIR = ''
AflExexutableFile = ''
witness_DIR = ''
versionInfo = EBF_DIR + SEP + "versionInfoFolder" + SEP + "versionInfo.txt"
start_time = 0
PROPERTY_FILE = ""
C_FILE = ''
c_file_i = ''
VERSION = ''
STRATEGY_FILE = ""
ARCHITECTURE = ""
RUN_LOG = ""
VALIDATOR_DIR = ""
VALIDATOR_PROP = ""
preprocessed_c_file = ""
EXTRAC=''
CONCURRENCY = False
isValidateTestSuite = False
correction_witness = ''
Tsanitizer = " -fsanitize=thread  "
Usanitizer = "-fsanitize=address  "
Compiler = " clang-10 "
AFL_COMPILER_DIR = EBF_FUZZENGINE + SEP + "AFLplusplus"
AFL_Bin = AFL_COMPILER_DIR + SEP + "./afl-clang-fast"
AFL_FUZZ_Bin = AFL_COMPILER_DIR + SEP + "afl-fuzz "
Optimization = " -g  "
Compile_Flag = " -Xclang -load -Xclang "  # -std=gnu89
TIMEOUT_AFL = ''  # kill if fuzzer reaches 420 s
TIMEOUT_TSAN = 40
TIMEOUT_BMC =''
seed = 10
MAX_VIRTUAL_MEMORY_BMC = ''  # 10 GB
MAX_VIRTUAL_MEMORY_AFL=''
pre_C_File = ''
PARALLEL_FUZZ = ''
BMC_Engine=''
found_event=Event()
finished_process=0
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


def startLogging():
    global RUN_LOG, RUN_STATUS_LOG
    RUN_LOG = open(EBF_LOG + SEP + "run.log", 'w+')
    RUN_STATUS_LOG = open(EBF_LOG + SEP + "runError.log", 'w+')


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

def printLogWord(logWord):
    print(logWord + "... " + f"{bcolors.OKGREEN}  Done{bcolors.ENDC}\n\n")


def processCommandLineArguements():
    global C_FILE, PROPERTY_FILE, STRATEGY_FILE, ARCHITECTURE, CONCURRENCY, c_file_i, versionInfo, VERSION, OUTDIR, AFL_DIR, PARALLEL_FUZZ,BMC_Engine,EXTRA,TIMEOUT_BMC,TIMEOUT_AFL,MAX_VIRTUAL_MEMORY_AFL,MAX_VIRTUAL_MEMORY_BMC
    parser = argparse.ArgumentParser(prog="EBF", description="Tool for detecting concurrent and memory corruption bugs")
    parser.add_argument("-v", '--version', action='version', version='4.0.0')
    parser.add_argument("benchmark", nargs='?', help="Path to the benchmark")
    parser.add_argument("-i", "--path", type=dir_path, nargs="+", help="Include Paths needed for compiling the benchmarks,  Multiple paths should be separated with spaces.",)
    parser.add_argument('-p', "--propertyfile", required=True, help="Path to the property file")
    parser.add_argument("-a", "--arch", help="Either 32 or 64 bits", type=int, choices=[32, 64], default=32)
    parser.add_argument("-t","--timeout",nargs="*", action="store", help= "Set Timelimit for BMC and Fuzzing respectively separated with spaces in SECOND" ,type=check_positive)
    parser.add_argument("-vm","--memory",nargs="*", action="store", help= "Set Max memory for BMC and Fuzzing respectively separated with spaces in MB" ,type=check_positive)
    parser.add_argument("-c", "--concurrency", help="Set concurrency flag", action='store_true')
    parser.add_argument("-m", "--parallel", help="Set fuzzengine parallel flag ", action='store_true')
    parser.add_argument( "-bmc", help="Set BMC engine", choices=["ESBMC", "CBMC", "CSEQ","DEAGLE"],
                        default="ESBMC")
    args = parser.parse_args()
    PROPERTY_FILE = args.propertyfile
    C_FILE = args.benchmark
    c_file_i = C_FILE
    ARCHITECTURE = args.arch
    CONCURRENCY = args.concurrency
    PARALLEL_FUZZ = args.parallel
    BMC_Engine = args.bmc
    EXTRA = args.path
    TIMEOUT=args.timeout
    MEMORY=args.memory
    if TIMEOUT is not None and len(args.timeout) not in (0, 2):
        parser.error('Either give no values for action, or two, not {}.'.format(len(args.timeout)))
    if TIMEOUT:
        TIMEOUT_BMC=TIMEOUT[0]
        TIMEOUT_AFL=TIMEOUT[1]
    else:
        TIMEOUT_BMC=500
        TIMEOUT_AFL=200
    if MEMORY is not None and len(args.memory) not in (0, 2):
        parser.error('Either give no values for action, or two, not {}.'.format(len(args.memory)))
    if MEMORY:
        if len(str(MEMORY[0])) < 8 or len(str(MEMORY[1])) <8:
            parser.error("Virtual MEmory limit is too low, please consider increasing the limit")
    if MEMORY:
        MAX_VIRTUAL_MEMORY_BMC=MEMORY[0]
        MAX_VIRTUAL_MEMORY_AFL=MEMORY[1]
    else:
        MAX_VIRTUAL_MEMORY_BMC=100000000
        MAX_VIRTUAL_MEMORY_AFL=500000000
    if C_FILE is None:
        exitMessage = " C File is not found. Please Rerun the Tool with Appropriate Arguments."
        sys.exit(exitMessage)
    if (not ((os.path.isfile(PROPERTY_FILE) == True) and (os.path.isfile(C_FILE) == True))):
        exitMessage = " Either C File or Property File is not found. Please Rerun the Tool with Appropriate Arguments."
        sys.exit(exitMessage)
    cFileName = os.path.basename(C_FILE)
    fileBase, fileExt = os.path.splitext(cFileName)
    # Validate input file name
    if (not (fileExt == ".i" or fileExt == ".c")):
        message = " Invalid input file, The input file should be a C file"
        sys.exit(message)
    return args

def dir_path(str_path: str):
    for quote in ['"', "'"]:
        if str_path.startswith(quote):
            str_path = str_path[1:-1]
    if str_path.startswith('~'):
        str_path = os.path.expanduser(str_path)
    if os.path.isdir(str_path):
        return str_path
    if os.path.isfile(str_path):
        return str_path
    raise NotADirectoryError(str_path)

def check_positive(value):
    ivalue = int(value)
    if ivalue <= 0:
        raise argparse.ArgumentTypeError("%s is an invalid positive int value" % value)
    return ivalue

def getRandomAlphanumericString():
    letters_and_digits = string.ascii_lowercase + string.digits
    result_str = ''.join((random.choice(letters_and_digits) for i in range(20)))
    return result_str


def initializeDir():
    global EBF_CORPUS, OUTDIR, EBF_LOG, EBF_EXEX, witness_DIR, AFL_DIR, C_FILE
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
    EBF_CORPUS = OUTDIR + SEP + 'CORPUS' + '_' + os.path.basename(C_FILE) + '_' + str(getRandomAlphanumericString())
    if os.path.exists(EBF_CORPUS):
        shutil.rmtree(EBF_CORPUS)
    os.mkdir(EBF_CORPUS)
    witness_DIR = OUTDIR + SEP + 'witness-File' + '_' + os.path.basename(C_FILE) + '_' + str(
        getRandomAlphanumericString())
    if os.path.exists(witness_DIR):
        shutil.rmtree(witness_DIR)
    os.mkdir(witness_DIR)
    EBF_EXEX = OUTDIR + SEP + "Executable-Dir" + '_' + os.path.basename(C_FILE) + '_' + str(
        getRandomAlphanumericString())  # Executable path
    if os.path.exists(EBF_EXEX):
        shutil.rmtree(EBF_EXEX)
    os.mkdir(EBF_EXEX)
    EBF_LOG = OUTDIR + SEP + "log-files" + '_' + os.path.basename(C_FILE) + '_' + str(getRandomAlphanumericString())
    if os.path.exists(EBF_LOG):
        shutil.rmtree(EBF_LOG)
    os.mkdir(EBF_LOG)
    AFL_DIR = OUTDIR + SEP + "AFL-Results" + '_' + os.path.basename(C_FILE) + '_' + str(getRandomAlphanumericString())
    if os.path.exists(AFL_DIR):
        shutil.rmtree(AFL_DIR)
    os.mkdir(AFL_DIR)

def RunBMCEngine():
    global BMC_Engine
    logWord = "Generating Seed Inputs from "+ BMC_Engine
    print('\n\n')
    printLogWord(logWord)
    if BMC_Engine == 'CBMC':
        GenerateInitialSeedCBMC()
    elif BMC_Engine =='ESBMC':
        GenerateInitialSeedESBMC()
    elif BMC_Engine == 'CSEQ':
        GenerateInitialSeedCSEQ()
    elif BMC_Engine == 'DEAGLE':
        GenerateInitialSeedDEAGLE()


def limit_virtual_memory():
    global MAX_VIRTUAL_MEMORY_BMC
    resource.setrlimit(resource.RLIMIT_AS, (MAX_VIRTUAL_MEMORY_BMC, resource.RLIM_INFINITY))



def limit_virtual_memory_AFL():
    global MAX_VIRTUAL_MEMORY_AFL
    resource.setrlimit(resource.RLIMIT_AS, (MAX_VIRTUAL_MEMORY_AFL, resource.RLIM_INFINITY))

def GenerateInitialSeedESBMC():
    global startTime, C_FILE, PROPERTY_FILE, STRATEGY_FILE, ARCHITECTURE, CONCURRENCY, witness_DIR,process,main_process
    InputGenerationPath = EBF_SCRIPTS + SEP + "esbmc-wrapper.py"
    if (not (os.path.isfile(InputGenerationPath))):
        message = "Generating Input file is Not Exists!! "
        print(message)
    concurrency_arg = " -c " if CONCURRENCY else ""
    concurrency_arg = ' -c '
    STRATEGY_FILE = ' incr '
    EBFRunCmd = "python3 " + InputGenerationPath + concurrency_arg + " -p " + PROPERTY_FILE + " -s " + STRATEGY_FILE + " -a " + str(
        ARCHITECTURE) + ' -w ' + witness_DIR + " " + C_FILE + " -t "+ str(TIMEOUT_BMC) +" -m "+str(MAX_VIRTUAL_MEMORY_BMC)+  " 1> " + EBF_LOG + SEP + "runCompiBMC.log" + " 2> " + EBF_LOG + SEP + "runErrorBMC.log"
    os.system(EBFRunCmd)



def GenerateInitialSeedCBMC():
    global startTime, C_FILE, PROPERTY_FILE, STRATEGY_FILE, ARCHITECTURE, CONCURRENCY, witness_DIR, CBMC
    cwd = os.getcwd()
    abs_PROPERTY_FILE = os.path.abspath(PROPERTY_FILE)
    abs_C_FILE = os.path.abspath(C_FILE)
    cbmc_binary = "./cbmc"
    checkCBMC = os.path.join(CBMC, cbmc_binary)
    if (not (os.path.isfile(checkCBMC))):
        message = "Generating Input file is Not Exists!! "
        print(message)
    os.chdir(CBMC)
    STRATEGY_FILE = '  '
    witness_BMC_file_name = witness_DIR + SEP + os.path.basename(C_FILE) + ".graphml "
    arch = "64"
    EBFRunCmd = "CBMC_timeout="+str(TIMEOUT_BMC)+" "+ cbmc_binary + " --propertyfile " + abs_PROPERTY_FILE + " --" + str(
        arch) + ' --graphml-witness  ' + witness_BMC_file_name + " " + abs_C_FILE + " 1> " + EBF_LOG + SEP + "runCompiBMC.log" + " 2> " + EBF_LOG + SEP + "runErrorBMC.log"
    os.system(EBFRunCmd)
    os.chdir(cwd)

def GenerateInitialSeedCSEQ():
    global startTime, C_FILE, PROPERTY_FILE, STRATEGY_FILE, ARCHITECTURE, CONCURRENCY, witness_DIR, CSEQ
    # Get the current working directory
    InputGenerationPath = CSEQ + SEP + "./lazy-cseq.py"
    if (not (os.path.isfile(InputGenerationPath))):
        message = " Generating Input file is Not Exists!! "
        print(message)
    cwd = os.getcwd()
    abs_PROPERTY_FILE = os.path.abspath(PROPERTY_FILE)
    abs_C_FILE = os.path.abspath(C_FILE)
    cseqbinary = './lazy-cseq.py'
    os.chdir(CSEQ)
    witness_BMC_file_name = witness_DIR + SEP + os.path.basename(C_FILE) + ".graphml "
    EBFRunCmd = "timeout -k 2s " + str(
        TIMEOUT_BMC) + " " + cseqbinary + ' --spec ' + abs_PROPERTY_FILE + '  --witness '+witness_BMC_file_name + " --input "+ abs_C_FILE
    file = open(EBF_LOG + SEP + "runCompiBMC.log", "w")
    file_err = open(EBF_LOG + SEP + "runErrorBMC.log", "w")
    p = subprocess.Popen(EBFRunCmd, shell=True, stdout=file, stderr=file_err, universal_newlines=True,
                         preexec_fn=limit_virtual_memory)
    p.communicate()
    os.chdir(cwd)



def GenerateInitialSeedDEAGLE():
    global startTime, C_FILE, PROPERTY_FILE, STRATEGY_FILE, ARCHITECTURE, CONCURRENCY, witness_DIR, DEAGLE,MAX_VIRTUAL_MEMORY_BMC
    InputGenerationPath = DEAGLE+SEP+"./deagle"
    if(not(os.path.isfile(InputGenerationPath))):
        message = " Generating Input file is Not Exists!! "
        print(message)
    witness_BMC_file_name = witness_DIR + SEP + os.path.basename(C_FILE) + ".graphml"
    EBFRunCmd = "timeout -k 2s "+str(TIMEOUT_BMC)+  " " + InputGenerationPath + ' --' + str(
         ARCHITECTURE) +  '  --no-unwinding-assertions --closure  '+  " " + C_FILE
    file= open(EBF_LOG + SEP + "runCompiBMC.log", "w")
    file_err= open(EBF_LOG + SEP + "runErrorBMC.log", "w")
    p = subprocess.Popen(EBFRunCmd,shell=True,stdout= file, stderr=file_err , universal_newlines=True, preexec_fn=limit_virtual_memory)
    p.communicate()
    if os.path.exists(EBF_DIR+SEP+'yogar-tmp'):
        shutil.rmtree(EBF_DIR+SEP+'yogar-tmp')
    if path.exists(EBF_DIR+SEP+'witness.graphml'):
        shutil.move(EBF_DIR+SEP+'witness.graphml', witness_BMC_file_name)


def ConvertInitialSeed():
    global EBF_DIR, EBF_TESTCASE, EBF_CORPUS, witness_DIR
    list = []
    testcase = witness_DIR + SEP + os.path.basename(C_FILE) + ".graphml"
    if (not (os.path.isfile(testcase) == True)):
        logWord = "Procceding"
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
                    elif item.attrib['key'] == 'assumption':
                        assumption = item.text
                        # assumption => threadid = %d;
                        try:
                            _, right = assumption.split("=")
                            # right => %d;
                            left, _ = right.split(";")
                            # left => %d
                            list.append(left.strip())
                        except:
                            pass
        if len(list) == 0:
            return
        count = 1
        with open(os.path.join(EBF_CORPUS, 'id-' + getRandomAlphanumericString()), "w") as output:
            for data in list:
                output.write(''.join(str(data)))
                output.write("\n")
            count += 1


def RandomSeed():
    global EBF_CORPUS, seed,BMC_Engine
    if [f for f in os.listdir(EBF_CORPUS) if not f.startswith('.')] == []:
        print("There is no Testcases generated From " + BMC_Engine + " ..Proceed to random inputs!\n\n")
        random.seed(seed)
        randomlist = random.sample(range(0, 5000), 15)
        n = len(randomlist)
        num_files = 5
        char_limit_per_file = n // num_files
        file_count = 1
        chunk_index = 0
        while file_count <= num_files:
            new_folder = 'id-' + getRandomAlphanumericString()
            with open(os.path.join(EBF_CORPUS, new_folder), mode="w") as out_file:
                for line in randomlist[chunk_index:chunk_index + char_limit_per_file]:
                    out_file.write(''.join(str(line)))
                    out_file.write("\n")

            chunk_index += char_limit_per_file
            file_count += 1


def runAFL():
    global EBF_EXEX, C_FILE, OUTDIR, EBF_INSTRAMENTATION, AFL_DIR, RUN_LOG, TIMEOUT_AFL, start_time, AFL_COMPILER_DIR, preprocessed_c_file, pre_C_File, AFL_Bin, AFL_FUZZ_Bin, AflExexutableFile
    if os.path.exists(EBF_EXEX):
        shutil.rmtree(EBF_EXEX)
    os.mkdir(EBF_EXEX)
    pre_C_File = EBF_DIR + SEP + "input.c"
    preprocessed_c_file = "cat " + C_FILE + " | sed -e 's/\<__inline\>//g' >  processed1 "
    preprocessed_c_file2 = "cat  processed1 | sed -e 's/\<inline\>//g' > " + pre_C_File
    os.system(preprocessed_c_file)
    os.system(preprocessed_c_file2)
    os.remove("processed1")
    Found_large_thread=False
    with open(pre_C_File,'r') as f1:
        red=f1.read()
        Found_large_thread='pthread_t t1_ids[10000]' in red or 'pthread_t t_ids[10000]' in red
    if Found_large_thread:
        runRegix=EBF_SCRIPTS+SEP+'Instrumrntation.py'
        RunInstra="python3 " + runRegix +  ' ' + pre_C_File +  ' -E ' + EBF_EXEX
        os.system(RunInstra)
    elif  'while(1) { pthread_create(&t, 0, thr1, 0)' in red or 'while(1) pthread_create(&t, 0, thr1, 0)' in red:
           print('contains large number of threads')
           return
    curTime = time.time()
    timeElapsed = curTime - start_time
    if (not ((os.path.isfile(EBF_LIB + SEP + "libmylib.a") == True) and (
            os.path.isfile(EBF_LIB + SEP + "libmylibFunctions.a") == True))):
        exitMessage = " Either libmylib.a or libmylibFunctions.a File doesn't exist in " + EBF_LIB + "!!"
        sys.exit(exitMessage)
    aflFlag = "AFL_BENCH_UNTIL_CRASH=1 AFL_I_DONT_CARE_ABOUT_MISSING_CRASHES=1 "
    if os.path.exists(AFL_DIR):
        shutil.rmtree(AFL_DIR)
    os.mkdir(AFL_DIR)
    Executable = os.path.splitext(os.path.basename(C_FILE))[0] + "_AFL"
    SetAnv = "AFL_CC"
    if SetAnv in os.environ:
        pass
    else:
        if path.exists('/usr/bin/clang-10'):
            os.environ["AFL_CC"] = "/usr/bin/clang-10"
        else:
            print(" Please set the environment \n export AFL_CC= clang-10")
            os.environ["AFL_CC"] = "/usr/bin/clang-10"
    AflExexutableFile = EBF_EXEX + SEP + Executable
    RunAfl = " AFL_LLVM_THREADSAFE_INST=1 " + AFL_Bin + Optimization + Compile_Flag + EBF_INSTRAMENTATION + pre_C_File + " " + \
             " -lpthread " + "-L" + EBF_LIB + SEP + " -lmylib -lmylibFunctions" + ' -o ' + EBF_EXEX + SEP + Executable + " 1> " + EBF_LOG + SEP + "AflCompile.log" + " 2> " + EBF_LOG + SEP + "AflCompileError.log"
    os.system(RunAfl)
    if PARALLEL_FUZZ:
        creatingPOol()
    elif CONCURRENCY:
        runTSAN()
    else:
        logWord = "Invoking the Concurrency-aware Fuzzer"
        printLogWord(logWord)
        ExecuteAfl = aflFlag + " timeout -k 2s " + str(
            TIMEOUT_AFL) + " " + AFL_FUZZ_Bin + " -i  " + EBF_CORPUS + " -o " + AFL_DIR + " -m none -t 3000+ -- " + AflExexutableFile + ' ' + " 1> " + EBF_LOG + SEP + "AflRun.log" + " 2> " + EBF_LOG + SEP + "AflrunError.log"
        SetAflenv()
        os.system(ExecuteAfl)



    logWord = "Compiling the instrumented code"
    printLogWord(logWord)


def creatingPOol():
    global found_event,finished_process,AFL_DIR

    with Pool(3) as p:  # choose appropriate level of parallelism
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


def ParallelFuzzing(inputs):
    global EBF_EXEX, C_FILE, OUTDIR, EBF_INSTRAMENTATION, AFL_DIR, RUN_LOG, TIMEOUT_AFL, start_time, AFL_COMPILER_DIR, preprocessed_c_file, pre_C_File, AFL_Bin, AFL_FUZZ_Bin, AflExexutableFile,found_event,finished_process
    logWord = "Invoking Parrallel Fuzzing"
    printLogWord(logWord)
    (nodes, outdir, logfile1) = inputs

    print("Starting node :{} with outdir {} and logfile {}".format(nodes, outdir, logfile1))
    ExecuteAfl = "AFL_BENCH_UNTIL_CRASH=1 AFL_I_DONT_CARE_ABOUT_MISSING_CRASHES=1 " + " timeout -k 2s " + str(
        TIMEOUT_AFL) + " " + AFL_FUZZ_Bin + " -i  " + EBF_CORPUS + " -o " + AFL_DIR + ' ' + nodes + ' ' + outdir + " -m none -t 3000+ -- " + AflExexutableFile + '' + " 1> " + EBF_LOG + SEP + logfile1 + " 2> " + EBF_LOG + SEP + "AflrunError.log"
    final = subprocess.Popen("{}".format(ExecuteAfl), shell=True, universal_newlines=True,
                             preexec_fn=limit_virtual_memory_AFL)
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
    global Tsanitizer, EBF_EXEX, C_FILE, EBF_LOG, EBF_LIB, EBF_INSTRAMENTATION, TIMEOUT_TSAN, start_time,EXTRA
    PATHS=''
    if EXTRA:
        for iarg in EXTRA:
            PATHS= PATHS+ " " + iarg
        Include="-I"+ f'{PATHS.lstrip()}'
    else:
        Include=''
        print("No extra includes provided\n")
    ExecutableTsan = os.path.splitext(os.path.basename(C_FILE))[0] + "_TSAN"
    CompileTasan = Compiler + Optimization + Tsanitizer + " " + C_FILE  + " "+ Include +"  -lpthread " + EBF_LIB + SEP + "atomics.c " + EBF_LIB + SEP + "nondet_rand.c " + ' -o ' + EBF_EXEX + SEP + ExecutableTsan + " 1> " + EBF_LOG + SEP + "TsanCompile.log" + " 2> " + EBF_LOG + SEP + "TasanCompileError.log"
    TSANExexutableFile = EBF_EXEX + SEP + "./" + ExecutableTsan
    print("TSAN com",CompileTasan)
    RunTsan = " timeout -k 2s " + str(
        TIMEOUT_TSAN) + " " + TSANExexutableFile + " 1> " + EBF_LOG + SEP + "TsanRun.log" + " 2> " + EBF_LOG + SEP + "TsanRunError.log"
    os.system(CompileTasan)
    os.system(RunTsan)
    logWord = "Runing Sanitizer"
    printLogWord(logWord)


def checkbothFiles(files):
    if len(files) != 2:
        return False
    file1 = files[0].startswith("witnessInfoAFL-") or files[0].startswith("seedValue-")
    file2 = files[1].startswith("witnessInfoAFL-") or files[1].startswith("seedValue-")
    return file1 and file2


def AnalaysResults():
    global RUN_LOG, AFL_DIR, RUN_STATUS_LOG
    if PARALLEL_FUZZ:
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
                    for t in crashingTestList:
                        if (t.startswith("id:")):
                            RUN_LOG.write("False(reach)\n")
                            return
        RUN_LOG.write("UNKNOWN\n")
        return
    elif CONCURRENCY:

        checkTSAN = open(EBF_LOG + SEP + "TsanRunError.log", "r")
        read3 = checkTSAN.read()
        if 'data race' in read3:
            RUN_LOG.write("False(reach)\n")
        else:
            RUN_LOG.write("UNKNOWN\n")
    else:
        checkLog = open(EBF_LOG + SEP + "AflRun.log", 'r')
        read1 = checkLog.read()
        crashDir = AFL_DIR + SEP + "default/crashes"
        if (not os.path.exists(crashDir)):
            return
        crashingTestList = os.listdir(crashDir)
        if '.DS_Store' in crashingTestList:
            crashingTestList.remove('.DS_Store')
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
    if BMC_Engine =='CBMC':
            #TODO check the BMC options and based on that check the result values.
        if "FALSE" in read2:
            if "FALSE" in read2 and "reason for conflict" in read2:
                RUN_LOG.write("UNKNOWN\n")
            else:
                RUN_LOG.write("False(reach)\n")
        elif "TRUE" in read2:
            RUN_LOG.write("true\n")
        else:
            RUN_LOG.write("UNKNOWN\n")
    elif BMC_Engine =="ESBMC":
         if "FALSE_REACH" in read2:
             RUN_LOG.write("False(reach)\n")
         elif "TRUE" in read2:
             RUN_LOG.write(" true\n")
         else:
             RUN_LOG.write("UNKNOWN\n")
    elif BMC_Engine=='CSEQ':
        if "FALSE" in read2:
            RUN_LOG.write("False(reach)\n")
        elif "SAFE" in read2:
            RUN_LOG.write(" true\n")
        else:
            RUN_LOG.write("UNKNOWN\n")

    elif BMC_Engine =='DEAGLE':
        if "VERIFICATION FAILED" in read2:
            RUN_LOG.write("False(reach)\n")
        elif "VERIFICATION SUCCESSFUL" in read2:
            RUN_LOG.write(" true\n")
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
    AFL_Results = 0
    BMC_Results=0
    RUN_LOG.close()
    with open(EBF_LOG + SEP + "run.log", "r") as f:
        for line in f:
            word = line.strip()
            if word:
                if i == 0:
                    if word == 'False(reach)':
                        AFL_Results = 1
                elif i == 1:
                    if word == 'False(reach)':
                        BMC_Results = 1
                    elif word == 'true':
                        BMC_Results = 2
            i += 1
    print("value from afl and bmc results", AFL_Results,BMC_Results,"\n")
    if BMC_Results == 2:
        print(f"{bcolors.OKGREEN}VERIFICATION TRUE\n\n{bcolors.ENDC}")
    elif BMC_Results == 1 or  AFL_Results == 1 or AFL_Results == 3:
        print(f"{bcolors.FAIL}FALSE(reach)\n\n{bcolors.ENDC}")
    else:
        print(f"{bcolors.WARNING}UNKNOWN\n\n {bcolors.ENDC}")

def correction_witness():
    global RUN_LOG
    i = 0
    BMC_Results = 0
    AFL_Results = 0
    RUN_LOG.close()
    with open(EBF_LOG + SEP + "run.log", "r") as f:
        for line in f:
            word = line.strip()
            if word:
                if i == 0:
                    if word == 'False(reach)':
                        AFL_Results = 1
                elif i == 1:
                    if word == 'False(reach)':
                        BMC_Results = 1
                    elif word == 'true':
                        BMC_Results = 2
            i += 1
    if AFL_Results == 1:
        return False
    elif BMC_Results == 1:
        return False
    else:
        f.close()
        return True


def witnessFile_pre():
    a = ''
    global witness_DIR, correction_witness
    Source = os.getcwd()
    try:
        with open("AFLCRASH", 'r') as f:
            lines = [line.strip() for line in f]
            if len(lines) == 1:
                a = lines[0]
    except:
        a = ' '
    print("Crash Process ID is", a+"\n")
    try:
        print("Removing AFLCRASH File ..")
        os.remove('AFLCRASH')
    except:
        print('we could not remove AFLCRASH file\n')
    for file in os.listdir(Source):

        if file.startswith("witnessInfoAFL-") or file.startswith("seedValue-") or file.startswith(
                "seedValueTSAN") or file.startswith("witnessInfoTSAN"):
            if file.endswith(a):
                shutil.move(os.path.join(Source, file), os.path.join(witness_DIR, file))
            else:
                os.remove(file)


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
    RunBMCEngine()
    ConvertInitialSeed()
    RandomSeed()
    startLogging()
    runAFL()
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






