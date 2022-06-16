#!/usr/bin/env python
'''
	SV-COMP 2020 parallel experiment simulation
		 for
	CSeq 1.9 wrapper script for Lazy Configuration

	2020.04.05  changed detection of unsafe/safe instances in the .yml desc
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

CPUS = 14         # by default, do not use all the CPUs to avoid performance fluctuations

memlimit = 1024   # MB (for the actual verification)
timelimit = 1800  # s (for the actual verification)
timelimitw = 120  # s (for witness checking) note: SVCOMP uses 90s, but their machines is roughly twice as fast than ours.

''' Timeout management

 See:
   http://stackoverflow.com/questions/1191374/subprocess-with-timeout
   http://stackoverflow.com/questions/4789837/how-to-terminate-a-python-subprocess-launched-with-shell-true

'''
import shlex, signal, subprocess, threading, resource, multiprocessing
from threading import Thread, Lock
from multiprocessing import Pool
import Queue


lock = threading.Lock()   # for mutual exclusion on log entries

# default
witness = False
cpus = CPUS
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
	try:
		with open(filename, 'r') as f:
			lines = f.read().splitlines()

			for l in lines:
				if  "false-unreach-call" in l: return False  # may have multiple properties

			return True
	except:
		return True


def lines(filename):
	with open(filename, 'r') as f:
		lines = f.read().splitlines()
		return len(lines)


'''
'''
def feed2(file):
	k=file[:file.find(' ')]
	file = file[file.find(' '):]
	file = file.lstrip()
	witnesscheckstatus = ''

	# verify
	#
	cmdline = 'ulimit -Sv %s && timeout %s ./lazy-cseq.py --input %s --witness %s.xml' %(memlimit*1024,timelimit,file,file)
	cmdline += ' --quick' if quick else ''
	command = Command(cmdline)
	out, err, code, mem = command.run()   # store stdout, stderr, process' return value

	check = ''

	if 'FALSE, ' in out and not falseortrue(file.replace('.i','.yml')):   ##'false-unreach-call' in file:
		check = 'PASS'
	elif 'TRUE, ' in out  and falseortrue(file.replace('.i','.yml')): ###and 'true-unreach-call' in file:
		check = 'PASS'
	else: check = 'FAIL'

	log = ''
	log += cmdline+'\n'
	log += indent(out)

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
	cmd = args[0]

	try:
		opts, args = getopt.getopt(sys.argv[1:], "hi:p:w", ["help", "input=", "path="])
	except getopt.GetoptError, err:
		print "error"
		usage(cmd, 'error: ' +str(err))

	inputfile = inputpath = ''

	for o, a in opts:
		if o in ("-h", "--help"): usage(cmd, "")
		elif o in ("-i", "--input"): inputfile = a
		elif o in ("-p", "--path"): inputpath = a
		else: assert False, "unhandled option"

	if inputfile == inputpath == '':
		print 'error: source file or path not specified'
		sys.exit(1)

	#
	sortedfiles = None

	if inputfile != '':
		sortedfiles = []
		sortedfiles.append(inputfile)
	elif inputpath != '':
		sortedfiles = sorted(listfiles(inputpath))

	# Invoke Lazy-CSeq wrapper
	for i,f in enumerate(sortedfiles):
		boh = falseortrue(sortedfiles[i].replace('.i','.yml'))
		print("%s, %s, %s" % (sortedfiles[i],boh, lines(sortedfiles[i])))


if __name__ == "__main__":
	main(sys.argv[0:])


