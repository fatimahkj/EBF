#!/usr/bin/env python3
import os.path  # To check if file exists
import xml.etree.ElementTree as ET  # To parse XML
import os,shutil
import argparse
import shlex
import subprocess
import time
import sys
import resource
import re

start_time = time.time()
SEP = os.sep
EBF_SCRIPT_DIR = os.path.split(os.path.abspath(__file__))[0]
EBF_DIR = os.path.split(EBF_SCRIPT_DIR)[0]
EBF_PATH=EBF_DIR+SEP+"lib"
OUTDIR = EBF_DIR + SEP + "Results"
witness_File=OUTDIR+SEP+"witness-File"
ESBMC_DIR=EBF_DIR + SEP+"bin"
# Start time for this script
property_file_content = ""
testcase_file=""
__graphml_base__ = '{http://graphml.graphdrawing.org/xmlns}'
__graph_tag__ = __graphml_base__ + 'graph'
__edge_tag__ = __graphml_base__ + 'edge'
__data_tag__ = __graphml_base__ + 'data'
__testSuiteDir__ = "test-suite/"
#__testSuiteDir__ = EBF_DIR + SEP + "Results" + SEP + "test-suite/"
class AssumptionHolder(object):
    """Class to hold line number and assumption from ESBMC Witness."""

    def __init__(self, line, assumption):
        """
        Default constructor.

        Parameters
        ----------
        line : unsigned
            Line Number from the source file
        assumption : str
            Assumption string from ESBMC.
        """
        assert(line >= 0)
        assert(len(assumption) > 0)
        self.line = line
        self.assumption = assumption

    def debugInfo(self):
        """Print info about the object"""
        print("AssumptionInfo: LINE: {0}, ASSUMPTION: {1}".format(self.line, self.assumption))


class AssumptionParser(object):
    """Class to parse a witness file generated from ESBMC and create a Set of AssumptionHolder."""

    def __init__(self, witness):
        """
        Default constructor.

        Parameters
        ----------

        witness : str
            Path to witness file (absolute/relative)
        """
        #assert(os.path.isfile(witness))
        self.__xml__ = None
        self.assumptions = list()
        self.__witness__ = witness

    def __openwitness__(self):
        """Parse XML file using ET"""
        self.__xml__ = ET.parse(self.__witness__).getroot()

    def parse(self):
        """ Iterates over all elements of GraphML and extracts all Assumptions """
        if self.__xml__ is None:
            self.__openwitness__()
        graph = self.__xml__.find(__graph_tag__)
        for node in graph:
            if(node.tag == __edge_tag__):
                startLine = 0
                assumption = ""
                for data in node:
                    if data.attrib['key'] == 'startline':
                        startLine = int(data.text)
                    elif data.attrib['key'] == 'assumption':
                        assumption = data.text
                if assumption != "":
                    self.assumptions.append(AssumptionHolder(startLine, assumption))

    def debugInfo(self):
        """Print current info about the object"""
        print("XML: {0}".format(self.__witness__))
        print("ET: {0}".format(self.__xml__))
        for assumption in self.assumptions:
            assumption.debugInfo()


class MetadataParser(object):
    """Class to parse a witness file generated from ESBMC and extract all metadata from it."""

    def __init__(self, witness):
        """
        Default constructor.

        Parameters
        ----------

        witness : str
            Path to witness file (absolute/relative)
        """
        assert(os.path.isfile(witness))
        self.__xml__ = None
        self.metadata = {}
        self.__witness__ = witness

    def __openwitness__(self):
        """Parse XML file using ET"""
        self.__xml__ = ET.parse(self.__witness__).getroot()

    def parse(self):
        """ Iterates over all elements of GraphML and extracts all Metadata """
        if self.__xml__ is None:
            self.__openwitness__()
        graph = self.__xml__.find(
            __graph_tag__)
        for node in graph:
            if(node.tag == __data_tag__):
                self.metadata[node.attrib['key']] = node.text


