#!/usr/bin/env python3

import os
import argparse
import Generategraphml
SEP = os.sep
EBF_SCRIPT_DIR = os.path.split(os.path.abspath(__file__))[0]
EBF_DIR = os.path.split(EBF_SCRIPT_DIR)[0]
witness_DIR = ""
EBF_SCRIPTS=EBF_DIR+SEP+"scripts"
PROPERTY_FILE = ""
C_FILE = ""
ARCHITECTURE=""
CBMCwitness=""
BMC_Engine=""
CORRECTNESS=None

def processCommandLineArguements():
    global C_FILE, PROPERTY_FILE,ARCHITECTURE,CORRECTNESS,witness_DIR,EBF_DIR,CBMCwitness,BMC_Engine
    parser = argparse.ArgumentParser(prog="WitnessFileGeneration", description="To Generate violation witness for SV-COMP")
    parser.add_argument("benchmark", nargs='?', help="Path to the benchmark")
    parser.add_argument('-p', "--propertyfile", required=True, help="Path to the property file")
    parser.add_argument("-a", "--arch", help="Either 32 or 64 bits", type=int, choices=[32, 64], default=32)
    parser.add_argument('--witnessType', help= 'if set generate correctness witness File')
    parser.add_argument("-w", "--witnessDirectory", help='Directory for stor Witness', action='store')
    parser.add_argument("-l", "--cbmcwitness", help='cbmc Witness directory (counter example in log file)', action='store')
    parser.add_argument( "-bmc", help="Set BMC engine", choices=["ESBMC", "CBMC", "CSEQ","DEAGLE"],default="ESBMC")

    args = parser.parse_args()
    PROPERTY_FILE = args.propertyfile
    C_FILE = args.benchmark
    ARCHITECTURE = args.arch
    CORRECTNESS=args.witnessType=='correct'
    witness_DIR = args.witnessDirectory
    CBMCwitness=args.cbmcwitness
    BMC_Engine=args.bmc





def witnessFile():
    global C_FILE

    witness_file_name = os.path.basename(C_FILE) +".EBF.graphml"
    if BMC_Engine=='CBMC':
            witness_file_name_BMC=os.path.join(CBMCwitness,"runCompiBMC.log")
    elif BMC_Engine=='ESBMC' or BMC_Engine=='CSEQ' or BMC_Engine=='DEAGLE':
            witness_file_name_BMC = os.path.join(witness_DIR + SEP +os.path.basename(C_FILE) + ".graphml")
    Graph = Generategraphml.ViolationGraph(C_FILE, PROPERTY_FILE, ARCHITECTURE, witness_DIR,witness_file_name_BMC,CORRECTNESS,BMC_Engine)
    if not CORRECTNESS:
        Graph.create_witness_from_tools(witness_DIR)
    Graph.save_witness(witness_file_name)




def main():
    processCommandLineArguements()
    witnessFile()

if __name__ == "__main__":
   main()


