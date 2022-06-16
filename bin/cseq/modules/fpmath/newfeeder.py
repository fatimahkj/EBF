""" CSeq C Sequentialization Framework
	backend feeder module

	written by Omar Inverso.
"""
VERSION = 'feeder-2018.07.20'
#VERSION = 'feeder-2015.07.16'     # CSeq 1.0 Release - ASE2015
# VERSION = 'feeder-2015.07.03'   # now as a CSeq module
# VERSION = 'feeder-2015.07.02'   # removed intermediate stripping
# VERSION = 'feeder-2014.09.25'   # removed the 3rd party timeout tool (due to portability issues, especially not working well on OSX despite the latest fixes available around)
							  	  # new timeout mechanism embedded in CSeq implemented from scratch using python multithread+subprocess management
# VERSION = 'feeder-2014.09.21'   # minor front-end adjustments
# VERSION = 'feeder-2014.06.03'   # front-end adjustments: default output is now more compact, for old-style output use -v
#VERSION = 'feeder-2014.03.10'
"""

Prerequisites:
	Input correctly instrumented for the specified backend.

TODO:
	- when the backend is not available, there should be an exception.

Changelog:
	2020.05.27  adapted from [ICCPS2017]
	2018.07.20  experimental support for Sage and constraint-based encodings
	2015.10.20  fix for backend and witness file
	2015.07.19  fix for backend llbmc and klee (Truc)
	2015.07.03  1st version, codebase inherited from cseq-feeder.py (feeder-2015.07.02)
"""

import os, sys, getopt, time, signal, subprocess, shlex
from threading import Timer
import pycparser.c_parser, pycparser.c_ast, pycparser.c_generator
import core.module, core.parser, core.utils
from core.module import ModuleError

'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

				  Options and Parameters below.

'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
# Name of the executable file to run, by backend.
backendFilename = {}
backendFilename['esbmc'] = 'esbmc'
backendFilename['cbmc'] = 'backends/cbmc-5.4'
#backendFilename['cbmc'] = 'backends/cbmc-5.12'
backendFilename['llbmc'] = 'llbmc'
backendFilename['blitz'] = 'blitz'
backendFilename['satabs'] = 'satabs'
backendFilename['sage'] = '/Applications/SageMath-8.0.app/sage'
# backendFilename['2ls'] = 'summarizer'
# backendFilename['smack'] = 'smack-verify.py'
backendFilename['klee'] = 'klee'
backendFilename['cpachecker'] = 'cpa.sh'
# backendFilename['spin'] = 'spin'

# Command-line parameters, by backend.
cmdLineOptions = {}
cmdLineOptions['esbmc'] = ' --no-slice --no-bounds-check --no-div-by-zero-check --no-pointer-check --unwind 1 --no-unwinding-assertions '
#cmdLineOptions['cbmc'] = '  --stop-on-fail --trace'  ###cmdLineOptions['cbmc'] = ' --bounds-check '
cmdLineOptions['cbmc'] = ' --32 '  ###cmdLineOptions['cbmc'] = ' --bounds-check '
###cmdLineOptions['cbmc'] = '  --unwind 1 --no-unwinding-assertions '
cmdLineOptions['llbmc'] = ' -no-max-function-call-depth-checks -no-memory-free-checks -no-shift-checks -no-memcpy-disjoint-checks -no-memory-access-checks -no-memory-allocation-checks --max-loop-iterations=1 --no-max-loop-iterations-checks --ignore-missing-function-bodies -no-overflow-checks -no-div-by-zero-checks'
cmdLineOptions['blitz'] = '  --terminate-on-firstbug '
cmdLineOptions['satabs'] = ' '
cmdLineOptions['sage'] = ' '
# cmdLineOptions['2ls'] = ' '
# cmdLineOptions['smack'] = ' --unroll 1 '
cmdLineOptions['klee'] = ' -exit-on-error '
cmdLineOptions['cpachecker'] = ' -preprocess -heap 15000M -timelimit 86400 -noout -predicateAnalysis '

# Command-line parameters, by backend - when no sequentialisation is performed.
cmdLineOptionsNOSEQ = {}
cmdLineOptionsNOSEQ['esbmc'] = ' --no-slice --no-bounds-check --no-div-by-zero-check --no-pointer-check '
cmdLineOptionsNOSEQ['cbmc'] = '  '
cmdLineOptionsNOSEQ['llbmc'] = ' -no-max-function-call-depth-checks -no-memory-free-checks -no-shift-checks -no-memcpy-disjoint-checks -no-memory-access-checks -no-memory-allocation-checks --ignore-missing-function-bodies -no-overflow-checks -no-div-by-zero-checks '
# cmdLineOptionsNOSEQ['blitz'] = '  --terminate-on-firstbug '   # No support concurrency
cmdLineOptionsNOSEQ['satabs'] = ' '
# cmdLineOptionsNOSEQ['2ls'] = ' '     # no concurrency support
# cmdLineOptionsNOSEQ['smack'] = ' '
cmdLineOptionsNOSEQ['klee'] = ' '
# cmdLineOptionsNOSEQ['cpachecker'] = ' -preprocess -heap 15000M -timelimit 86400 -noout -predicateAnalysis '  # No support concurrency