class NonDeterministicCall(object):
    def __init__(self, value):
        """
        Default constructor.

        Parameters
        ----------
        value : str
            String containing value from input
        """
        assert(len(value) > 0)
        self.value = value

    @staticmethod
    def extract_byte_little_endian(value):
        """
        Converts an byte_extract_little_endian((unsigned int)%d, %d) into an value

                Parameters
        ----------
        value : str
            Nondeterministic assumption
        """

        PATTERN = 'byte_extract_little_endian\(\(unsigned int\)(.+), (.+)\)'
        INT_BYTE_SIZE = 4
        match = re.search(PATTERN, value)
        if match == None:
            return value
        number = match.group(1)
        index = match.group(2)

        byte_value = (int(number)).to_bytes(INT_BYTE_SIZE, byteorder='little', signed=True)

        return str(byte_value[int(index)])

    @staticmethod
    def fromAssumptionHolder(assumption):
        """
        Converts an Assumption (that is nondet, this function will not verify this) into a NonDetermisticCall

        Parameters
        ----------
        assumption : AssumptionHolder
            Nondeterministic assumption
        """
        try:
            _, right = assumption.assumption.split("=")
            left, _ = right.split(";")
            assert(len(right) > 0)
            if left[-1] == "f" or left[-1] == "l":
                left = left[:-1]
            value = NonDeterministicCall.extract_byte_little_endian(left.strip())
            return NonDeterministicCall(value)
        except:
            return None

    def debugInfo(self):
        print("Nondet call: {0}".format(self.value))


class SourceCodeChecker(object):
    """
        This class will read the original source file and checks if lines from assumptions contains nondeterministic calls
    """

    def __init__(self, source, assumptions):
        """
        Default constructor.

        Parameters
        ----------
        source : str
            Path to source code file (absolute/relative)
        assumptions : [AssumptionHolder]
            List containing all assumptions of the witness
        """
        assert(os.path.isfile(source))
        assert(assumptions is not None)
        self.source = source
        self.assumptions = assumptions
        self.__lines__ = None

    def __openfile__(self):
        """Open file in READ mode"""
        self.__lines__ = open(self.source, "r").readlines()

    def __is_not_repeated__(self, i):
        x = self.assumptions[i]
        y = self.assumptions[i+1]

        if x.line != y.line:
            return True

        _, x_right = x.assumption.split("=")
        _, y_right = y.assumption.split("=")

        return x_right != y_right

    def __isNonDet__(self, assumption):
        """
            Checks if assumption is nondet by checking if line contains __VERIFIER_nondet
        """

        if "=" in assumption.assumption:
            check_cast = assumption.assumption.split("=")
            if len(check_cast) > 1:
                if check_cast[1].startswith(" ( struct "):
                    return False

        if self.__lines__ is None:
            self.__openfile__()
        lineContent = self.__lines__[assumption.line - 1]
        # At first we do not care about variable name or nondet type
        # TODO: Add support to variable name
        # TODO: Add support to nondet type

        result = lineContent.split("__VERIFIER_nondet_")
        return len(result) > 1
        # return right != ""

    def getNonDetAssumptions(self):
        filtered_assumptions = list()
        for i in range(len(self.assumptions)-1):
            if self.__is_not_repeated__(i):
                filtered_assumptions.append(self.assumptions[i])
        if(len(self.assumptions)>0):
            filtered_assumptions.append(self.assumptions[-1])
        return [NonDeterministicCall.fromAssumptionHolder(x) for x in filtered_assumptions if self.__isNonDet__(x)]

    def getNonDetAssumptions_New(self):

        newList=[]

        for i in range(len(self.assumptions)-1):
            if self.__is_not_repeated__(i):
                #holder is NonDeterministicCall: it has only value
                holder = NonDeterministicCall.fromAssumptionHolder(self.assumptions[i])
                if holder != None:
                    newList.append(holder)

        return newList

    def debugInfo(self):
        for x in self.getNonDetAssumptions():
            x.debugInfo()


