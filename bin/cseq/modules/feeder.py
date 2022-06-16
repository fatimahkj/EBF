""" CSeq Program Analysis Framework
    backend feeder module

Author:
    Omar Inverso

Changes:
    2021.10.20  obsolete options removed
	2021.02.02  amended default options for ESBMC
    2020.12.29  using ASCII-encoded strings rather then UTF
    2020.12.21  Python 3
    2020.04.14  terminating group of processes via kill(os.getpgid())
    2020.04.14  prefixing exec to the command line will terminate sub-processes too
    2020.04.14  merging stdout with stderr in backend's answer
    2020.04.09  improved support for CPAchecker and ESBMC
    2020.04.09  backend version check
    2020.04.09  termination of any pending sub-processes on any exception
    2020.04.08  no longer using pipes (they deadlock if text too long)
    2020.03.31 (CSeq 2.0)
    2020.03.23 [SV-COMP 2020] + [PPoPP 2020]
    2020.03.23  parallel analysis (merged from feeder_parallel, PPoPP2020 artefact)
    2019.11.16 (CSeq 1.9) [SV-COMP 2020]
    2019.11.16  use suffix .c to save the input file for the backend (even if the original filename was .i)
    2018.11.08 [SV-COMP 2019]
    2018.11.08  no witness parameter any longer, no log file (i.e. output from the backend) saved either
    2018.11.05  check whether it is possible to access the backend
    2018.10.20  add option (no-simplify) to disable propositional simplification (cbmc-only)
    2016.10.07  add option to set backend path manually
    2016.08.19  add option to set output sequentialized file
    2016.08.12  add option to show memory usage
    2016.08.09 (CSeq 1.3) unfinished journal
    2016.08.09  add backend framac
    2015.10.20  fix for backend and witness file
    2015.07.19  fix for backend llbmc and klee (Truc)
    2015.07.16 (CSeq 1.0 Release) [ASE 2015]
    2015.07.03  now as a CSeq module
    2015.07.03  1st version, codebase inherited from cseq-feeder.py (feeder-2015.07.02)
    2015.07.02  removed intermediate stripping
    2014.09.25  removed the 3rd party timeout tool (due to portability issues, especially on OSX)
    2014.09.25  new built-in timeout mechanism (python multithread+subprocess)
    2014.09.21  minor front-end adjustments
    2014.06.03  front-end adjustments: default output is now more compact, for old-style output use -v
    2014.03.10  first version

To do:
  - bufsize should be an external parameter (and show a warning when size is insufficient, or save to file)
  - very urgent: check os.killpg(os.getpgid(c), signal.SIGTERM) works well with parallel analysis
  - termination of any pending sub-processes (e.g., Java or Z3 with Ultimate backend)
   (may need to use execution groups etc.)
  - suppose one sub-process finds a bug even before all the others are spawned
   (for example, -i lazy_unsafe.c --contexts 16 --cores 128). what happens?
  - add input parameter for extra backend arguments to be appended to the command line
  - when the backend is not available, there should be an exception.

Notes:
  - keep bufsize reasonably slow to prevent unnecessary runtime overhead
   (allocation seems really slow)

"""
import ctypes, os, sys, getopt, time, signal, subprocess, shlex, multiprocessing, traceback, resource
import pycparserext.ext_c_parser, pycparser.c_ast, pycparserext.ext_c_generator
import core.module, core.parser, core.utils


'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

				  Options and Parameters below.

'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
# Name of the executable file to run, by backend.
command = {}
command['esbmc'] = 'backends/esbmc-6.6'
command['cbmc'] = 'backends/cbmc-5.4'
command['cbmc-ext'] = 'backends/cbmc-ext'
command['cbmc-svcomp2020'] = 'backends/cbmc-5.12'
command['llbmc'] = 'llbmc'
command['blitz'] = 'blitz'
command['satabs'] = 'satabs'
command['2ls'] = 'summarizer'
#command['smack'] = 'smack-verify.py'
command['smack'] = "backends/smack-2.4.0/bin/smack"
command['klee'] = 'klee'
command['cpachecker'] = 'backends/CPAchecker-1.9-unix/scripts/cpa.sh' ####command['cpachecker'] = 'backends/CPAchecker-1.9-unix/scripts/cpa--single-core.sh'
command['spin'] = 'spin'
command['ultimate'] = 'backends/uautomizer/Ultimate'
command['symbiotic'] = 'backends/symbiotic/bin/symbiotic'

