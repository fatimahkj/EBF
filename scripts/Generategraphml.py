import os,re
from datetime import datetime
import xml.etree.cElementTree as ET
from xml.dom import minidom
import hashlib
from Extract_assumptions import __getNonDetAssumptions__


class Value:
    def __init__(self, var_name, line, value, threadid, function_name):
        self.var_name = var_name
        self.value = value
        self.line = line
        self.function_name = function_name
        self.threadid = threadid


    
    def generate_assumption(self):
        #return ""
        if(self.var_name == ""):
            return self.value
        #if we want to remove ; after a=value
        #return self.value[:-1]
        return (str(self.var_name) + "=" + str(self.value) )

class ViolationGraph:

    @staticmethod
    def GetSH1ForFile(fil):
        BUF_SIZE = 32768
        sha1 = hashlib.sha256()
        with open(fil, 'rb') as f:
            while True:
                data = f.read(BUF_SIZE)
                if not data:
                    break
                sha1.update(data)
            return sha1.hexdigest()

        return ''

    def __init__(self, C_FILE, PROPERTY_FILE, ARCHITECTURE, witness_dir,witness_bmc,CORRECT_WITNESS,BMC_Engine):
        self.xml = ET.Element('graphml')
        self.xml.set("xmlns", "http://graphml.graphdrawing.org/xmlns")
        self.xml.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
        self.now = datetime.now()
        self.N = 0
        self.E = 0
        self.LastNode = None
        self.threads = []
        self.witness_dir = witness_dir
        self._initialize_graph(C_FILE, PROPERTY_FILE, ARCHITECTURE,CORRECT_WITNESS)
        self.witness_bmc=witness_bmc
        self.BMC_Engine=BMC_Engine
    #    T0        T1      T2
    # [2321432, 1341234, 13451]
    def find_thread(self, threadid):
        try:
            return str(self.threads.index(threadid))
        except:
            self.threads.append(threadid)
            return str(self.threads.index(threadid))

    @staticmethod
    def create_key_node(_id, _name, _type, _for):
        elem = ET.Element("key", id=_id)
        elem.set("attr.name", _name)
        elem.set("attr.type", _type)
        elem.set("for", _for)
        return elem

    def _initialize_graph(self, C_FILE, PROPERTY_FILE, ARCHITECTURE,CORRECT_WITNESS):

        elem = ViolationGraph.create_key_node("frontier", "isFrontierNode", "boolean", "node")
        ET.SubElement(elem, "default").text="false" # Creating default value
        self.xml.append(elem)

        elem = ViolationGraph.create_key_node("violation", "isViolationNode", "boolean", "node")
        ET.SubElement(elem, "default").text="false"
        self.xml.append(elem)

        elem = ViolationGraph.create_key_node("entry", "isEntryNode", "boolean", "node")
        ET.SubElement(elem, "default").text="false"
        self.xml.append(elem)

        elem = ViolationGraph.create_key_node("sink", "isSinkNode", "boolean", "node")
        ET.SubElement(elem, "default").text="false"
        self.xml.append(elem)

        elem = ViolationGraph.create_key_node("cyclehead", "cyclehead", "boolean", "node")
        ET.SubElement(elem, "default").text="false"
        self.xml.append(elem)

        elem = ViolationGraph.create_key_node("sourcecodelang", "sourcecodeLanguage", "string", "graph")
        self.xml.append(elem)

        elem = ViolationGraph.create_key_node("programfile", "programfile", "string", "graph")
        self.xml.append(elem)

        elem = ViolationGraph.create_key_node("programhash", "programhash", "string", "graph")
        self.xml.append(elem)

        elem = ViolationGraph.create_key_node("creationtime", "creationtime", "string", "graph")
        self.xml.append(elem)

        elem = ViolationGraph.create_key_node("specification", "specification", "string", "graph")
        self.xml.append(elem)

        elem = ViolationGraph.create_key_node("architecture", "architecture", "string", "graph")
        self.xml.append(elem)

        elem = ViolationGraph.create_key_node("producer", "producer", "string", "graph")
        self.xml.append(elem)

        elem = ViolationGraph.create_key_node("sourcecode", "sourcecode", "string", "edge")
        self.xml.append(elem)

        elem = ViolationGraph.create_key_node("startline", "startline", "int", "edge")
        self.xml.append(elem)

        elem = ViolationGraph.create_key_node("startoffset", "startoffset", "int", "edge")
        self.xml.append(elem)

        elem = ViolationGraph.create_key_node("control", "control", "string", "edge")
        self.xml.append(elem)

        elem = ViolationGraph.create_key_node("invariant", "invariant", "string", "node")
        self.xml.append(elem)

        elem = ViolationGraph.create_key_node("invariant.scope", "invariant.scope", "string", "node")
        self.xml.append(elem)

        elem = ViolationGraph.create_key_node("assumption", "assumption", "string", "edge")
        self.xml.append(elem)

        elem = ViolationGraph.create_key_node("assumption.scope", "assumption", "string", "edge")
        self.xml.append(elem)

        elem = ViolationGraph.create_key_node("assumption.resultfunction", "assumption.resultfunction", "string", "edge")
        self.xml.append(elem)

        elem = ViolationGraph.create_key_node("enterFunction", "enterFunction", "string", "edge")
        self.xml.append(elem)

        elem = ViolationGraph.create_key_node("returnFromFunction", "returnFromFunction", "string", "edge")
        self.xml.append(elem)

        elem = ViolationGraph.create_key_node("endline", "endline", "int", "edge")
        self.xml.append(elem)

        elem = ViolationGraph.create_key_node("endoffset", "endoffset", "int", "edge")
        self.xml.append(elem)

        elem = ViolationGraph.create_key_node("threadId", "threadId", "string", "edge")
        self.xml.append(elem)

        elem = ViolationGraph.create_key_node("createThread", "createThread", "string", "edge")
        self.xml.append(elem)

        elem = ViolationGraph.create_key_node("witness-type", "witness-type", "string", "graph")
        self.xml.append(elem)

        self.graph = ET.Element('graph', edgedefault="directed")
        self.xml.append(self.graph)

        elem = ET.Element("data", key="producer")
        elem.text = "EBF"
        self.graph.append(elem)

        elem = ET.Element("data", key="sourcecodelang")
        elem.text = "C"
        self.graph.append(elem)

        elem = ET.Element("data", key="programfile")
        elem.text = str(C_FILE)
        self.graph.append(elem)

        c_file_hash = ViolationGraph.GetSH1ForFile(C_FILE)
        elem = ET.Element("data", key="programhash")
        elem.text = str(c_file_hash)
        self.graph.append(elem)

        elem = ET.Element("data", key="specification")
        f = open(PROPERTY_FILE, 'r')
        property_file_content = f.read()
        elem.text = property_file_content.strip()
        self.graph.append(elem)

        elem = ET.Element("data", key="architecture")

        elem.text = str(ARCHITECTURE)+ "bit"
        self.graph.append(elem)

        elem = ET.Element("data", key="creationtime")
        now = datetime.now()
        #elem.text = now.strftime("%Y-%m-%dT%H:%M:%S.%f")
        elem.text= now.strftime('%Y-%m-%dT%H:%M:%SZ')
        self.graph.append(elem)
        if CORRECT_WITNESS:
            self.init_correct_witness()
        else:
            self.init_violation_witness()
    def init_correct_witness(self):
        elem = ET.Element("data", key="witness-type")
        elem.text = "correctness_witness"
        self.graph.append(elem)

        # Adds N0 (default)
        elem = self.add_node()
        self.graph.append(elem)

        # Adds N1 (default)
        elem = self.add_node()
        self.graph.append(elem)

        # E0 = N0 -> N1 (default)
        elem = self._create_initial_edge()
        self.graph.append(elem)

    def init_violation_witness(self):
        elem = ET.Element("data", key="witness-type")
        elem.text = "violation_witness"
        self.graph.append(elem)

        # Adds N0 (default)
        elem = self.add_node()
        self.graph.append(elem)

        # Adds N1 (default)
        elem = self.add_node()
        self.graph.append(elem)

        # E0 = N0 -> N1 (default)
        elem = self._create_initial_edge()
        self.graph.append(elem)

    def read_values_from_ebf(self, file_prefix):
        if not os.path.exists(self.witness_dir):
            print (self.witness_dir, "\ndirectory is not exist")
            exit(0)
        found_witness_afl = False
        for file in os.listdir(self.witness_dir):
            if file.startswith(file_prefix):
                found_witness_afl = True
                with open(os.path.join(self.witness_dir, file), 'r') as AlfWitnessFile:
                    CheckInfo = AlfWitnessFile.read()
                    if len(CheckInfo)==0:
                        CheckInfo=None
                        raise RuntimeError("\nThe witness is empty")
        if not found_witness_afl:
            raise RuntimeError("\nCouldn't find a witness")

        p = re.compile("Setting variable: (.*) in Line number (.*) with value: (.*) running from thread: (.*) in function: (.*) with address:(.*)" )
        result = p.findall(CheckInfo)
        values = [ Value(a,b,c,d,e) for (a,b,c,d,e,_) in result]
        return values
    #This function will read the assumptions values from witnessInfoAFL generated from AFL 
    def read_values_from_afl(self):
        return self.read_values_from_ebf('witnessInfoAFL')
    #This function will extract the assumptions values from ESBMC witness file
    def read_values_from_ESBMC(self):
        print("Found Values from ESBMC")
        if os.path.exists(self.witness_bmc):
            from_esbmc = __getNonDetAssumptions__(self.witness_bmc)
            values = [ Value("",str(x.line),x.assumption,x.threadid,"") for x in from_esbmc ]
            return values
        raise RuntimeError("\nCouldn't find the ESBMC witness")

    #This function will extract the assumptions values from CBMC counter example using regex. 
    def read_values_from_cbmc(self):
        if os.path.exists(self.witness_bmc):
            with open(self.witness_bmc, 'r') as CBMCconterExample:
                CheckInfo = CBMCconterExample.read()
                if len(CheckInfo) == 0:
                    CheckInfo = None
                    raise RuntimeError("\nThe witness is empty")
            p = re.compile("State \d* file .* function (.*) line (\d+) thread (\d+)")
            result = p.findall(CheckInfo)
            values = [Value( "", str(b), "", c, a) for (a, b, c) in result]
            return values
        raise RuntimeError("\nCouldn't find the CBMC witness")
        
    #This function will extract the assumptions values from Cseq witness. 
    def read_values_from_CSEQ(self):
        print("Found Values from CSEQ")
        if os.path.exists(self.witness_bmc):
            from_cseq = __getNonDetAssumptions__(self.witness_bmc)
            values = [ Value("",str(x.line),x.assumption,x.threadid,"") for x in from_cseq ]
            return values
        raise RuntimeError("\nCouldn't find the CSEQ witness")
    #This function will extract the assumptions values from DEAGLE witness. 
    def read_values_from_DEAGLE(self):
        print("Found Values from DEAGLE")
        if os.path.exists(self.witness_bmc):
            from_deagle = __getNonDetAssumptions__(self.witness_bmc)
            values = [ Value("",str(x.line),x.assumption,x.threadid,"") for x in from_deagle]
            return values
        raise RuntimeError("\nCouldn't find the DEAGLE witness")


    # This function will generate the values for the witness.
    # First, it will check if AFL generate values, if not it will check which BMC engine we used then will generate the values in the witness

    def create_witness_from_tools(self, witness_DIR):
        # AFL -> ESBMC
        # Try parsing AFL
        try:
            values = self.read_values_from_afl()
            print("Found AFL values")

        except Exception as e:
            try:
                if self.BMC_Engine=='CBMC':
                    values = self.read_values_from_cbmc()
                    print("Found CBMC values")
                elif self.BMC_Engine=='ESBMC':
                    values=self.read_values_from_ESBMC()
                elif self.BMC_Engine=="CSEQ":
                    values=self.read_values_from_CSEQ()
                elif self.BMC_Engine=='DEAGLE':
                    values=self.read_values_from_DEAGLE()
                # Couldn't find any witness, generate an empty violation (maybe dangerous, should be certain that at leas one of tools found a bug)
            except Exception as e:
                print(e)
                print ("Couldn't find any values from ",self.BMC_Engine )
                values = []
        if values is None:
            values = []
        self.values_length=len(values)
        for V in values:
            elem = self.add_node()
            self.graph.append(elem)
            edge = self.create_edge(V.line, V.generate_assumption(), V.threadid)
            self.graph.append(edge)



    def add_node(self):
        elem = ET.Element("node", id="N"+str(self.N))
        if (self.N == 0):
            ViolationGraph.make_node_entry(elem)
        self.N = self.N + 1
        self.LastNode = elem
        # TODO: self.graph.append(elem)
        return elem

    @staticmethod
    def make_node_entry(node):
        ET.SubElement(node, "data", key="entry").text="true"

    @staticmethod
    def make_node_violation(node):
        ET.SubElement(node, "data", key="violation").text="true"

    def _create_initial_edge(self):
        # Always create an edge between the two last Nodes
        source = "N" + str(self.N - 2)
        target = "N" + str(self.N - 1)
        edge = ET.Element("edge", id="E"+str(self.E), source=source, target=target)
        self.E = self.E + 1
        ET.SubElement(edge, "data", key="enterFunction").text="main"
        ET.SubElement(edge, "data", key="createThread").text="0"
        return edge

    def create_edge(self, line, assumption, thread):
        # Always create an edge between the two last Nodes
        source = "N" + str(self.N - 2)
        target = "N" + str(self.N - 1)
        edge = ET.Element("edge", id="E"+str(self.E), source=source, target=target)
        self.E = self.E + 1

        ET.SubElement(edge, "data", key="threadId").text=self.find_thread(thread)
        ET.SubElement(edge, "data", key="startline").text=line
        ET.SubElement(edge, "data", key="assumption").text=assumption
        #ET.SubElement(edge, "data", key="threadId").text=thread

        return edge

    def save_witness(self, witness_file_name):
        ViolationGraph.make_node_violation(self.LastNode)

        dom = minidom.parseString(ET.tostring(self.xml))
        xml_string = dom.toprettyxml(encoding="utf-8")


        with open (witness_file_name, "wb") as files :
            files.write(xml_string)
            files.close()
            
    def removeCBMC_witness(self, witness_file_name_CBMC):
        if  os.path.isfile(witness_file_name_CBMC):
            os.remove(witness_file_name_CBMC)