class TestCompMetadataGenerator(object):
    def __init__(self, metadata):
        """
        Default constructor.

        Parameters
        ----------
        metadata : { key: value}
            A dictionary containing metada info
        """
        self.metadata = metadata

    def writeMetadataFile(self):
        """ Write metadata.xml file """
        root = ET.Element("test-metadata")
        # TODO: add support to enter function
        ET.SubElement(root, 'entryfunction').text = 'main'
        ET.SubElement(root, 'specification').text = property_file_content.strip()
        properties = {'sourcecodelang', 'sourcecodelang', 'producer',
                      'programfile', 'programhash', 'architecture', 'creationtime'}
        for property in properties:
            ET.SubElement(root, property).text = self.metadata[property]

        output = os.path.join(__testSuiteDir__, "metadata.xml")
        ET.ElementTree(root).write(output)
        with open(output, 'r') as original: data = original.read()
        with open(output, 'w') as modified: modified.write(
            '<?xml version="1.0" encoding="UTF-8" standalone="no"?><!DOCTYPE test-metadata PUBLIC "+//IDN sosy-lab.org//DTD test-format test-metadata 1.0//EN" "https://sosy-lab.org/test-format/test-metadata-1.0.dtd">' + data)


class TestCompGenerator(object):
    def __init__(self, nondetList):
        """
        Default constructor.

        Parameters
        ----------
        value : [NonDeterministicCall]
            All NonDeterministicCalls from the program
        """
        self.__root__ = ET.Element("testcase")
        for inputData in nondetList:
            ET.SubElement(self.__root__, "input").text = inputData.value

    def writeTestCase(self, output):
        """
        Write testcase into XML file.

        Parameters
        ----------
        output : str
            filename (with extension)
        """
        ET.ElementTree(self.__root__).write(output)
        with open(output, 'r') as original: data = original.read()
        with open(output, 'w') as modified: modified.write('<?xml version="1.0" encoding="UTF-8" standalone="no"?><!DOCTYPE testcase PUBLIC "+//IDN sosy-lab.org//DTD test-format testcase 1.0//EN" "https://sosy-lab.org/test-format/testcase-1.0.dtd">' + data)

def __getNonDetAssumptions__(witness, source):
    assumptionParser = AssumptionParser(witness)
    assumptionParser.parse()
    #assumptionParser.debugInfo()
    assumptions = assumptionParser.assumptions
    return SourceCodeChecker(source, assumptions).getNonDetAssumptions_New()


def createTestFile(witness, source):
    assumptions = __getNonDetAssumptions__(witness, source)
    TestCompGenerator(assumptions).writeTestCase(os.path.join(__testSuiteDir__, "testcase.xml"))
    metadataParser = MetadataParser(witness)
    metadataParser.parse()
    TestCompMetadataGenerator(metadataParser.metadata).writeMetadataFile()

class Result:
    success = 1
    fail_deref = 2
    fail_memtrack = 3
    fail_free = 4
    fail_reach = 5
    fail_overflow = 6
    err_timeout = 7
    err_memout = 8
    err_unwinding_assertion = 9
    force_fp_mode = 10
    unknown = 11
    fail_memcleanup = 12

    @staticmethod
    def is_fail(res):
        if res == Result.fail_deref:
            return True
        if res == Result.fail_free:
            return True
        if res == Result.fail_memtrack:
            return True
        if res == Result.fail_overflow:
            return True
        if res == Result.fail_reach:
            return True
        if res == Result.fail_memcleanup:
            return True
        return False

    @staticmethod
    def is_out(res):
        if res == Result.err_memout:
            return True
        if res == Result.err_timeout:
            return True
        if res == Result.unknown:
            return True
        return False

# Enum -> {1...5}
# print(Property.memory)
class Property:
    reach = 1
    memory = 2
    overflow = 3
    termination = 4
    memcleanup = 5


# Function to run esbmc