# Command-line parameters, by backend.
options = {}
#options['esbmc'] = '--no-library --no-slice --no-bounds-check --no-div-by-zero-check --no-pointer-check  --no-align-check --no-pointer-relation-check --unwind 1 --no-unwinding-assertions'
options['esbmc'] = '--result-only --no-library --no-bounds-check --no-div-by-zero-check --no-pointer-check  --no-align-check --no-pointer-relation-check --unwind 1 --no-unwinding-assertions'
options['cbmc'] =     '--unwind 1 --no-unwinding-assertions' # --stop-on-fail'
options['cbmc-ext'] = '--unwind 1 --no-unwinding-assertions' # Note: cbmc-ext doesn't seem to work well with --32 and --assume?!
options['cbmc-svcomp2020'] =     '--unwind 1 --no-unwinding-assertions --stop-on-fail --trace' # SV-COMP requires 32bit for category Concurrency
options['llbmc'] = '-no-max-function-call-depth-checks -no-memory-free-checks -no-shift-checks -no-memcpy-disjoint-checks -no-memory-access-checks -no-memory-allocation-checks --max-loop-iterations=1 --no-max-loop-iterations-checks --ignore-missing-function-bodies -no-overflow-checks -no-div-by-zero-checks'
options['blitz'] = '--terminate-on-firstbug'
options['satabs'] = ''
options['2ls'] = ''
options['smack'] = '--unroll 1 '  # --bit-precise' <-- this won't find any errors at all1
options['klee'] = '-exit-on-error'
options['cpachecker'] = '-predicateAnalysis -spec sv-comp-reachability' # -spec sv-comp-reachability' # '-preprocess -heap 15000M -timelimit 86400 -noout -predicateAnalysis'
###options['ultimate'] = '--full-output --architecture 32bit --spec backends/UAutomizer-linux/prova.spc --file'
##options['ultimate'] = '-tc backends/UAutomizer-linux/config/AutomizerReach.xml -s backends/UAutomizer-linux/config/svcomp-Reach-32bit-Automizer_Default.epf -i'
options['ultimate'] = '-tc  backends/uautomizer/config/AutomizerReach.xml -s backends/uautomizer/config/svcomp-Reach-32bit-Automizer_Default.epf --rcfgbuilder.size.of.a.code.block=LoopFreeBlock --rcfgbuilder.size.of.a.code.block=LoopFreeBlock --rcfgbuilder.smt.solver=Internal_SMTInterpol --traceabstraction.smt.solver=Internal_SMTInterpol --traceabstraction.compute.interpolants.along.a.counterexample=Craig_TreeInterpolation --traceabstraction.trace.refinement.strategy=FIXED_PREFERENCES  -i'
options['symbiotic'] = '--32  --prp=prova.spc --sv-comp'

# Environment variables to be prefixed to the command line
export = {}
export['esbmc'] = ''
export['cbmc'] = ''
export['cbmc-ext'] = ''
export['cbmc-svcomp2020'] = ''
export['llbmc'] = ''
export['blitz'] = ''
export['satabs'] = ''
export['2ls'] = ''
export['smack'] = "CORRAL=\"mono backends/corral/bin/Debug/corral.exe\" PATH=backends/gentoo/usr/bin:backends/llvm-8.0.1.src/build/bin:backends/smack-2.4.0/build/bin/:$PATH"
export['klee'] = ''
export['cpachecker'] = ''
export['spin'] = ''
export['ultimate'] = 'PATH=backends/UAutomizer-linux:$PATH'
export['symbiotic'] = ''

