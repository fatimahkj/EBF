#!/usr/bin/env python3
'''
	CSeq 3.0 wrapper script for Lazy Configuration, SV-COMP 2022

Previous versions:
CSeq 2.1 wrapper script for Lazy Configuration, SV-COMP 2021
CSeq 1.9 wrapper script for Lazy Configuration, SV-COMP 2020
CSeq 1.6 wrapper script for Lazy Configuration, SV-COMP 2019
Lazy-CSeq 1.1 SV-COMP 2017 wrapper script
Lazy-CSeq 1.1 SV-COMP 2016 wrapper script
October 2015  SV-COMP 2016 VERSION
July 2015  adapted to CSeq-1.0 new command-line format
October 2014  SV-COMP 2015 VERSION
November 2013  original version
'''
VERSION = "CSeq 3.0 -l lazy SV-COMP 2022"

import resource
import time
import subprocess
import shlex
import os.path
import getopt
import sys
import re
import core.utils


# 2022 Reachability
svcompparams = []
###svcompparams.append('--time 1 --show-backend-output --threads 100 -l lazy --sv-comp --backend cbmc --32 --atomic-parameters --deep-propagation --cex --rounds=2 --nondet-condvar-wakeups --unwind-while=2 --unwind-for=2')
svcompparams.append('--show-backend-output --threads 100 -l lazy --sv-comp --backend cbmc --32 --atomic-parameters --deep-propagation --cex --rounds=2 --nondet-condvar-wakeups --unwind-while=2 --unwind-for=2')
svcompparams.append('--show-backend-output --threads 100 -l lazy --sv-comp --backend cbmc --32 --atomic-parameters --deep-propagation --cex --rounds=4 --nondet-condvar-wakeups --unwind-while=3 --unwind-for=5')
svcompparams.append('--show-backend-output --threads 100 -l lazy --sv-comp --backend cbmc --32 --atomic-parameters --deep-propagation --cex --rounds=20 --nondet-condvar-wakeups --unwind-while=1 --unwind-for=20 --softunwindbound --unwind-for-max=10000')

# 2022 Data Race
svcompparamsd = []
###svcompparamsd.append('--time 1 --show-backend-output --threads 100 -l lazy --sv-comp --backend cbmc --32 --atomic-parameters --deep-propagation --cex --rounds=2 --nondet-condvar-wakeups --unwind-while=2 --unwind-for=2')
svcompparamsd.append('--show-backend-output --threads 100 -l lazy --sv-comp --backend cbmc --32 --atomic-parameters --deep-propagation --nondet-condvar-wakeups --data-race-check --contexts 4 --unwind 2')
svcompparamsd.append('--show-backend-output --threads 100 -l lazy --sv-comp --backend cbmc --32 --atomic-parameters --deep-propagation --nondet-condvar-wakeups --data-race-check --contexts 9 --unwind 3')
# svcompparamsd.append('--show-backend-output --threads 100 -l lazy --sv-comp --backend cbmc --32 --atomic-parameters --deep-propagation --nondet-condvar-wakeups --data-race-check --contexts 100 --unwind-while=1 --unwind-for=20 --softunwindbound --unwind-for-max=10000')


def usage(cmd,errormsg=''):
	print(VERSION)
	print("")
	print("Warning:  This is a wrapper script for the software verification competition.")
	print("          For any other purpose, please use CSeq's main command-line front end (cseq.py) instead.")
	print("         (also see README file).")
	print("")
	print(" Usage:")
	print("   -h, --help                            display this help screen")
	print("")
	print("   -i<filename>, --input=<filename>      read input from the filename")
	print("   -s<specfile>, --spec=<specfile>       SV-COMP specfile (default:ALL.prp)")
	print("   -w<logfile>, --witness=<logfile>      counterexample output file (default:a.log)")
	print("   -q, --quick                           only run the first step with timeout 2 seconds")
	print("   -V, --version                         print version")
	print("")
	if errormsg!='': print(errormsg+'\n')
	sys.exit(1)


def indent(s):
	t = ''
	for l in s.splitlines(): t += '   |'+l+'\n'
	return t