class newfeeder(core.module.BasicModule):
	verbose = False

	def init(self):
		self.inputparam('backend', 'backend (%sblitz%s, cbmc, esbmc, llbmc, cpachecker, satabs, klee)', 'b', 'cbmc', False)
		self.inputparam('backendparams', 'extra backend parameters', 'x', '', True)
		#self.inputparam('show', 'show sequentialized file without analyzing', '', False, True)
		#self.inputparam('save', 'save sequentialized file as _cs_filename.c', '', False, True)
		self.inputparam('time', 'analysis time limit (in seconds)', 't', '3600000', False)
		######self.inputparam('llvm', 'clang or llvm search path (only for llbmc,klee)', 'p', '', True)
		self.inputparam('depth', 'limit search depth', 'd', '0', False)   # depth parameter for the competition
		######self.inputparam('witness', 'output counterexample from backend', 'w', '', True) # parameter for witness
		self.outputparam('exitcode')

	def loadfromstring(self, string, env):
		if self.getinputparam('show') is not None:
			self.output = string
			return

		depth = int(self.getinputparam('depth'))
		timelimit = self.getinputparam('time')
		backend = self.getinputparam('backend')
		backendparams = self.getinputparam('backendparams')
		witness = self.getinputparam('witness')

		#if not os.path.isfile(backendFilename[backend]):
		'''
		if shutil.which(backendFilename[format]) is None:
			raise ModuleError("unable to find the given backend (%s)" % backendFilename[backend])
			sys.exit(2)
		'''
		seqfile = core.utils.rreplace(env.inputfile, '/', '/_cs_', 1) if '/' in env.inputfile else '_cs_' + env.inputfile
		if backend == 'sage': seqfile = seqfile + '.sage'

		logfile = seqfile + '.' + backend + '.log' if witness is None else witness

		core.utils.saveFile(seqfile, string)

		'''
		(filestripped, contents) = core.utils.stripIfNeeded(inputfile)

		if filestripped:
			inputfile = inputfile[:-2] + '.strip.c'
			core.utils.saveFile(inputfile, contents)
		'''

		''' Run the verification tool on the input file '''
		# if self.verbose: print "output: %s" % (seqfile)

		timeBeforeCallingBackend = time.time()    # save wall time

		if backend == 'esbmc':
			cmdline = backendFilename[backend] + cmdLineOptions[backend] + seqfile
			if depth != 0:
				cmdline += ' --depth %s ' % str(depth)
		elif backend == 'cbmc':
			cmdline = backendFilename[backend] + cmdLineOptions[backend] + seqfile
			if depth != 0:
				cmdline += ' --depth %s ' % str(depth)
		elif backend == 'llbmc':
			# llbmc and clang need to be match
			clangpath = '' if self.getinputparam('llvm') is None else  self.getinputparam('llvm')
			clangexe = clangpath +'clang'
			cmdline = "%s -c -g -I. -emit-llvm %s -o %s.bc 2> %s " % (clangexe, seqfile, seqfile[:-2], logfile)
			p = subprocess.Popen(cmdline, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
			out, err = p.communicate()
			core.utils.saveFile('clang_stdout.log', out)
			core.utils.saveFile('clang_stderr.log', err)
			cmdline = backendFilename[backend] + ' ' + cmdLineOptions[backend] + ' ' + seqfile[:-2] + '.bc'
		elif backend == 'blitz':
			cmdline = backendFilename[backend] + cmdLineOptions[backend] + seqfile
			if depth != 0:
				cmdline += ' --depth %s ' % str(depth)
		elif backend == 'satabs':
			cmdline = backendFilename[backend] + cmdLineOptions[backend] + seqfile
		elif backend == 'sage':
			cmdline = backendFilename[backend] + cmdLineOptions[backend] + seqfile
		elif backend == '2ls':
			cmdline = backendFilename[backend] + cmdLineOptions[backend] + seqfile
		elif backend == 'klee':
			# klee needs llvm-gcc version 2.9
			clangpath = '' if self.getinputparam('llvm') is None else  self.getinputparam('llvm')
			clangexe = clangpath + 'llvm-gcc'
			cmdline = "%s -c -g -emit-llvm %s -o %s.bc " % (clangexe, seqfile, seqfile[:-2])
			# print "CLANG: %s" % cmdline
			p = subprocess.Popen(cmdline, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
			out, err = p.communicate()
			core.utils.saveFile('clang_stdout.log', out)
			core.utils.saveFile('clang_stderr.log', err)
			cmdline = backendFilename[backend] + ' ' + cmdLineOptions[backend] + ' ' + seqfile[:-2] + '.bc'
		elif backend == 'cpachecker':
			cmdline = backendFilename[backend] + cmdLineOptions[backend] + seqfile
		elif backend == 'smack':
			cmdline = backendFilename[backend] + cmdLineOptions[backend] + seqfile

		cmdline = cmdline + ' '
		#######print "%s\n\n" % cmdline

		# handling of memory and time restrictions
		#
		# `-t T` - set up CPU+SYS time limit to T seconds
		# `-m M` - set up virtual memory limit to M kilobytes
		'''
		memorylimit = 1000*memorylimit # kBytes --> mBytes
		timespacecheck = 'timeout/timeout'
		if timelimit > 0: timespacecheck += ' -t %s' % (timelimit)
		if memorylimit > 0: timespacecheck += ' -m %s' % (memorylimit)
		'''

		#print "running: " + cmdline
		command = core.utils.Command(cmdline)
		out, err, code, mem = command.run(timeout=int(timelimit))   # store stdout, stderr, process' return value

		self.setoutputparam('exitcode', code)

		if 'warning' in err:
			self.warn('warnings on stderr from the backend')

		if backend not in ('klee', ):
			core.utils.saveFile(logfile, out)   # klee outputs errors to stdout, all other backends to stderr
			self.output = out
		else:
			core.utils.saveFile(logfile, err)
			self.output = err