# Expressions to check for from the log to see whether the verification went fine.
ok = {}
ok['esbmc'] = 'VERIFICATION SUCCESSFUL'
ok['cbmc'] = 'VERIFICATION SUCCESSFUL'
ok['cbmc-ext'] = 'VERIFICATION SUCCESSFUL'
ok['cbmc-svcomp2020'] = 'VERIFICATION SUCCESSFUL'
ok['blitz'] = 'VERIFICATION SUCCESSFUL'
ok['llbmc'] = 'No error detected.'
ok['cpachecker'] = 'Verification result: TRUE.'
ok['smack'] = 'SMACK found no errors' # ok['smack'] = 'Finished with 1 verified, 0 errors'
ok['satabs'] = 'VERIFICATION SUCCESSFUL'
ok['klee'] = 'DKJFHSDKJDFHSJKF' # no such thing for Klee?
ok['ultimate'] = 'RESULT: Ultimate proved your program to be correct!'
ok['symbiotic'] = 'RESULT: true'

# Expressions to check for from the log to see whether the verification failed.
ko = {}
ko['esbmc'] = 'VERIFICATION FAILED'
ko['cbmc'] = 'VERIFICATION FAILED'
ko['cbmc-ext'] = 'VERIFICATION FAILED'
ko['cbmc-svcomp2020'] = 'Violated property:'
ko['blitz'] = 'VERIFICATION FAILED'
ko['llbmc'] = 'Error detected.'
ko['cpachecker'] = 'Verification result: FALSE.' #ko['smack'] = 'Error BP5001: This assertion might not hold.\n'
ko['smack'] = 'SMACK found an error.' #ko['smack'] = 'Finished with 0 verified,'
ko['satabs'] = 'VERIFICATION FAILED'
ko['klee'] = 'ASSERTION FAIL: '
#ko['ultimate'] = 'Possible FailurePath:'
ko['ultimate'] = 'RESULT: Ultimate proved your program to be incorrect!'
ko['symbiotic'] = 'RESULT: false(unreach-call)'

# Specific versions of a verifier to be enforced, if required.
version = {}
version['cbmc'] = '5.4'
version['cbmc-ext'] = '5.4'
version['cbmc-svcomp2020'] = '5.12 (cbmc-5.12-d8598f8-1363-ge5a4d93)'
version['esbmc'] = 'ESBMC version 6.6.0 64-bit x86_64 linux'
version['cpachecker'] = 'CPAchecker 1.9 (OpenJDK 64-Bit Server VM 1.8.0_232)' #last line only!
version['smack'] = 'SMACK version 2.4.0'
version['ultimate'] = ''
version['symbiotic'] = ''

# Option to get version from the backend
versioncmd = {}
versioncmd['cbmc'] = '--version'
versioncmd['cbmc-ext'] = '--version'
versioncmd['cbmc-svcomp2020'] = '--version'
versioncmd['esbmc'] = '--version'
versioncmd['cpachecker'] = '-version'
versioncmd['smack'] = '--version'
versioncmd['ultimate'] = '--version'
versioncmd['symbiotic'] = ''


bufsize = 1024*1024        # buffer size limit for communicating threads
                           # (buffer replace pipes as they deadlong if text too long)
                           # Note: this parameter should be kept reasonably small,
                           # because allocation is very slow.


