#!/usr/bin/env python
'''
    SV-COMP 2020 parallel experiment simulation
         for
    CSeq 1.9 wrapper script for Lazy Configuration

	2019.11.17  bugfix: Command.run default timeout is None (not 0)
	2019.11.17  bugfix: script no longer terminating upon hitting timelimit
	2019.11.16  timeout for witness validator set in its own commandline
	2019.11.11  a non-verified witness now means FAIL
	2019.11.11  now using external .yml file to compare against expected verification outcome
    2018.11.25  can now run on a single program
    2018.11.23  command-line options
    2018.11.09  witness checking

'''
import sys, getopt
import os, sys
from glob import glob


# limits for the overall procedure to be checked at the very end (TODO)
membound = 16   # GB
timebound = 900

CPUS_WITNESS_NO_QUICK = 16   # in quick mode use all cores
CPUS_WITNESS_NO = 12         # by default, do not use all the CPUs to avoid performance fluctuations
CPUS_WITNESS = 10            # when validating witnesses, leave some cores for the witness checker as it spawns its own threads

memlimit = 1024   # MB (for the actual verification)
timelimit = 1800  # s (for the actual verification)
timelimitw = 120  # s (for witness checking) note: SVCOMP uses 90s, but their machines is roughly twice as fast than ours.

