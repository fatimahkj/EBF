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
C_FILE=''
SEP = os.sep
EBF_SCRIPT_DIR = os.path.split(os.path.abspath(__file__))[0]
EBF_DIR = os.path.split(EBF_SCRIPT_DIR)[0]
OUTDIR = EBF_DIR + SEP + "EBF_Results"
EBF_EXEX=''

def processCommandLineArguements():
    global C_FILE
    parser = argparse.ArgumentParser(prog="EBF", description="Tool for detecting concurrent and memory corruption bugs")
    parser.add_argument("benchmark", nargs='?', help="Path to the benchmark")
    parser.add_argument("-E", "--EXEXDirectory", help='Execution directory', action='store')
    args = parser.parse_args()
    C_FILE = args.benchmark
    EBF_EXEX = args.EXEXDirectory
    print('EBF_EXEX',EBF_EXEX)


    return args



def ProcessingInput():
    global  C_FILE,EBF_EXEX
    print ('C File=',C_FILE)
    pre_C_File = EBF_DIR + SEP + "input.c"
    preprocessed_c_file = " sed -i 's/\<10000\>/10/g' " + pre_C_File
    os.system(preprocessed_c_file)
    print("pre",pre_C_File)



def main():

    processCommandLineArguements()
    ProcessingInput()

if __name__ == "__main__":
    main()