class feeder(core.module.BasicModule):
	def init(self):
		self.inputparam('backend', 'backend (blitz, cbmc, cbmc-ext, esbmc, llbmc, cpachecker, satabs, klee)', 'b', 'cbmc-ext', False)
		self.inputparam('time', 'analysis time limit (in seconds)', 't', '86400', False)
		self.inputparam('llvm', 'Clang or LLVM search path (only LLBMC and Klee)', 'p', '', True)
		#self.inputparam('output', 'output final file without analysis', 'o', '', True)
		self.inputparam('unwind', 'loop unwind bound', 'u', '1', False)
		self.inputparam('contexts', 'execution contexts', 'r', None, optional=True)
		self.inputparam('unwind', 'loop unwind bound', 'u', '1', False)
		self.inputparam('32', '32-bit wordlength', '', default=False, optional=True)  # e.g., SV-COMP concurrency
		self.inputparam('show-backend-output', 'show backend output (stderr+stdout)', '', default=False, optional=True)

		# Parallel analysis only
		self.inputparam('extrargs', 'extra arguments to use for parallel analysis (one per core)', 'x', [], False)
		self.inputparam('from', 'first search partition to analyse (default=0)', 'f', default=0, optional=True)
		self.inputparam('to', 'last search partition to analyse (default=cores-1)', 't', default=0, optional=True)

		self.inputparam('extra', 'extra argument(s) for the backend', 'j', '', False)

		self.outputparam('exitcode')
		self.outputparam('memsize')


	def signal(self,signum,frame):
		self.warn("received external signal (%s)" % signum)
		raise Exception("received external signal (%s)" % signum)


	def loadfromstring(self, string, env):
		timelimit = self.getinputparam('time')
		backend = self.getinputparam('backend').lower()
		witness = self.getinputparam('witness')
		extrargs = self.getinputparam('extrargs') if self.getinputparam('extrargs') is not None else []
		contexts = int(self.getinputparam('contexts')) if self.getinputparam('contexts') is not None else 0
		unwind =  int(self.getinputparam('unwind'))
		bits32 = True if self.getinputparam('32') is not None else False
		showbackendoutput = True if self.getinputparam('show-backend-output') is not None else False
		cores = 1 if len(extrargs) in (0,None) else len(extrargs)
		coresstart = int(self.getinputparam('from')) if self.getinputparam('from') is not None else 0
		coresstop = int(self.getinputparam('to')) if self.getinputparam('to') is not None else cores-1
		extra = self.getinputparam('extra')

		#if coresstop-coresstart+1 > 1 and coresstop-coresstart+1 != cores:
		#	self.error("Parallel analysis not supported with these parameters")

		if coresstop-coresstart+1 > 1:
			self.log("parallel analysis using %s cores, partitions [%s...%s], %s overall partitions" % (coresstop-coresstart+1,coresstart,coresstop,cores))
		else:
			self.debug("no parallel analysis")

		if coresstop-coresstart+1 > multiprocessing.cpu_count():
			self.warn("exceeding the CPU count: spawning %s separate backend processes on a host with %s CPUs" % (coresstop-coresstart+1,multiprocessing.cpu_count()))

		#seqfile = core.utils.rreplace(env.inputfile, '/', '/_cs_', 1) if '/' in env.inputfile else '_cs_' + env.inputfile
		seqfile = core.utils.filepathprefix(env.inputfile,'_cs_')
		seqfile = seqfile[:-2] + '.c' if seqfile.endswith('.i') else seqfile
		core.utils.saveFile(seqfile,string,binary=False)

		# Make sure the backend works, and check the version, if required.
		try:
			testcmd = "%s %s" % (command[backend],versioncmd[backend])
			p = subprocess.Popen(testcmd,shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
			out,err = p.communicate()
			out = err + out  # some backends will write the version on stderr....
			backendversion = out.splitlines()[-1].decode()

			self.debug("running backend (%s) version (%s)" % (backend,backendversion))

			if backend in version and version[backend] != backendversion and version[backend] != '':
				pass
				##self.error("backend version (%s) required, installed version is (%s)" % (version[backend],backendversion))
		except Exception as e:
			self.error("unable to execute the backend (%s)\n%s" % (command[backend],e))


		# Add backend-specific parameters to the command line
		cmd = "%s %s %s %s" % (command[backend],options[backend],seqfile,extra)

		if backend == 'esbmc':
			if bits32: cmd += ' --32'
		elif backend == 'cbmc':
			if bits32: cmd += ' --32'
		elif backend == 'cbmc-svcomp2020':
			if bits32: cmd += ' --32'
		elif backend == 'cbmc-ext':
			if bits32: self.error("backend (%s) in 32-bit mode not supported" % backend)
		elif backend == 'llbmc':
			clangpath = '' if self.getinputparam('llvm') is None else self.getinputparam('llvm')
			clangexe = clangpath + '/clang'
			cmd = "%s -c -g -I. -emit-llvm %s -o %s.bc 2> %s " % (clangexe, seqfile, seqfile[:-2], logfile)
			p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
			out, err = p.communicate()
			core.utils.saveFile(os.path.dirname(seqfile) + '/clang_stdout.log', out)
			core.utils.saveFile(os.path.dirname(seqfile) + '/clang_stderr.log', err)
			# Launch LLBMC
			cmd = command[backend] + ' ' + options[backend] + ' ' + seqfile[:-2] + '.bc'
		elif backend == 'blitz':
			pass
		elif backend == 'satabs':
			pass
		elif backend == '2ls':
			pass
		elif backend == 'klee':
			# klee needs llvm-gcc version 2.9
			clangpath = '' if self.getinputparam('llvm') is None else self.getinputparam('llvm')
			clangexe = clangpath + '/clang' if clangpath != '' else 'clang'
			cmd = "%s -c -g -emit-llvm %s -o %s.bc " % (clangexe, seqfile, seqfile[:-2])
			p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
			out, err = p.communicate()
			core.utils.saveFile(os.path.dirname(seqfile) + '/clang_stdout.log', out)
			core.utils.saveFile(os.path.dirname(seqfile) + '/clang_stderr.log', err)
			# Launch Klee
			cmd = command[backend] + ' ' + options[backend] + ' ' + seqfile[:-2] + '.bc'
		elif backend == 'cpachecker':
			if bits32: cmd += ' -32'
			cmd += ' -timelimit 1200'
		elif backend == 'smack':
			pass
		elif backend == 'ultimate':
			# need to pre-process first
			cmd = "cpp %s > %s.preprocessed.i " % (seqfile, seqfile[:-2])
			p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
			out, err = p.communicate()

			#cmd = "rm -rf /home/omar/cseq/backends/uautomizer/.ultimate"    # ultimate workspace gets corrupted sometimes
			p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
			out, err = p.communicate()

			# Launch Ultimate
			cmd = command[backend] + ' ' + options[backend] + ' ' + seqfile[:-2] + '.preprocessed.i'
			#cmd += ' --core.toolchain.timeout.in.seconds 500'

		# A sub-process is spawn from the shell to execute the backend, but
		# it won't terminate when the shell terminates (e.g., upon a timeout):
		# the backend sub-process will then become a child of init.
		#
		# Using exec solves the issue.
		#
		# This is necessary when redirecting stderr (i.e., 2>&1), but
		# without redirection doesn't seem to be required.
		#cmd = 'ulimit -Sv %s && %s exec %s 2>&1' % (1024*1024*16,export[backend],cmd)
		cmd = '%s exec %s 2>&1' % (export[backend],cmd)
		#cmd = '%s %s 2>&1' % (export[backend],cmd)

		signal.signal(signal.SIGTERM, self.signal)

    	# Handling of memory and time restrictions.
		##
		## `-t T` - set up CPU+SYS time limit to T seconds
		## `-m M` - set up virtual memory limit to M kilobytes
		#memorylimit = 1000*memorylimit # kBytes --> mBytes
		#timespacecheck = 'timeout/timeout'
		#if timelimit > 0: timespacecheck += ' -t %s' % (timelimit)
		#if memorylimit > 0: timespacecheck += ' -m %s' % (memorylimit)

		# Single-threaded feeder (Cseq 1.9) [SV-COMP 2020]
		#self.debug("invoking backend [%s]" % backend)
		#self.debug("backend command line: [%s]" % (cmd))
		#self.debug("timelimit: [%s]" % (timelimit))
		#p = core.utils.Command(cmd)
		#out,err,code,memsize = p.run(timeout=int(timelimit))   # store stdout, stderr, process' return value
		#
		#self.debug("backend exitcode [%s]" % code)
		#self.setoutputparam('exitcode', code)
		#self.setoutputparam('memsize', memsize)
		#
		##if env.debug:
		#if 'warning' in err:
		#	self.warn('warnings on stderr from the backend\n' +err)
		#
		#if backend not in ('klee', ):
		#	core.utils.saveFile(seqfile + '.' + backend + '.log', out)   # klee outputs errors to stdout, all other backends to stderr
		#	self.output = out
		#else:
		#	####core.utils.saveFile(logfile, err)
		#	self.output = err

		processes = []     # a vector of sub-processes to spawn separate threads
		lock = multiprocessing.Lock()

		# Thread-safe shared vectors of:
		# process identifiers, process exit codes,
		# spawned process identifiers, and memory usage.
		#
		# Every process fills in its own entries.
		# (handling shared data structures in Python = definitely not so nice).
		pool = multiprocessing.Array('i', [-1 for i in range(cores)])      # -1=not started, 0=terminated
		code = multiprocessing.Array('i', [-1 for i in range(cores)])      # sub-process exit codes
		childpid = multiprocessing.Array('i', [-1 for i in range(cores)])  # -1=not set, child processes PIDs (i.e., PID of the spawned backend)
		bugfound = multiprocessing.Array('i', [0 for i in range(cores)])      # 0=not found, 1=found
		memory = multiprocessing.Array('i', [0 for i in range(cores)])     # memory usage

		# Communication buffers where sub-processes will send
		# the output (stdout,stderr) from the backend.
		#
		# Better than using pipes,
		# as pipes deadlock if one of the processes sends too much data, and
		# there is no portable way to figure out the limit.
		buff1 = multiprocessing.Array(ctypes.c_char, b'\0'*bufsize)
		buff2 = multiprocessing.Array(ctypes.c_char, b'\0'*bufsize)

		starttime = time.time()

		#logfile = 'log/'+seqfile+'.u%sc%s.c%s.from%sto%s' %(unwind,contexts,cores,coresstart,coresstop) # [PPoPP 2020]
		logfile = seqfile+'.c%s.from%sto%s' %(cores,coresstart,coresstop)


		######MEMORY LIMIT -- enable for benchmarking (e.g., SV-COMP)
		######resource.setrlimit(resource.RLIMIT_AS, (15 * 1024*1024*1024, resource.RLIM_INFINITY))

		try:
			for id in range(coresstart,coresstop+1):
				newlogfile = logfile +'.partition%s.log' % id
				args = '' if coresstart==coresstop else extrargs[id]
				p = multiprocessing.Process(target=self.feed, args=(id,coresstart,coresstop, cmd+' '+args,timelimit,backend,newlogfile, pool,childpid,bugfound,memory, lock, starttime,    buff1, buff2))
				processes.append(p)
				p.start()

			# Wait for all processes to terminate
			# (the first process to find an error -if any- terminates the others).
			for p in processes:
				p.join()

			# In any case,
			# only one of the processes' output will make it to this point
			# through the shared buffers:
			# either the first process that finds an error trace (or crashes)
			# or the last one to terminate (or time out) without finding anything.
			self.output = buff1.value
			err = buff2.value

			#if len(err) > 0:
			#	self.warn('output on stderr from the backend\n' +err)
			#self.setoutputparam('exitcode', code)         # backend process exitcode
			self.setoutputparam('memsize', sum(memory))   # overall memory usage
			core.utils.saveFile(logfile+'.log',self.output)
		except:
			self.debug("shutting down any pending sub-process")

			for k in range(coresstart,coresstop+1):
				(c,p) = (childpid[k],pool[k])  # store them as another thread may change them

				if c!=0 and c!=-1 and p!=0:
					self.debug("[%s] kill  +%0.2fs pid:[%s] killing backend process %s spawned from pid %s" % (id,time.time()-starttime,os.getpid(),childpid[k],pool[k]))
					try:  # might have terminated meanwhile
						os.killpg(os.getpgid(c), signal.SIGTERM)  # Send the signal to all the process groups
						#os.kill(c,signal.SIGTERM)
						#os.kill(c,signal.SIGKILL)
						childpid[k] = 0
						self.debug("[%s] kill success" % id)
					except:
						self.debug("[%s] kill fail" % id)

		# Cleaning up
		if backend == 'ultimate':
			cmd = "rm %s.preprocessed.i " % (seqfile[:-2])
			p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
			out, err = p.communicate()

		if showbackendoutput:
			self.log(core.utils.indent(buff1.value.decode()))
			self.log(core.utils.indent(buff2.value.decode()))

		self.output = self.output.decode()

	''' Spawn a separate process to invoke the backend with the given command line.

		Upon UNSAFE verdict (i.e., error trace found),
		kill the other sub-processes, then
		return stdout and stderr through the shared buffers.

		On crashing terminate all other processes.

		On successfully terminating without crashing or counterexamples,
		do nothing.

		Upon SAFE or UNKNOWN verdict:
		if this is the last process to terminate,
		update the exit code, send the output to the pipe, and close it;
		otherwise, no action is taken apart from saving the logfile.

	'''
	def feed(self,  id,coresstart,coresstop,  cmd,timeout,backend,logfile,  pool,childpid,bugfound,mem,  l,   starttime,    buff1,buff2):
		pool[id] = os.getpid()  # store this process' pid into the shared array
		self.debug("[%s] start +%0.2fs pid:[%s] cmd:[%s] log:[%s]" %(id,time.time()-starttime,os.getpid(),cmd,logfile))

		try:
			# Spawn process and execute backend.
			p = core.utils.CommandPid(cmdline=cmd)
			newpid = p.spawn()
			childpid[id] = newpid    # pid of the backend just spawned

			self.debug("[%s] spawn +%0.2fs pid:[%s] spawning pid %s" %(id,time.time()-starttime,os.getpid(),childpid[id]))
			out,err,cod,mem[id] = p.wait(int(timeout))
			#print("======> %s <=====" % out)
			out = out.decode()
			#print("+++++++++++> %s <=====" % out)


			l.acquire()
			self.debug("[%s] backend exitcode [%s]" % (id,cod))

			pool[id] = 0     # sub-process terminated
			childpid[id] = -1

			# UNSAFE, SAFE, or UNKNOWN?
			outcome =  'unknown'

			for line in out.splitlines():
				if ko[backend] in line:
					outcome = 'unsafe'
					break
				elif ok[backend] in line:
					outcome = 'safe'
					break

			# If UNSAFE, kill every process in childpid[].
			#l.acquire()
			self.debug("[%s] %s  +%0.2fs pid:[%s] cmd:[%s]" %(id,outcome,time.time()-starttime,os.getpid(),cmd))

			if outcome == 'unsafe':
				bugfound[id] = True

				for k in range(coresstart,coresstop+1):
					(c,p) = (childpid[k],pool[k])

					if c!=0 and c!=-1 and p!=0:
						self.debug("[%s] kill  +%0.2fs pid:[%s] killing backend process %s spawned from pid %s" % (id,time.time()-starttime,os.getpid(),c,p))

						try:
							os.killpg(os.getpgid(c), signal.SIGTERM)  # Send the signal to all the process groups
							#os.kill(c,signal.SIGTERM)
							#os.kill(c,signal.SIGKILL)
							childpid[k] = 0
							self.debug("[%s] kill success" % id)
						except:
							self.debug("[%s] kill fail" % id)

			# Is this the only process still running?
			lastone = True

			for k in range(coresstart,coresstop+1):  #for k in range(coresstart,coresstop):
				if k!=id and pool[k]!=0:
					lastone = False

			# If UNSAFE or last process to terminate,
			# store stdout and stderr into the shared buffers.
			#
			# TODO: just save this on file if too long.
			if outcome == 'unsafe' or (lastone and True not in bugfound):
				if len(out) > bufsize:
					self.warn("stdout backend output too long (%s), trimming text down to last (%s) characters; this will likely break counterexample generation" % (len(out),bufsize))
					out = out[-bufsize:]

				if len(err) > bufsize:
					self.warn("stderr backend output too long (%s), trimming text down to last (%s) characters; this will likely break counterexample generation" % (len(err),bufsize))
					err = err[-bufsize:]

				buff1.value = out.encode('ascii')
				buff2.value = err

			self.setoutputparam('exitcode', cod)  #('exitcode', code[id])
			core.utils.saveFile(logfile,out,binary=False) # dump error trace to file
			l.release()
		except Exception as e:
			traceback.print_exc(file=sys.stdout)
			pass