class colors:
    BLINK = '\033[5m'
    BLACK = '\033[90m'
    DARKRED = '\033[31m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    HIGHLIGHT = '\033[1m'
    FAINT = '\033[2m'
    UNDERLINE = '\033[4m'
    NO = '\033[0m'

''' Timeout management

 See:
   http://stackoverflow.com/questions/1191374/subprocess-with-timeout
   http://stackoverflow.com/questions/4789837/how-to-terminate-a-python-subprocess-launched-with-shell-true

'''
import shlex, signal, subprocess, threading, resource, multiprocessing
from threading import Thread, Lock
from multiprocessing import Pool
import Queue

import core.utils


lock = threading.Lock()   # for mutual exclusion on log entries

# default
witness = False
cpus = CPUS_WITNESS_NO
quick = False


class Command(object):
    status = None
    output = stderr = ''

    def __init__(self, cmdline):
        self.cmd = cmdline
        self.process = None

    def run(self, timeout=None):
        def target():
            # Thread started
            self.process = subprocess.Popen(self.cmd, shell=True, preexec_fn=os.setsid, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.output, self.stderr = self.process.communicate()
            # Thread finished

        thread = threading.Thread(target=target)

        try:
            thread.start()
            thread.join(timeout)

            if thread.is_alive():
                # Terminating process
                ###
                os.killpg(self.process.pid,signal.SIGTERM)
                os.killpg(self.process.pid,signal.SIGKILL)
                self.process.kill()
                self.process.terminate()
                thread.join()
        except KeyboardInterrupt:
            os.killpg(self.process.pid,signal.SIGTERM)
            os.killpg(self.process.pid,signal.SIGKILL)
            self.process.kill()
            self.process.terminate()

        memsize = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        return self.output, self.stderr, self.process.returncode, memsize


def indent(s,char='|'):
    t = ''
    for l in s.splitlines(): t += '   %s%s'%(char,l)+'\n'
    return t

import logging


''' Checks whether in the .yml file the test case is marked as safe or unsafe
'''
def falseortrue(filename):
    with open(filename, 'r') as f:
        lines = f.read().splitlines()
        last_line = lines[-1]
        return True if  "expected_verdict: true" in last_line else False

'''
def feed(k,file):
    cmdline = './lazy-cseq.py -i ' +file
    command = Command(cmdline)
    out, err, code, mem = command.run(timeout=int(timelimit))   # store stdout, stderr, process' return value

    check = ''

    if 'FALSE, ' in out and 'false-unreach-call' in file: check = 'PASS'
    elif 'TRUE, ' in out and 'true-unreach-call' in file: check = 'PASS'
    else: check = 'FAIL'

    print cmdline
    print indent(out),
    print "%s,   " %(str(k)) +check + ', '+ out.splitlines()[-1] + '\n'
'''
def feed2(file):
    k=file[:file.find(' ')]
    file = file[file.find(' '):]
    file = file.lstrip()
    needtocheckwitness = None
    witnesscheckstatus = ''

    # verify
    #
    cmdline = 'ulimit -Sv %s && timeout %s ./lazy-cseq.py --input %s --witness %s.xml' %(memlimit*1024,timelimit,file,file)
    cmdline += ' --quick' if quick else ''
    command = Command(cmdline)
    out, err, code, mem = command.run()   # store stdout, stderr, process' return value

    check = ''

    if 'FALSE, ' in out and not falseortrue(file.replace('.i','.yml')):   ##'false-unreach-call' in file:
        if witness: needtocheckwitness = True
        check = 'PASS'
    elif 'TRUE, ' in out  and falseortrue(file.replace('.i','.yml')): ###and 'true-unreach-call' in file:
        if witness: needtocheckwitness = False
        check = 'PASS'
    else: check = 'FAIL'

    log = ''
    log += cmdline+'\n'
    log += indent(out)

    # validate witness if any
    #
    cpacheckerpath = '../CPAchecker-1.8-unix'
    inputfilepath = file ###'concurrency_2019/pthread/fib_bench_false-unreach-call.i'
    witnesspath = inputfilepath +'.xml'
    witnesscheckstatus = 'witness-ok-skip'

    if needtocheckwitness and witness ==  True:
    #if needtocheckwitness:
        #params = "-witnessValidation -setprop witness.checkProgramHash=false -heap 5000m -benchmark -setprop cpa.predicate.memoryAllocationsAlwaysSucceed=true -setprop cpa.smg.memoryAllocationFunctions=malloc,__kmalloc,kmalloc,kzalloc,kzalloc_node,ldv_zalloc,ldv_malloc -setprop cpa.smg.arrayAllocationFunctions=calloc,kmalloc_array,kcalloc -setprop cpa.smg.zeroingMemoryAllocation=calloc,kzalloc,kcalloc,kzalloc_node,ldv_zalloc -setprop cpa.smg.deallocationFunctions=free,kfree,kfree_const"
        params = "-witnessValidation -setprop witness.checkProgramHash=false -heap 5000m -benchmark -setprop cpa.predicate.memoryAllocationsAlwaysSucceed=true -setprop cpa.smg.memoryAllocationFunctions=malloc,__kmalloc,kmalloc,kzalloc,kzalloc_node,ldv_zalloc,ldv_malloc -setprop cpa.smg.arrayAllocationFunctions=calloc,kmalloc_array,kcalloc -setprop cpa.smg.zeroingMemoryAllocation=calloc,kzalloc,kcalloc,kzalloc_node,ldv_zalloc -setprop cpa.smg.deallocationFunctions=free,kfree,kfree_const -timelimit %ss -stats " % timelimitw
        cmdline2 = '%s/scripts/cpa.sh %s -witness %s -spec %s/PropertyUnreachCall.prp %s' % (cpacheckerpath,params,witnesspath,cpacheckerpath,inputfilepath)
        #print "----> cmdline <%s> " % cmdline2
        log += indent(cmdline2)

        command2 = Command(cmdline2)
        out2, err2, code2, mem2 = command2.run()   # store stdout, stderr, process' return value

        #witnesscheckstatus = 'witness-ok' if 'Verification result: FALSE.' in out2 else 'witness-ko'
        if 'Verification result: FALSE.' in out2: witnesscheckstatus = 'witness-ok-confirmed'
        elif 'Shutdown requested' in out2: witnesscheckstatus = 'witness-ko-timeout'
        elif 'Cannot parse witness: ' in out2: witnesscheckstatus = 'witness-ko-invalid'
        elif 'Error: Parsing failed' in out2: witnesscheckstatus = 'witness-ko-parsing'
        elif 'Verification result: TRUE. ' in out2: witnesscheckstatus = 'witness-ko-incorrect'
        elif 'Verification result: UNKNOWN' in out2: witnesscheckstatus = 'witness-ko-unknown'
        else: witnesscheckstatus = 'witness-ko-boh'

        check = 'FAIL' if witnesscheckstatus.startswith('witness-ko') else check

        log += indent(err2)
        log += indent(out2)
        core.utils.saveFile(inputfilepath+'.xml.log',err2+out2)

    # close log entry
    if len(out)>0:
        out = out.splitlines()[-1] 
    else:
        out = out + '0.00,0.00, 0.00,0.00, 0.00,0.00, 0.00,0.00, 0.00,0.00,  KILL, %s' % file


    log += "stop, %s, " %(str(k)) +check + ', '+ out + ', '+witnesscheckstatus+'\n'
    #log += "stop, %s,   " %(str(k)) +check + ', '+ out.splitlines()[-1] + '\n'

    return log


def listfiles(path='./'):
    return [y for x in os.walk(path) for y in glob(os.path.join(x[0], '*.i'))]


def usage(cmd, errormsg):
    print "SV-COMP2020 simulator for CSeq-Lazy wrapper script"
    print ""
    print " Usage:"
    print "   -h, --help                    display this help screen"
    print ""
    print "   -i<path>, --input=<path>      path to a single .i file"
    print "   -p<path>, --path=<path>       path to recursively scan for .i files"
    print "   -q, --quick                   call lazycseq.py --quick"
    print "   -w, --witness-check           enable violation witness checking"
    print "\n"
    print "  Notes:"
    print "       (1) for quickly checking that something did not break the tool: use --quick"
    print "       (2) for a full round with real bounds: use no extra parameters"
    print "       (3) for a full round with real bounds and witness checking: use --witness-check"
    print ""
    #print '\n' + errormsg + '\n'
    sys.exit(1)


def main(args):    
    # Command-line params
    #
    cmd = args[0]

    try:
        opts, args = getopt.getopt(sys.argv[1:], "hi:p:w", ["help", "input=", "path=", "quick", "witness-check"])
    except getopt.GetoptError, err:
        print "error"
        usage(cmd, 'error: ' +str(err))

    inputfile = inputpath = ''

    global quick
    global cpus
    global witness

    for o, a in opts:
        if o in ("-h", "--help"): usage(cmd, "")
        elif o in ("-i", "--input"): inputfile = a
        elif o in ("-p", "--path"): inputpath = a
        elif o in ("-q", "--quick"):
            quick = True
            cpus = CPUS_WITNESS_NO_QUICK
        elif o in ("-w", "--witness-check"):
            witness = True
            cpus = CPUS_WITNESS
        else: assert False, "unhandled option"

    if inputfile == inputpath == '':
        print 'error: source file or path not specified'
        sys.exit(1)


    sortedfiles = None

    #
    #
    if inputfile != '':
        sortedfiles = []
        sortedfiles.append(inputfile)
    elif inputpath != '':
        # Spawn parallel processes . .   .
        #
        sortedfiles = sorted(listfiles(inputpath))


    # Invoke Lazy-CSeq wrapper
    #
    for i,f in enumerate(sortedfiles):
        sortedfiles[i] = str(i+1)+' '+f

    pool = Pool(processes=cpus,maxtasksperchild=1)


    k=0
    try:
        for i in pool.imap(feed2,sortedfiles):
            k+=1
            with lock: print(indent(i,str(k).zfill(4) + '> '))
    except (KeyboardInterrupt, SystemExit):
        print("interrupted")
        sys.exit(0)

if __name__ == "__main__":
    try:
        resource.setrlimit(resource.RLIMIT_STACK, (resource.RLIM_INFINITY, resource.RLIM_INFINITY))
        resource.setrlimit(resource.RLIMIT_AS, (resource.RLIM_INFINITY, resource.RLIM_INFINITY))
    except:
        print ("Warning: unable to set resource limits, current limits:")
        print ("   RLIMIT_DATA: soft:%s hard:%s"  % resource.getrlimit(resource.RLIMIT_DATA)  )
        print ("   RLIMIT_STACK: soft:%s hard:%s"  % resource.getrlimit(resource.RLIMIT_STACK)  )
        print ("   RLIMIT_RSS: soft:%s hard:%s"  % resource.getrlimit(resource.RLIMIT_RSS)  )
        print ("   RLIMIT_MEMLOCK: soft:%s hard:%s"  % resource.getrlimit(resource.RLIMIT_MEMLOCK)  )
        print ("   RLIMIT_AS: soft:%s hard:%s"  % resource.getrlimit(resource.RLIMIT_AS)  )

    main(sys.argv[0:])


'''
i = Queue.Queue()   # filenames
o = Queue.Queue()   # outputs
lock = threading.RLock()

def worker():
    while True:
        item = i.get()

        with lock:
            print item

        o.put("ciao "+str(item))
        i.task_done()

def main():
    sortedfiles = sorted(listfiles(sys.argv[1]))

    for j,f in enumerate(sortedfiles):
        sortedfiles[j] = str(j+1)+' '+f

    for f in sortedfiles:
        i.put(f)

    for j in range(CPUS):
         t = Thread(target=worker)
         t.daemon = True
         t.start()

    i.join()       # block until all tasks are done

    print "finished!"
'''