def run(cmd_line):
    print ("Verifying with ESBMC and generate initial seed")
    print ("Command: " + cmd_line)

    the_args = shlex.split(cmd_line)
    p = subprocess.Popen(the_args, stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    (stdout, stderr) = p.communicate()

    print (stdout.decode(), stderr.decode())
    return stdout.decode()


def parse_result(the_output, prop):

    # Parse output
    if "Timed out" in the_output:
        return Result.err_timeout

    if "Out of memory" in the_output:
        return Result.err_memout

    if "Chosen solver doesn\'t support floating-point numbers" in the_output:
        return Result.force_fp_mode

    # Error messages:
    memory_leak = "dereference failure: forgotten memory"
    invalid_pointer = "dereference failure: invalid pointer"
    access_out = "dereference failure: Access to object out of bounds"
    dereference_null = "dereference failure: NULL pointer"
    invalid_object = "dereference failure: invalidated dynamic object"
    invalid_object_free = "dereference failure: invalidated dynamic object freed"
    invalid_pointer_free = "dereference failure: invalid pointer freed"
    free_error = "dereference failure: free() of non-dynamic memory"
    bounds_violated = "array bounds violated"
    free_offset = "Operand of free must have zero pointer offset"

    if "VERIFICATION FAILED" in the_output:
        if "unwinding assertion loop" in the_output:
            return Result.err_unwinding_assertion

        if prop == Property.memcleanup:
            if memory_leak in the_output:
                return Result.fail_memcleanup

        if prop == Property.memory:
            if memory_leak in the_output:
                return Result.fail_memtrack

            if invalid_pointer_free in the_output:
                return Result.fail_free

            if invalid_object_free in the_output:
                return Result.fail_free

            if invalid_pointer in the_output:
                return Result.fail_deref

            if dereference_null in the_output:
                return Result.fail_deref

            if free_error in the_output:
                return Result.fail_free

            if access_out in the_output:
                return Result.fail_deref

            if invalid_object in the_output:
                return Result.fail_deref

            if bounds_violated in the_output:
                return Result.fail_deref

            if free_offset in the_output:
                return Result.fail_free

            if " Verifier error called" in the_output:
                return Result.success

        if prop == Property.overflow:
            return Result.fail_overflow

        if prop == Property.reach:
            return Result.fail_reach

    if "VERIFICATION SUCCESSFUL" in the_output:
        return Result.success

    return Result.unknown



def get_result_string(the_result):
    if the_result == Result.fail_memcleanup:
        return "FALSE_MEMCLEANUP"

    if the_result == Result.fail_memtrack:
        return "FALSE_MEMTRACK"

    if the_result == Result.fail_free:
        return "FALSE_FREE"

    if the_result == Result.fail_deref:
        return "FALSE_DEREF"

    if the_result == Result.fail_overflow:
        return "FALSE_OVERFLOW"

    if the_result == Result.fail_reach:
        return "DONE"

    if the_result == Result.success:
        return "DONE"

    if the_result == Result.err_timeout:
        return "Timed out"

    if the_result == Result.err_unwinding_assertion:
        return "Unknown"

    if the_result == Result.err_memout:
        return "Unknown"

    if the_result == Result.unknown:
        return "Unknown"

    exit(0)

#esbmc_path = "/home/fatimahj/Desktop/esbmc-new/esbmc/release/bin"
#esbmc_path ="./esbmc"
esbmc_path =ESBMC_DIR+SEP+ "./esbmc "
if(os.path.exists(ESBMC_DIR) == False):
    exitMessage = "bin directory is not found !!!"
    sys.exit(exitMessage)


# ESBMC default commands: this is the same for every submission
esbmc_dargs = "--timeout 5m --memlimit 6g --no-div-by-zero-check --force-malloc-success --state-hashing "
esbmc_dargs += "--no-align-check --k-step 5 --floatbv --unlimited-k-steps "
esbmc_dargs += "--overflow-check  "
esbmc_dargs += "--no-slice --unwind 10 "
#esbmc_dargs += " --data-races-check --incremental-cb  "


def get_command_line(strat, prop, arch, benchmark, concurrency, esbmc_dargs):
    command_line = esbmc_path + esbmc_dargs
    #command_line = esbmc_path

    # Add benchmark
    command_line += benchmark + " "

    # Add arch
    if arch == 32:
        command_line += "--32 "
    else:
        command_line += "--64 "

    if concurrency:
        command_line+= " --no-por --context-bound 2 --yices "
    # Add witness arg
    witness_file_name = os.path.basename(benchmark) + ".graphml "
    command_line += "--witness-output " + witness_file_name + " "

    # Special case for termination, it runs regardless of the strategy
    if prop == Property.termination:
        command_line += "--no-pointer-check --no-bounds-check --no-assertions "
        command_line += "--termination "
        return command_line

    # Add strategy
    if strat == "kinduction":
        command_line += "--bidirectional "
    elif strat == "falsi":
        command_line += "--falsification "
    elif strat == "incr":
        command_line += "--incremental-bmc "
    else:
        print ("Unknown strategy")
        exit(1)

    if prop == Property.overflow:
        command_line += "--no-pointer-check --no-bounds-check --overflow-check --no-assertions "
    elif prop == Property.memory:
        command_line += "--memory-leak-check "
        command_line += "--context-bound 2 "
    elif prop == Property.memcleanup:
        command_line += "--memory-leak-check --no-assertions "
    elif prop == Property.reach:
        command_line += "--no-pointer-check --no-bounds-check --interval-analysis  "
    else:
        print ("Unknown property")
        exit(1)
    return command_line


def verify(strat, prop, concurrency, dargs):
    # Get command line
    esbmc_command_line = get_command_line(strat, prop, arch, benchmark, concurrency, dargs)

    # Call ESBMC
    output = run(esbmc_command_line)

    res = parse_result(output, category_property)
    return res

    # Parse output
    #return res

# Parsing Arguments
# Options
parser = argparse.ArgumentParser()
parser.add_argument("-a", "--arch", help="Either 32 or 64 bits", type=int, choices=[32, 64], default=32)
#parser.add_argument("-v", "--version",help="Prints ESBMC's version", action='store_true')
parser.add_argument("-p", "--propertyfile", help="Path to the property file")
parser.add_argument("benchmark", nargs='?', help="Path to the benchmark")
parser.add_argument("-s", "--strategy", help="ESBMC's strategy", choices=["kinduction", "falsi", "incr"], default="incr")
parser.add_argument("-c", "--concurrency", help="Set concurrency flags", action='store_true')
args = parser.parse_args()

arch = args.arch
#version = args.version
property_file = args.propertyfile
benchmark = args.benchmark
strategy = args.strategy
concurrency = args.concurrency

#if version:
#	print (os.popen(esbmc_path + "--version").read()[6:]),
#	exit(0)

# Validating Arguments

if property_file is None:
    print ("Please, specify a property file")
    exit(1)

if benchmark is None:
    print ("Please, specify a benchmark to verify")
    exit(1)


# Parse property files
f = open(property_file, 'r')
property_file_content = f.read()

category_property = 0
if "CHECK( init(main()), LTL(G valid-free) )" in property_file_content:
    category_property = Property.memory
elif "CHECK( init(main()), LTL(G ! overflow) )" in property_file_content:
    category_property = Property.overflow
#elif "CHECK( init(main()), LTL(G ! call(__VERIFIER_error())) )" in property_file_content:
    #category_property = Property.reach
elif "CHECK( init(main()), LTL(G ! call(reach_error())) )" in property_file_content:
    category_property = Property.reach
elif "CHECK( init(main()), LTL(F end) )" in property_file_content:
    category_property = Property.termination
elif "COVER( init(main()), FQL(COVER EDGES(@CALL(__VERIFIER_error))) )" in property_file_content:
    category_property = Property.reach
elif "COVER( init(main()), FQL(COVER EDGES(@DECISIONEDGE)) )" in property_file_content:
    print("Unknown")
    exit(0)
else:
    print ("Unsupported Property")
    exit(1)

result = verify(strategy, category_property, concurrency, esbmc_dargs)
print (get_result_string(result))
witness_file_name = os.path.basename(benchmark) + ".graphml"

# Check if witness was created
if not os.path.exists(witness_file_name):
    exit(0)

if not os.path.exists(__testSuiteDir__):
    os.mkdir(__testSuiteDir__)
createTestFile(witness_file_name, benchmark)
shutil.move(witness_file_name, witness_File)