def main(args):
	quick = False

	realstarttime = time.time()
	cmd = args[0]

	try:
		opts, args = getopt.getopt(sys.argv[1:], "hi:s:w:qV", ["help", "input=", "spec=", "witness=", "quick", "version"])
	except getopt.GetoptError as err:
		print("error")
		usage(cmd, 'error: ' +str(err))

	inputfile = spec = witness = ''

	for o, a in opts:
		if o == "-v": verbose = True
		elif o in ("-h", "--help"): usage(cmd, "")
		elif o in ("-w", "--witness"): witness = a
		elif o in ("-s", "--spec"): spec = a
		elif o in ("-i", "--input"): inputfile = a
		elif o in ("-q", "--quick"):
			quick = True
			global svcompparams
			svcompparams[0] = re.sub(' --time=[0-9]+ ', ' --time=2 ', svcompparams[0])
			svcompparams = svcompparams[:1]
			print(svcompparams)
		elif o in ("-V", "--version"):
			print(VERSION)
			sys.exit(0)
		else: assert False, "unhandled option"

	# Check parameters
	if inputfile == '':
		usage(cmd,"error: input file name not specified")
		sys.exit(1)

	if not os.path.isfile(inputfile):
		print('error: unable to open input file (%s)' % inputfile)
		sys.exit(1)

	if witness == '': witness = inputfile + '.log'
	if spec == '': spec = 'ALL.prp'

	#if not os.path.isfile(spec):
	#	print('error: unable to open spec file (%s)' % spec)
	#	sys.exit(1)

	#
	print(VERSION)
	print("")
	print("Warning:  This is a wrapper script for the software verification competition.")
	print("          For any other purpose, please use CSeq's main command-line frontend (cseq.py) instead.")
	print("         (also see README file).")
	print("\n")

	last = lazyout = ''
	maxmem = 0

	#try:
	#	resource.setrlimit(resource.RLIMIT_STACK, (resource.RLIM_INFINITY, resource.RLIM_INFINITY))
	#	resource.setrlimit(resource.RLIMIT_AS, (resource.RLIM_INFINITY, resource.RLIM_INFINITY))
	#except:
	#	print("Warning: unable to set resource limits, current limits:")
	#	print("   RLIMIT_DATA: soft:%s hard:%s"  % resource.getrlimit(resource.RLIMIT_DATA)  )
	#	print("   RLIMIT_STACK: soft:%s hard:%s"  % resource.getrlimit(resource.RLIMIT_STACK)  )
	#	print("   RLIMIT_RSS: soft:%s hard:%s"  % resource.getrlimit(resource.RLIMIT_RSS)  )
	#	print("   RLIMIT_MEMLOCK: soft:%s hard:%s"  % resource.getrlimit(resource.RLIMIT_MEMLOCK)  )
	#	print("   RLIMIT_AS: soft:%s hard:%s"  % resource.getrlimit(resource.RLIMIT_AS)  )


	racecheck = 'no-data-race' in spec
	svcompparams = svcompparamsd if racecheck else svcompparams

	# Analyse the input program as many times as svcompparams[] is long,
	# until a property violation is found, or the tool crashes.
	for i,params in enumerate(svcompparams):
		# Move on to the next input file
		# as soon as a reachable bug is found, or
		# the tool crashes.
		if last in ('UNSAFE','UNKNOWN','BACKENDREJECT'):
			lazyout += '0.00,0.00, '      # this step will be skipped, time is 0
			continue

		if not racecheck:
			cmdline = './cseq.py %s --input %s --witness %s' % (params,inputfile,witness)
		else:
			cmdline = './cseq.py %s --input %s --witness %s --data-race-check' % (params,inputfile,witness)

		indentedout = ''

		try:
			print(cmdline)

			p = subprocess.Popen(shlex.split(cmdline), stdout=subprocess.PIPE)
			out,err = p.communicate()
			out = out.decode()
			print(indent(out))

			# Only get the last line of the output.
			out = out.splitlines()[-1]
			out = out.replace(core.utils.colors.BLINK, '')
			out = out.replace(core.utils.colors.GREEN, '')
			out = out.replace(core.utils.colors.DARKRED, '')
			out = out.replace(core.utils.colors.RED, '')
			out = out.replace(core.utils.colors.BLACK, '')
			out = out.replace(core.utils.colors.NO, '')

			# Extract time and memory used in this step as reported by CSeq (cseq.py).
			lasttime = float(out[out[:out.rfind(', ')].rfind(", ") + 2:out.rfind('s, ')].strip())
			lastmem = out[out.rfind(', ')+2:].replace('MB','')
			lazyout += '%2.2f,%s, ' % (float(lasttime),lastmem)
			maxmem = max(float(lastmem),maxmem)      # memory peak overall steps

			if 'UNSAFE' in out:
				last = 'UNSAFE'
				continue

			if 'BACKENDREJECT' in out:
				last = 'BACKENDREJECT'
				continue

			if 'SAFE' in out:
				last = 'SAFE'
				continue

			last = 'UNKNOWN'
		except: ### subprocess.CalledProcessError, err:
			last = 'UNKNOWN'
			lazyout += '0.00,0.00, '
			continue

	# Change SAFE and UNSAFE into TRUE and FALSE, for SV-COMP
	if last == 'SAFE': last = 'TRUE'
	elif last == 'UNSAFE': last = 'FALSE'
	# If the backend rejects the sequentialised file (last == 'BACKENDREJECT'), or
	# the analysis does not even start (last = 'UNKNOWN'), etc.,
	# the program cannot be analysed.
	else: last = 'UNKNOWN'

	print("%s %s, %s, %2.1f,%2.1f" % (lazyout, last, witness, (time.time()-realstarttime), maxmem))


if __name__ == "__main__":
	main(sys.argv[0:])

