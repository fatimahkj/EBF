#!/usr/bin/env python3
'''
	SV-COMP 2022 parallel experiment simulation
		 for
	CSeq 3.0 wrapper script for Lazy Configuration

	2021.11.06  support for data race check
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


CPUS_WITNESS_NO_QUICK = 16   # in quick mode use all cores
CPUS_WITNESS_NO = 8         # by default, do not use all the CPUs to avoid performance fluctuations
CPUS_WITNESS = 6            # when validating witnesses, leave some cores for the witness checker as it spawns its own threads

memlimit = 1024*16   # MB (for the actual verification)
timelimit = 1200     # s (for the actual verification)
timelimitw = 120     # s (for witness checking) note: SVCOMP uses 90s, but their machines is roughly twice as fast than ours.


''' Timeout management

 See:
   http://stackoverflow.com/questions/1191374/subprocess-with-timeout
   http://stackoverflow.com/questions/4789837/how-to-terminate-a-python-subprocess-launched-with-shell-true

'''
import shlex, signal, subprocess, threading, resource, multiprocessing
from threading import Thread, Lock
from multiprocessing import Pool
import queue

import core.utils


lock = threading.Lock()   # for mutual exclusion on log entries

# default
witness = False
cpus = CPUS_WITNESS_NO
quick = False
checkraces = False
checkreach = False


class Command(object):
	output = stderr = ''

	def __init__(self, cmdline):
		self.cmd = cmdline
		self.process = None

	def run(self,timeout=None):
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


''' Check whether in the .yml file the test case is marked as safe or unsafe
'''
def reachornot(filename):
	with open(filename,'r') as f:
		lines = f.read().splitlines()

		for (no,l) in enumerate(lines):
			if "property_file: ../properties/unreach-call.prp" in l:
				if "expected_verdict: false" in lines[no+1]:
					return False
				if "expected_verdict: true" in lines[no+1]:
					return True

				assert(0)


''' Check whether in the .yml file the test case is marked as safe or unsafe
'''
def racesornot(filename):
	with open(filename,'r') as f:
		lines = f.read().splitlines()

		for (no,l) in enumerate(lines):
			if "property_file: ../properties/no-data-race.prp" in l:
				if "expected_verdict: false" in lines[no+1]:
					return False
				if "expected_verdict: true" in lines[no+1]:
					return True

				assert(0)


'''
Check whether in the .yml file there is a reachability property to check.
'''
def wantreach(ymlfile):
	with open(ymlfile,'r') as f:
		return "unreach-call.prp" in f.read()

'''
Check whether in the .yml file there is a no-data-race property to check.
'''
def wantraces(ymlfile):
	with open(ymlfile,'r') as f:
		return "no-data-race.prp" in f.read()


def getfilename(ymlfile):
	with open(ymlfile, 'r') as yml:
		lines = yml.read().splitlines()
		for (no, l) in enumerate(lines):
			if 'input_files: ' in l:
				fname = l.split(':')[-1].strip()
				if fname[0] == '\'':
					fname = fname[1:-1]

				fpath = os.path.join(os.path.dirname(ymlfile), fname)
				assert os.path.exists(fpath), "Cannot open %s" % fpath

				return fpath  # TODO: Check if there are examples with multiple input files
	raise Exception('Could not find filename in yml file.')


def feed2(file):
	k = file[:file.find(' ')]
	#k = k.encode()
	file = file[file.find(' '):]
	file = file.lstrip()
	needtocheckwitness = None
	witnesscheckstatus = ''

	# verify
	#
	#cmdline = 'timeout %s ./lazy-cseq.py --input %s --witness %s.xml' %(timelimit,file,file)
	#cmdline = 'ulimit -Sv %s && timeout %s ./lazy-cseq.py --input %s --witness %s.xml' %(memlimit*1024,timelimit,file,file)
	cmdline = 'ulimit -m %s ; timeout %s ./lazy-cseq.py --input %s --witness %s.xml' %(memlimit*1024,timelimit,file,file)
	cmdline += ' --quick' if quick else ''
	cmdline += ' --spec=no-data-race.prp' if checkraces else ''
	command = Command(cmdline)
	out, err, code, mem = command.run()   # store stdout, stderr, process' return value
	out = out.decode()

	check = ''
	end = file[-2:]  # .i or .c

	if checkreach:
		if 'FALSE, ' in out and not reachornot(file.replace(end,'.yml')):   ##'false-unreach-call' in file:
			if witness: needtocheckwitness = True
			check = 'PASS'
		elif 'TRUE, ' in out and reachornot(file.replace(end,'.yml')): ###and 'true-unreach-call' in file:
			if witness: needtocheckwitness = False
			check = 'PASS'
		else: check = 'FAIL'
	elif checkraces:
		if 'FALSE, ' in out and not racesornot(file.replace(end,'.yml')):
			if witness: needtocheckwitness = True
			check = 'PASS'
		elif 'TRUE, ' in out and racesornot(file.replace(end,'.yml')):
			if witness: needtocheckwitness = False
			check = 'PASS'
		else: check = 'FAIL'

	log = ''
	log += cmdline+'\n'
	log += indent(out)

	# validate witness if any
	#
	cpacheckerpath = '../CPAchecker-1.9-unix'
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
		out2 = out2.decode()
		err2 = err2.decode()

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
		#print("======= %s %s ======== %s %s ======= %s "  % (type(out),type(err),type(out2),type(err2),type(inputfilepath)))
		core.utils.saveFile(inputfilepath+'.xml.log',err2+out2,binary=False)

	# close log entry
	if len(out)>0:
		out = out.splitlines()[-1]
	else:
		times = 1 if quick else 3
		zeroes = '0.00,0.00, '*times
		out = out + '%s KILL, %s' % (zeroes, file)

	log += "stop, %s, " % k +check + ', '+ out + ', '+witnesscheckstatus+'\n'

	return log


def listfiles(path='./'):
	return [y for x in os.walk(path) for y in glob(os.path.join(x[0], '*.yml'))]


def usage(cmd, errormsg):
	print("SV-COMP2022 simulator for CSeq-Lazy wrapper script")
	print("")
	print(" Usage:")
	print("   -h, --help                    display this help screen")
	print("")
	print("   -i<path>, --input=<path>      path to a single .i file")
	print("   -p<path>, --path=<path>       path to recursively scan for .i files")
	print("   -q, --quick                   call lazycseq.py --quick")
	print("       --reach                   reachability check only (default)")
	print("       --races                   data race check only")
	print("       --unsafe-only             only consider unsafe instances")
	print("       --safe-only               only consider safe instances")
	print("       --list                    just list the files")
	print("\n")
	print("  Notes:")
	print("       (1) for quickly checking that something did not break the tool: use --quick")
	print("       (2) for a full round with real bounds: use no extra parameters")
	print("       (3) for a full round with real bounds and witness checking: use --witness-check")
	print("")
	#print '\n' + errormsg + '\n'
	sys.exit(1)


def main(args):
	# Command-line params
	#
	cmd = args[0]

	try:
		opts, args = getopt.getopt(sys.argv[1:], "hi:p:w", ["help", "input=", "path=", "quick", "witness-check", "races", "reach", "list", "unsafe-only", "safe-only"])
	except getopt.GetoptError as err:
		print("error")
		usage(cmd, 'error: ' +str(err))

	global quick
	global cpus
	global witness
	global checkreach
	global checkraces

	inputfile = inputpath = ''
	checkreach = checkraces = listonly = unsafeonly = safeonly = False


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
		elif o in ("--races"): checkraces = True
		elif o in ("--reach"): checkreach = True
		elif o in ("--unsafe-only"): unsafeonly = True
		elif o in ("--safe-only"): safeonly = True
		elif o in ("--list"): listonly = True
		else: assert False, "unhandled option"

	if checkraces and checkreach:
		print('error: both --races and --reach not allowed')
		sys.exit(1)

	if inputfile == inputpath == '':
		print('error: source file or path not specified')
		sys.exit(1)

	if not checkraces and not checkreach: checkreach = True

	# Prepare the list of files to analyse.
	#
	sortedfiles = filteredlist = ymllist = []

	# Test a specific file or all files at the given path.
	if inputfile != '': ymllist = [inputfile]
	elif inputpath != '': ymllist = sorted(listfiles(inputpath))

	for i,f in enumerate(ymllist):
		ic = getfilename(f)   # get .i or .c filename from .yml specfile

		if checkreach and wantreach(f):
			s = str(reachornot(f)).lower()
			if unsafeonly and reachornot(f): print ("skipping %s [%s] (not unsafe)" % (s,ic))
			elif safeonly and not reachornot(f):  print ("skipping %s [%s] (not safe)" % (s,ic))
			else:
				print ("adding %s [%s]" % (s,ic))
				filteredlist.append(ic)
		elif checkraces and wantraces(f):
			s = str(racesornot(f)).lower()
			if unsafeonly and racesornot(f): print ("skipping %s [%s] (not unsafe)" % (s,ic))
			elif safeonly and not racesornot(f):  print ("skipping %s [%s] (not safe)" % (s,ic))
			else:
				print ("adding %s [%s]" % (s,ic))
				filteredlist.append(ic)
		else:
			print ("skipping [%s] (different category)" % f)

	sortedfiles = sorted(filteredlist)

	if listonly: sys.exit(0)

	# Invoke Lazy-CSeq wrapper
	#
	for i,f in enumerate(sortedfiles):
		sortedfiles[i] = (str(i+1)+' '+f)

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
	'''
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
	'''

	main(sys.argv[0:])


