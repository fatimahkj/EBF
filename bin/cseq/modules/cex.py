""" CSeq Program Analysis Framework
    counterexample translation module

The counterexample generation implemented in this module
is specific for the Lazy schema (lazyseq.py) but most of it should in principle work
for any translation where the relationship betweeen the input of the first module and the output of the last module
is a points-to-set function, or equivalently,
the linemap from the output of the last module to the input of the first module
is a surjective (and therefore invertible) function.

Author:
    Omar Inverso

Changes:
    2021.10.20  obsolete options removed
    2020.12.29  using ASCII-encoded strings rather then UTF
    2020.12.21  slight changes to support Python 3
    2020.11.30  loop bound check (cbmc-only)
    2020.10.16  __VERIFIER_error() -> reach_error() [SV-COMP 2021]
    2020.04.09  no longer using exit codes from feeder module (not portable)
    2020.03.24 (CSeq 2.0)
    2020.03.23  cbmc-ext backend [PPoPP 2020]
    2019.11.15 (CSeq 1.9) pycparserext [SV-COMP 2020]
    2019.11.15  no longer mapping pthread_xyz function identifiers
    2018.11.08 [SV-COMP 2019] svcomp mode (incl. witness generation)
    2016.08.12  show memory usage
    2016.08.09  add option for backend framac
    2015.07.16  improved cbmc error trace readability by showing more simulated pthread states (Omar,Truc)
    2015.07.15  fixed line mapping for mutex destroy (Truc)
    2015.07.07  1st version

To do:
  - map thread creation and thread join using similar way for mutexes
  - pthread_cond_wait() cex entry does not show lock parameter
  - fix __cs_thread_index detection of context switch

"""
import pycparserext.ext_c_parser, pycparser.c_ast, pycparserext.ext_c_generator
import core.module, core.parser, core.utils
import sys
import time

# Expressions to check for from the log to see whether the verification went fine.
ok = {}
ok['esbmc'] = 'VERIFICATION SUCCESSFUL'
ok['cbmc'] = 'VERIFICATION SUCCESSFUL'
ok['cbmc-ext'] = 'VERIFICATION SUCCESSFUL'
ok['cbmc-svcomp2020'] = 'VERIFICATION SUCCESSFUL'
ok['blitz'] = 'VERIFICATION SUCCESSFUL'
ok['llbmc'] = 'No error detected.'
ok['cpachecker'] = 'Verification result: TRUE.'
ok['smack'] = 'SMACK found no errors' # prefix
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
ko['smack'] = 'SMACK found an error.'
ko['satabs'] = 'VERIFICATION FAILED'
ko['klee'] = 'ASSERTION FAIL: '
#ko['ultimate'] = 'Possible FailurePath:'
ko['ultimate'] = 'RESULT: Ultimate proved your program to be incorrect!'
ko['symbiotic'] = 'RESULT: false(unreach-call)'


# Backend reject/error.
backendERROR = {}
backendERROR['cbmc'] = 'CONVERSION ERROR'
backendERROR['cbmc-ext'] = 'CONVERSION ERROR'
backendERROR['cbmc-svcomp2020'] = 'CONVERSION ERROR'


class cex(core.module.BasicModule):
	# when in SV-COMP:
	#      - do not consider the exit values from the backend (they do not work well)
	#      - save the witnesses in their specific format
	svcomp = None
	entrypoint = None      # coords to the program's entry point (i.e. beginning of main() function)
	errorpoint = None      # coords to property violation
	loopheads = []         # coords to first statement of all loops
	times = {}
	lastloophead = 0


	def init(self):
		self.inputparam('backend', 'backend', 'b', default='cbmc-ext', optional=False)
		self.inputparam('cex', 'show counterexample (CBMC only)', '', default=False, optional=True)
		#self.inputparam('exitcode', 'backend exit-code', '', default=0, optional=True)
		self.inputparam('threadnamesmap', 'map from thread copies to thread function', '', default=None, optional=True)
		self.inputparam('threadindexes', 'map from thread copies to thread indexes', '', default=None, optional=True)
		self.inputparam('threadindextoname', 'map from thread index to thread function name', '', default=None, optional=True)
		self.inputparam('varnamesmap', 'map for replaced variable names', '', default=None, optional=True)
		self.inputparam('coordstofunctions', 'map from input coords to function ids', '', default=None, optional=True)
		self.inputparam('sv-comp', 'SV-COMP counterexample format', '', default=False, optional=True)
		self.inputparam('witness', 'save counterexample to file', 'w', None, True)
		self.inputparam('entry', 'entry point of the program (i.e., coords to main() function', 'e', default='0', optional=False)
		self.inputparam('threadsizes', 'number of context-switch points', '', default=None, optional=True)
		self.inputparam('threadendlines', 'line number for the last statement in each thread', '', default=None, optional=True)
		self.inputparam('loopheads', 'line number of loop heads', '', default=None, optional=True)
		self.inputparam('unwind-check', 'check loop unwinding assertions', '', default=False, optional=True)


	def loadfromstring(self, string, env):
		self.env = env

		self.backend = self.getinputparam('backend').lower()
		#self.code = self.getinputparam('exitcode')
		self.memsize = self.getinputparam('memsize') if self.getinputparam('memsize') else 0
		self.threadnamesmap = self.getinputparam('threadnamesmap')

		self.threadindexes = self.getinputparam('threadindexes')
		self.threadreversedindexes = {}
		for x in self.threadindexes: self.threadreversedindexes[self.threadindexes[x]] = x

		self.threadindextoname = self.getinputparam('threadindextoname')
		self.varnamesmap = self.getinputparam('varnamesmap')
		self.coordstofunctions = self.getinputparam('coordstofunctions')
		self.svcomp = True if self.getinputparam('sv-comp') is not None else False
		self.outputtofiles = self.env.outputtofiles
		self.witness = self.getinputparam('witness')
		self.entrypoint = self.getinputparam('entry')
		self.threadsizes = self.getinputparam('threadsizes')
		self.threadendlines = self.getinputparam('threadendlines')
		self.showcex = True if self.getinputparam('cex') is not None else False
		self.loopheads = self.getinputparam('loopheads')

		self.unwindcheck = True if self.getinputparam('unwind-check') is not None else False

		# program has loops
		'''
		if len(self.loopheads) > 0: self.error("LOOPS (%s)" % env.inputfile)
		else: self.error("NOLOOP (%s)" % env.inputfile)
		'''

		'''
		self._showfullmapback()
		for x in self.coordstofunctions: print "line:%s file:%s function:%s " % (x[0],x[1],self.coordstofunctions[x])
		print str(self.threadindextoname)
		print str(self.coordstofunctions)
		for x in self.outputtofiles: print ("%s -> %s" % (x, self.outputtofiles[x]))
		sys.exit(1)
		'''

		self.output = self._shortanswer(string)
		cex = ''

		# error trace requested
		if self.showcex or self.witness:
			# translate CBMC's counterexample anyway (this also generates SV-COMP chunks)
			cex = self._translateCPROVERcex(string)

			# replace the counterexample with the one in SV-COMP format
			if self.svcomp:
				import hashlib
				openedFile = open(env.inputfile)
				# readFile = openedFile.read() # Python 2
				#readFile = openedFile.read().encode('ascii')
				readFile = openedFile.read().encode()
				sha256hash = hashlib.sha256(readFile)
				hash = sha256hash.hexdigest()

				import datetime
				timestamp = datetime.datetime.utcnow().replace(microsecond=0).isoformat()
				timestamp += 'Z' if not timestamp.endswith('Z') else ''

				cex = self.chunks(env.inputfile,hash,timestamp,self.errorpoint,self.entrypoint,self.svcompwitness)

			# save if needed, or add the error trace to the module's output
			if self.witness is not None: core.utils.saveFile(self.witness,cex,binary=False)
			if self.showcex: self.output = cex + self.output


	''' Short interpretation of the backend answer.
	'''
	def _shortanswer(self,input):
		outcome = ''
		mem = maxmem = cpu = stale = variables = clauses = 0

		'''
		for line in input:  # variables and clauses extraction
			if ' variables, ' in line:
				splitline = line.split()
				variables = splitline[0]
				clauses = splitline[2]
		'''

		# scan the backend's output to check the outcome of the verification
		for line in input.splitlines():
			if '(signed int)__cs_loop_check' in line:
				outcome = 'LOOP BOUND EXCEEDED'
				break;
			if ko[self.backend] in line:
				outcome = 'UNSAFE'
				break
			elif ok[self.backend] in line and not self.unwindcheck:
				outcome = 'SAFE'
				break
			elif ok[self.backend] in line and self.unwindcheck:
				outcome = 'SAFE'
				break
			#elif self.backend in ('cbmc','cbmc-ext') and self.code == 6:
			#	outcome = 'BACKENDREJECT'

		# Exit values from backend process do not seem to work properly in SV-COMP2019,
		# so we can't use self.code to detect timeouts.
		#
		if not self.svcomp:
			#if outcome == '' and self.code == -9: outcome = 'TIMEOUT' # backend timeout
			#elif outcome == '': outcome = 'UNKNOWN'
			if outcome == '': outcome = 'UNKNOWN'
		else:
			# when in SV-COMP mode,
			# anything else than SAFE or UNSAFE is UNKNOWN (including TIMEOUTs)
			if outcome == '': outcome = 'UNKNOWN' # backend timeout

		#
		if outcome == 'UNKNOWN': result = core.utils.colors.YELLOW + outcome + core.utils.colors.NO
		elif outcome == 'LOOP BOUND EXCEEDED': result = core.utils.colors.YELLOW + outcome + core.utils.colors.NO
		elif outcome == 'BACKENDREJECT': result = core.utils.colors.BLUE + outcome + core.utils.colors.NO
		elif outcome == 'TIMEOUT': result = core.utils.colors.YELLOW + outcome + core.utils.colors.NO
		elif outcome == 'SAFE': result = core.utils.colors.GREEN + outcome + core.utils.colors.NO
		#elif outcome == 'CONCLUSIVE SAFE': result = core.utils.colors.GREEN + outcome + core.utils.colors.NO
		elif outcome == 'UNSAFE': result = core.utils.colors.RED + outcome + core.utils.colors.NO

		return "%s, %s, %0.2fs, %0.2fMB" % (self.env.inputfile,result,time.time()-self.env.starttime, (self.memsize/1024.0))


	''' Full counterexample translation for CBMC
	   (and other tools based on the CPROVER framework)
	'''
	svcompwitness = ''        # what a waste of my time
	svcomplaststate = 1       # id of the last node (used for adding edges)

	def _translateCPROVERcex(self,cex):
		if self.backend not in ('cbmc','cbmc-ext','cbmc-svcomp2020'):
			self.warn('error trace translation for backend %s is yet supported.' % self.backend)
			return ''

		translatedcex = ''
		lines = cex.split('\n')
		k = cex[:cex.find('Counterexample:')].count('\n')+1+1
		separator = "----------------------------------------------------"

		while k<len(lines):
			# case 1: another transition to fetch
			if lines[k].startswith('State ') and lines[k+1] == separator:
				A,B,C = lines[k],lines[k+1],lines[k+2]

				# the part below the separator might be
				# more than one line long..
				j=1
				while ( k+2+j<len(lines) and
					not lines[k+2+j].startswith('State ') and
					not lines[k+2+j].startswith('Violated property') ):
					C+=lines[k+2+j]
					j+=1

				#
				#####if not self.hasloops(): self.error("SKIP_NOLOOP %s" % (env.inputfile))

				X,Y,Z = self._mapCPROVERstate_noloops(A,B,C) if not self.hasloops() else self._mapCPROVERstate_loops(A,B,C)

				if X != '':
					translatedcex += '%s\n' % X
					if Y != '': translatedcex += '%s\n' % Y
					if Z != '': translatedcex += '%s\n' % Z
					translatedcex += '\n'
			# case 2: final transation with property violation
			elif lines[k].startswith('Violated property'):
				Y,Z,W = self._mapCPROVERendstate(lines[k+1],lines[k+2],lines[k+3])

				if '__cs_loop_check' in Z: # loop unwinding assertion violation
					translatedcex += 'Violated property:\n%s\n%s\n%s\n' % (Y,Z,W)
					translatedcex += '\nLOOP BOUND EXCEEDED'
				else:
					translatedcex += 'Violated property:\n%s\n%s\n%s\n' % (Y,Z,W)
					translatedcex += '\nVERIFICATION FAILED'

			k+=1

		if len(translatedcex) > 0:
			translatedcex = "Counterexample:\n\n" + translatedcex + '\n\n'

		return translatedcex


	''' Returns the coords of the original input file
		in the format (line,file)
		corresponding to the given output line number, or
		(?,?) if unable to map back.
	'''
	def sbizz(self,lineno):
		nextkey = 0
		inputfile = ''

		lastmodule = len(self.env.maps)

		if lineno in self.env.maps[len(self.env.maps)-1]:
			firstkey = nextkey = lastkey = lineno

			for modno in reversed(range(0,lastmodule)):
				if nextkey in self.env.maps[modno] and nextkey != 0:
					lastkey = nextkey
					nextkey = self.env.maps[modno][nextkey]
				else:
					nextkey = 0

				if nextkey!=0 and modno == 0 and lastkey in self.outputtofiles:
					inputfile = self.env.outputtofiles[lastkey]

		if nextkey == 0: nextkey = '?'
		if inputfile == '': inputfile = '?'

		return (nextkey, inputfile)


	'''
	'''
	__lastthreadID = '0'
	__startedthreadID = []       # avoid entering the same thread multiple times
	__terminatedthreadID = []    # avoid reporting the same thread terminating multiple times
	lastlastlast = None          # context-switch detection

	def _mapCPROVERstate_noloops(self,A,B,C,showbinaryencoding=False):
		Aout = Bout = Cout = ''
		keys = {}

		# Fetch values.
		try:
			# 1st line
			tokens = A.split()

			for key,value in zip(tokens[0::2],tokens[1::2]):
				keys[key] = value

			stateout = keys['State']

			# 3rd line
			line3 = C.strip()
			lvalue = line3[:line3.find('=')]
			rvalue = line3[len(lvalue)+1:]

			# double-check parsing correctness
			if 'function' in keys: Aout = "State %s file %s line %s function %s thread %s" % (keys['State'],keys['file'],keys['line'],keys['function'],keys['thread'])
			else: Aout = "State %s file %s line %s thread %s" % (keys['State'],keys['file'],keys['line'],keys['thread'])

			Cout = "  %s=%s" % (lvalue,rvalue)

			if A != Aout or C != Cout:
				self.warn('unable to parse counterexample state %s' % keys['State'])
				return ('','','')
		except Exception as e:
			self.warn('unable to parse counterexample state')
			return ('','','')

		# Special case: context switching.
		if lvalue.startswith('__cs_thread_index') and 'function' in keys and keys['function'] != '':
			threadout = rvalue[:rvalue.find(' ')]
			threadindexout = ''
			self.__lastthreadID = threadout
			if int(threadout) in self.threadindextoname: threadindexout = self.threadindextoname[int(threadout)]
			if 'line' in keys: lineout,fileout = self.sbizz(int(keys['line']))
			###Aout = "State %s <<<%s>>>" % (stateout,keys['line'])
			Aout = "State %s" % (stateout)
			Cout = "  thread %s (%s) scheduled" % (threadout,threadindexout)

			'''
			#
			tid = int(self.__lastthreadID)##self.threadreversedindexes[int(self.__lastthreadID)] if int(self.__lastthreadID) in self.threadreversedindexes else 'main'
			fname = self.threadindextoname[int(self.__lastthreadID)]
			self.chunk(stateout,self.svcomplaststate,stateout,tid                ,lineout,lineout,'enterFunction',fname)
			self.svcomplaststate = stateout
			'''

			return Aout,"- - - - - - - - - - - - - - - - - - - - - - - - - - ",Cout

		# Special case: thread creation
		if lvalue == '__cs_threadID':
			threadout = ''
			threadindexout = ''
			fileout = ''
			tid = rvalue[:rvalue.find(' (')]   # id of created thread
			if 'line' in keys: lineout,fileout = self.sbizz(int(keys['line']))
			Aout = "State %s file %s line %s thread %s" % (stateout,fileout,lineout,self.__lastthreadID)
			Cout = '  pthread_create(thread %s)' % (tid)

			# SV-COMP nonsense
			# nodeid,edgesource,edgetarget,threadid,startline,endline,extrakey,extravalue
			self.chunk(stateout,self.svcomplaststate,stateout,self.__lastthreadID,lineout,lineout,'createThread',tid)
			self.svcomplaststate = stateout
			newstateout = str(stateout)+'-2'
			##self.chunk(newstateout,self.svcomplaststate,newstateout,self.__lastthreadID                ,lineout,lineout,'enterFunction',self.threadindextoname[int(tid)])
			self.chunk(newstateout,self.svcomplaststate,newstateout,tid                ,lineout,lineout,'enterFunction',self.threadindextoname[int(tid)])
			self.svcomplaststate = newstateout

			return Aout,"- - - - - - - - - - - - - - - - - - - - - - - - - - ",Cout


		# Special case: thread exit (i.e., last statement executed)
		if lvalue.startswith('__cs_pc[') and str(self.__lastthreadID) != '0': # and rvalue == self.threadsizes[self.__lastthreadID]:
			#self.log("---- - - - - - - - - - >>>>> <last:%s> " % (self.__lastthreadID))
			#self.log("---- - - - - - - - - - >>>>> <last:%s> " % self.threadindextoname[int(self.__lastthreadID)]   )

			#self.log("namesmap %s" % self.threadnamesmap)
			#self.log("indexes %s" % self.threadindexes)
			#self.log("reversedindexes %s" % self.threadreversedindexes)
			#self.log("sizes %s" % self.threadsizes)
			#self.log("endlines %s" % self.threadendlines)
			#self.log("indextoname %s" % self.threadindextoname)

			# Thread termination detection:
			# if the updated program counter for the simulated thread is exactly its size,
			# then the thread must have terminated.
			size = rvalue[:rvalue.find(' (')]
			check = self.threadsizes[self.threadreversedindexes[int(self.__lastthreadID)]]

			if str(size) == str(check) and int(self.__lastthreadID) not in self.__terminatedthreadID:
				#int(self.__lastthreadID) in self.__terminatedthreadID
				self.__terminatedthreadID.append(int(self.__lastthreadID))

				#########self.log("terminatedid %s" % self.__terminatedthreadID)

				fileout = ''
				lineout = self.threadendlines[self.threadreversedindexes[int(self.__lastthreadID)]]
				Aout = "State %s file %s line %s thread %s" % (stateout,fileout,lineout,self.__lastthreadID)
				Cout = '  pthread_exit(thread %s)' % (self.__lastthreadID)

				tid = self.threadnamesmap[self.threadreversedindexes[int(self.__lastthreadID)]]
				self.chunk(stateout,self.svcomplaststate,stateout,self.__lastthreadID,lineout,lineout,'returnFrom',tid)
				self.svcomplaststate = stateout

				return Aout,"- - - - - - - - - - - - - - - - - - - - - - - - - - ",Cout

		# Special case: cond signal
		if lvalue == '__cs_cond_to_signal':
			threadout = ''
			threadindexout = ''
			fileout = ''
			if 'line' in keys: lineout,fileout = self.sbizz(int(keys['line']))
			Aout = "State %s file %s line %s thread %s" % (stateout,fileout,lineout,self.__lastthreadID)
			Cout = '  pthread_cond_signal(%s)' % (rvalue[:rvalue.find(' (')])
			return Aout,"- - - - - - - - - - - - - - - - - - - - - - - - - - ",Cout

		# Special case: cond wait
		if lvalue == '__cs_cond_to_wait_for':
			threadout = ''
			threadindexout = ''
			fileout = ''
			if 'line' in keys: lineout,fileout = self.sbizz(int(keys['line']))
			Aout = "State %s file %s line %s thread %s" % (stateout,fileout,lineout,self.__lastthreadID)
			Cout = '  pthread_cond_wait(%s,?)' % (rvalue[:rvalue.find(' (')])
			return Aout,"- - - - - - - - - - - - - - - - - - - - - - - - - - ",Cout

		# Special case: mutexes lock and unlock
		if lvalue == '__cs_mutex_to_lock' and 'function' in keys and not keys['function']=='pthread_cond_wait_2':
			threadout = ''
			threadindexout = ''
			fileout = ''
			if 'line' in keys: lineout,fileout = self.sbizz(int(keys['line']))
			Aout = "State %s file %s line %s thread %s" % (stateout,fileout,lineout,self.__lastthreadID)
			Cout = '  pthread_mutex_lock(%s)' % (rvalue[:rvalue.find(' (')])
			return Aout,"- - - - - - - - - - - - - - - - - - - - - - - - - - ",Cout

		if lvalue == '__cs_mutex_to_unlock' and 'function' in keys and not keys['function']=='pthread_cond_wait_1' :
			threadout = ''
			threadindexout = ''
			fileout = ''
			if 'line' in keys: lineout,fileout = self.sbizz(int(keys['line']))

			Aout = "State %s file %s line %s thread %s" % (stateout,fileout,lineout,self.__lastthreadID)
			Cout = '  pthread_mutex_unlock(%s)' % (rvalue[:rvalue.find(' (')])
			return Aout,"- - - - - - - - - - - - - - - - - - - - - - - - - - ",Cout

		# Special case: mutexes destroy
		if lvalue == '__cs_mutex_to_destroy':
			threadout = ''
			threadindexout = ''
			fileout = ''
			if 'line' in keys: lineout,fileout = self.sbizz(int(keys['line']))
			Aout = "State %s file %s line %s thread %s" % (stateout,fileout,lineout,self.__lastthreadID)
			Cout = '  pthread_mutex_destroy(%s)' % (rvalue[:rvalue.find(' (')])
			return Aout,"- - - - - - - - - - - - - - - - - - - - - - - - - - ",Cout

		# Special case: explicit __CSEQ_message().
		if lvalue== '__cs_message':
			threadout = ''
			threadindexout = ''

			if 'line' in keys: lineout,fileout = self.sbizz(int(keys['line']))

			if 'function' in keys:
				#if keys['function'] in self.threadindexes: threadout = self.threadindexes[keys['function']]
				if keys['function'] in self.threadnamesmap: functionout = self.threadnamesmap[keys['function']]

			if 'function' in keys:
				if keys['function'] in self.threadindexes: threadout = self.threadindexes[keys['function']]
				#if keys['function'] in self.threadnamesmap: functionout = self.threadnamesmap[keys['function']]

			message = rvalue[:rvalue.find(' (')][1:-1]
			Aout = "State %s thread %s" % (stateout,self.__lastthreadID)
			Cout = '  '+message
			return Aout,"- - - - - - - - - - - - - - - - - - - - - - - - - - ",Cout

		# Extended info: branching.
		if '__cs_tmp_if_cond_' in lvalue:
			threadout = ''
			threadindexout = ''
			fileout = ''
			functionout = ''
			branch = rvalue[:rvalue.find(' (')]   # should be 'TRUE or 'FALSE'
			if 'line' in keys: lineout,fileout = self.sbizz(int(keys['line']))
			#if keys['function'] in self.threadnamesmap: functionout = self.threadnamesmap[keys['function']]
			#if functionout != '': Aout = "State %s file %s line %s function %s thread %s" % (stateout,fileout,lineout,functionout,self.__lastthreadID)
			#else:
			Aout = "State %s file %s line %s thread %s" % (stateout,fileout,lineout,self.__lastthreadID)
			Cout = '  branch %s' % (branch)

			# SV-COMP nonsense
			# nodeid,edgesource,edgetarget,threadid,startline,endline,extrakey,extravalue
			last = self.svcomplaststate
			if branch == 'TRUE':
				self.chunk(stateout,last,stateout,self.__lastthreadID,lineout,lineout,'control','condition-true')
				self.chunk(stateout+'-2',last,'INK'  ,self.__lastthreadID,lineout,lineout,'control','condition-false')
			elif branch == 'FALSE':
				self.chunk(stateout,last,stateout,self.__lastthreadID,lineout,lineout,'control','condition-false')
				self.chunk(stateout+'-2',last,'INK'  ,self.__lastthreadID,lineout,lineout,'control','condition-true')
			else:
				self.warn("unable to convert state %s" % stateout)

			self.svcomplaststate = stateout

			return Aout,"- - - - - - - - - - - - - - - - - - - - - - - - - - ",Cout

		# Extended info: branching (loop iteration).
		if '__cs_loop_' in lvalue:
			threadout = ''
			threadindexout = ''
			fileout = ''
			functionout = ''
			branch = rvalue[:rvalue.find(' (')]   # should be 'TRUE or 'FALSE'
			if 'line' in keys: lineout,fileout = self.sbizz(int(keys['line']))
			#if keys['function'] in self.threadnamesmap: functionout = self.threadnamesmap[keys['function']]
			#if functionout != '': Aout = "State %s file %s line %s function %s thread %s" % (stateout,fileout,lineout,functionout,self.__lastthreadID)
			#else:
			Aout = "State %s file %s line %s thread %s" % (stateout,fileout,lineout,self.__lastthreadID)
			Cout = '  branch branch branch branch branch branch branch branch branchbranch %s' % (branch)

			# SV-COMP nonsense
			# nodeid,edgesource,edgetarget,threadid,startline,endline,extrakey,extravalue
			last = self.svcomplaststate

			if branch == 'TRUE':
				#  (node_i_0) -> (node_i) -> node(i_2) 
				##if lineout not in self.times:
				if 1: #self.lastloophead != lineout:
					self.times[lineout] = 1
					self.lastloophead = lineout
					self.chunk(stateout+'-0',last,stateout+'-0',self.__lastthreadID,lineout,lineout,'enterLoopHead','true')

					self.chunk(stateout,stateout+'-0',stateout,self.__lastthreadID,lineout,lineout,'control','condition-true')
					self.chunk(stateout+'-2',stateout+'-0','INK',self.__lastthreadID,lineout,lineout,'control','condition-false')
				else:
					self.chunk(stateout,last,stateout,self.__lastthreadID,lineout,lineout,'control','condition-true')
					self.chunk(stateout+'-2',last,'INK'  ,self.__lastthreadID,lineout,lineout,'control','condition-false')
			elif branch == 'FALSE':
				if 1: #self.lastloophead != lineout:
					self.times[lineout] = 1
					self.lastloophead = lineout
					self.chunk(stateout+'-0',last,stateout+'-0',self.__lastthreadID,lineout,lineout,'enterLoopHead','true')

					self.chunk(stateout,stateout+'-0',stateout,self.__lastthreadID,lineout,lineout,'control','condition-false')
					self.chunk(stateout+'-2',stateout+'-0','INK',self.__lastthreadID,lineout,lineout,'control','condition-true')
				else:
					self.chunk(stateout,last,stateout,self.__lastthreadID,lineout,lineout,'control','condition-false')
					self.chunk(stateout+'-2',last,'INK'  ,self.__lastthreadID,lineout,lineout,'control','condition-true')
			else:
				self.warn("unable to convert state %s" % stateout)

			self.svcomplaststate = stateout

			return Aout,"- - - - - - - - - - - - - - - - - - - - - - - - - - ",Cout



		# State mapping for the lazy schema,
		# general case.
		fileout = functionout = ''
		lineout = 0
		# Truc -- dirty fix
		threadout = -1

		if 'line' in keys: lineout,fileout = self.sbizz(int(keys['line']))

		if 'function' in keys:
			if keys['function'] in self.threadindexes: threadout = self.threadindexes[keys['function']]
			if keys['function'] in self.threadnamesmap: functionout = self.threadnamesmap[keys['function']]

		# Truc
		# Cannot find the thread id from line map
		if threadout == -1: threadout = self.__lastthreadID

		if self.coordstofunctions is not None and (lineout,fileout) in self.coordstofunctions: functionout = self.coordstofunctions[lineout,fileout]

		fullvarname = lvalue

		if lvalue in self.varnamesmap:
			lvalue = self.varnamesmap[lvalue]

		rightvar = rvalue[:rvalue.rfind(' (')]

		if rightvar[0] != '&' and rightvar in self.varnamesmap: rvalue = rvalue.replace(rightvar,self.varnamesmap[rightvar],1)
		elif rightvar[0] == '&' and rightvar[1:] in self.varnamesmap: rvalue = '&'+rvalue.replace(rightvar,self.varnamesmap[rightvar[1:]],1)

		if not showbinaryencoding: rvalue = rvalue[:rvalue.rfind(' (')]

		if functionout != '': Aout = "State %s file %s line %s function %s thread %s" % (stateout,fileout,lineout,functionout,threadout)
		else: Aout = "State %s file %s line %s thread %s" % (stateout,fileout,lineout,threadout)

		Cout = "  %s=%s" % (lvalue,rvalue)

		# Filter out extra computations due to simulation code injected when translating.
		if lvalue.startswith('__cs_') and lvalue!= '__cs_message':
			return '','',''

		# Filter out __CPROVER internal states.
		if lineout == '?' and fileout == '?': return '','',''

		# Context switch detected!
		'''
		if self.lastlastlast != str(self.__lastthreadID):
			#self.warn("---> %s %s    (state: %s)" % (threadout, self.__lastthreadID,stateout))
			if str(self.__lastthreadID) != '0' and str(self.__lastthreadID) not in self.__startedthreadID:  # 1st statement for the thread
				self.__startedthreadID.append(str(self.__lastthreadID))
				self.lastlastlast = str(self.__lastthreadID)

				fname = self.threadindextoname[int(self.__lastthreadID)]
				self.chunk(stateout,self.svcomplaststate,stateout,self.__lastthreadID,lineout,lineout,'enterFunction',fname)
				self.svcomplaststate = stateout
			else:
				self.__startedthreadID.append(str(self.__lastthreadID))
				self.lastlastlast = str(self.__lastthreadID)

				fname = self.threadindextoname[int(self.__lastthreadID)]
				self.chunk(stateout,self.svcomplaststate,stateout,self.__lastthreadID,lineout,lineout,'enterFunction',fname)
				self.svcomplaststate = stateout
		'''

		fname = self.threadindextoname[int(self.__lastthreadID)]
		scope = ''

		if '&' not in rvalue and '{' not in rvalue:   # referencing in rvalue not accepted by witness checker
			if fullvarname.startswith('__cs_local_'):
				scope = fullvarname[len('__cs_local_'):]
				scope = scope[:-len(lvalue)-1]
				Cout = Cout.strip().replace('=','==')  + ';'
				self.chunk_doublekey(stateout,self.svcomplaststate,stateout,self.__lastthreadID,lineout,lineout,'assumption',Cout,'assumption.scope',scope)
				self.svcomplaststate = stateout
			else:  # global variable
				Cout = Cout.strip().replace('=','==') + ';'
				self.chunk(stateout,self.svcomplaststate,stateout,self.__lastthreadID,lineout,lineout,'assumption',Cout)
				self.svcomplaststate = stateout

		return (Aout,B,Cout)


	def _mapCPROVERendstate(self,A,B,C):
		mapback = {}

		'''
		'Violated property:'
		'  file _cs_lazy_unsafe.c line 318 function thread3_0'
		'  assertion 0 != 0'
		'  0 != 0'

		'''
		# Fetch values.
		try:
			# 1st line
			tokens = A.split()
			keys = {}

			for key,value in zip(tokens[0::2], tokens[1::2]):
				keys[key] = value

			line = filename = function = ''
		except Exception as e:
			self.warn('unable to parse counterexample final state')
			return ('','','')

		#if 'file' in keys: filename = keys['file']

		#if 'line' in keys and int(keys['line']) in mapback: line = mapback[int(keys['line'])]
		lineout = fileout = ''
		if 'line' in keys: lineout,fileout = self.sbizz(int(keys['line']))

		if 'function' in keys and int(keys['line']) in mapback:
			function = keys['function']

			if function in self.threadindexes: thread = self.threadindexes[function]
			if function in self.threadnamesmap: function = self.threadnamesmap[function]

			A = '  file %s line %s function %s' % (fileout,lineout,function)
		else:
			A = '  file %s line %s' % (fileout,lineout)

		self.errorpoint = lineout

		'''

		def chunk(self,nodeid,edgesource,edgetarget,threadid,startline,endline,extrakey,extravalue):
		chunk = ''\
		'<node id="Snode-id"/>\n'\
		'<edge source="edge-source" target="edge-target">\n'\
		'<data key="threadId">edge-threadid</data>\n'\
		'<data key="startline">edge-startline</data>\n'\
		'<data key="endline">edge-endline</data>\n'\
		'<data key="edge-extra-key">edge-extra-value</data></edge>\n'

		self.chunk('123',self.svcomplaststate,'STOP',)
		'''

		return (A,B,C)



	def chunk(self,nodeid,edgesource,edgetarget,threadid,startline,endline,extrakey,extravalue):
		chunk = ''\
		'<node id="Snode-id"/>\n'\
		'<edge source="Sedge-source" target="Sedge-target">\n'\
		'<data key="threadId">edge-threadid</data>\n'\
		'<data key="startline">edge-startline</data>\n'\
		'<data key="endline">edge-endline</data>\n'\
		'<data key="edge-extra-key">edge-extra-value</data></edge>\n'

		chunk = chunk.replace('node-id',str(nodeid),1)
		chunk = chunk.replace('edge-source',str(edgesource),1)
		chunk = chunk.replace('edge-target',str(edgetarget),1)
		chunk = chunk.replace('edge-threadid',str(threadid),1)
		chunk = chunk.replace('edge-startline',str(startline),1)
		chunk = chunk.replace('edge-endline',str(endline),1)
		chunk = chunk.replace('edge-extra-key',str(extrakey),1)
		chunk = chunk.replace('edge-extra-value',str(extravalue),1)

		self.svcompwitness += chunk + '\n'


	def chunk_doublekey(self,nodeid,edgesource,edgetarget,threadid,startline,endline,extrakey,extravalue,extraextrakey,extraextravalue):
		chunk = ''\
		'<node id="Snode-id"/>\n'\
		'<edge source="Sedge-source" target="Sedge-target">\n'\
		'<data key="threadId">edge-threadid</data>\n'\
		'<data key="startline">edge-startline</data>\n'\
		'<data key="endline">edge-endline</data>\n'\
		'<data key="edge-extra-key">edge-extra-value</data>\n'\
		'<data key="edge-extraextra-key">edge-extraextra-value</data></edge>\n'

		chunk = chunk.replace('node-id',str(nodeid),1)
		chunk = chunk.replace('edge-source',str(edgesource),1)
		chunk = chunk.replace('edge-target',str(edgetarget),1)
		chunk = chunk.replace('edge-threadid',str(threadid),1)
		chunk = chunk.replace('edge-startline',str(startline),1)
		chunk = chunk.replace('edge-endline',str(endline),1)
		chunk = chunk.replace('edge-extra-key',str(extrakey),1)
		chunk = chunk.replace('edge-extra-value',str(extravalue),1)
		chunk = chunk.replace('edge-extraextra-key',str(extraextrakey),1)
		chunk = chunk.replace('edge-extraextra-value',str(extraextravalue),1)

		self.svcompwitness += chunk + '\n'


	def chunks(self,file,hash,time,violationline,mainline,allchunks):
		header = ''\
		'<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'\
		'<graphml xmlns="http://graphml.graphdrawing.org/xmlns" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'\
		'\n'\
		'<key attr.name="programFile" attr.type="string" for="graph" id="programfile"/>\n'\
		'<key attr.name="programHash" attr.type="string" for="graph" id="programhash"/>\n'\
		'<key attr.name="specification" attr.type="string" for="graph" id="specification"/>\n'\
		'<key attr.name="architecture" attr.type="string" for="graph" id="architecture"/>\n'\
		'<key attr.name="producer" attr.type="string" for="graph" id="producer"/>\n'\
		'<key attr.name="creationTime" attr.type="string" for="graph" id="creationtime"/>\n'\
		'<key attr.name="inputWitnessHash" attr.type="string" for="graph" id="inputwitnesshash"/>\n'\
		'<key attr.name="witness-type" attr.type="string" for="graph" id="witness-type"/>\n'\
		'\n'\
		'<key attr.name="isViolationNode" attr.type="boolean" for="node" id="violation"><default>false</default></key>\n'\
		'<key attr.name="isEntryNode" attr.type="boolean" for="node" id="entry"><default>false</default></key>\n'\
		'<key attr.name="isSinkNode" attr.type="boolean" for="node" id="sink"><default>false</default></key>\n'\
		'<key attr.name="violatedProperty" attr.type="string" for="node" id="violatedProperty"/>\n'\
		'\n'\
		'<key attr.name="threadId" attr.type="string" for="edge" id="threadId"/>\n'\
		'<key attr.name="createThread" attr.type="string" for="edge" id="createThread"/>\n'\
		'<key attr.name="sourcecodeLanguage" attr.type="string" for="graph" id="sourcecodelang"/>\n'\
		'<key attr.name="startline" attr.type="int" for="edge" id="startline"/>\n'\
		'<key attr.name="endline" attr.type="int" for="edge" id="endline"/>\n'\
		'<key attr.name="startoffset" attr.type="int" for="edge" id="startoffset"/>\n'\
		'<key attr.name="endoffset" attr.type="int" for="edge" id="endoffset"/>\n'\
		'<key attr.name="control" attr.type="string" for="edge" id="control"/>\n'\
		'<key attr.name="enterFunction" attr.type="string" for="edge" id="enterFunction"/>\n'\
		'<key attr.name="returnFromFunction" attr.type="string" for="edge" id="returnFrom"/>\n'\
		'<key attr.name="assumption" attr.type="string" for="edge" id="assumption"/>\n'\
		'\n'\
		'<graph edgedefault="directed">\n'\
		'<data key="witness-type">violation_witness</data>\n'\
		'<data key="sourcecodelang">C</data>\n'\
		'<data key="producer">CSeq</data>\n'\
		'<data key="specification">CHECK( init(main()), LTL(G ! call(reach_error())) )</data>\n'\
		'<data key="programfile"><insert-programfile-here></data>\n'\
		'<data key="programhash"><insert-programhash-here></data>\n'\
		'<data key="creationtime"><insert-creationtime-here></data>\n'\
		'<data key="architecture">32bit</data>\n'\
		'\n'\
		'<node id="START"><data key="entry">true</data></node>\n'\
		'<node id="SINK"><data key="sink">true</data></node>\n'\
		'\n'\
		'<node id="S1"/>\n'\
		'<edge source="START" target="S1">\n'\
		'<data key="threadId">0</data>\n'\
		'<data key="startline"><insert-main-firstline></data>\n'\
		'<data key="endline"><insert-main-firstline></data>\n'\
		'<data key="enterFunction">main</data>\n'\
		'</edge>\n'\
		'\n'\
		'<insert-all-chunks-here>'\
		'<edge source="S<insert-last-state-here>" target="STOP"/>\n'\
		'<node id="STOP"><data key="violation">true</data></node>\n'\
		'</graph>\n'\
		'</graphml>\n'

		header = header.replace('<insert-programfile-here>',str(file),1)
		header = header.replace('<insert-programhash-here>',str(hash),1)
		header = header.replace('<insert-creationtime-here>',str(time),1)
		header = header.replace('<insert-violationline-here>',str(violationline),1)
		header = header.replace('<insert-main-firstline>',str(mainline[0]),2)
		header = header.replace('<insert-all-chunks-here>',str(allchunks),1)
		header = header.replace('<insert-last-state-here>',str(self.svcomplaststate),1)

		return header


	def hasloops(self):
		return (len(self.loopheads) > 0)

		
































































	def _mapCPROVERstate_loops(self,A,B,C,showbinaryencoding=False):
		Aout = Bout = Cout = ''
		keys = {}

		# Fetch values.
		try:
			# 1st line
			tokens = A.split()

			for key,value in zip(tokens[0::2],tokens[1::2]):
				keys[key] = value

			stateout = keys['State']

			# 3rd line
			line3 = C.strip()
			lvalue = line3[:line3.find('=')]
			rvalue = line3[len(lvalue)+1:]

			# double-check parsing correctness
			if 'function' in keys: Aout = "State %s file %s line %s function %s thread %s" % (keys['State'],keys['file'],keys['line'],keys['function'],keys['thread'])
			else: Aout = "State %s file %s line %s thread %s" % (keys['State'],keys['file'],keys['line'],keys['thread'])

			Cout = "  %s=%s" % (lvalue,rvalue)

			if A != Aout or C != Cout:
				self.warn('unable to parse counterexample state %s' % keys['State'])
				return ('','','')
		except Exception as e:
			self.warn('unable to parse counterexample state')
			return ('','','')

		# Special case: context switching.
		if lvalue.startswith('__cs_thread_index') and 'function' in keys and keys['function'] != '':
			threadout = rvalue[:rvalue.find(' ')]
			threadindexout = ''
			self.__lastthreadID = threadout
			if int(threadout) in self.threadindextoname: threadindexout = self.threadindextoname[int(threadout)]
			if 'line' in keys: lineout,fileout = self.sbizz(int(keys['line']))
			###Aout = "State %s <<<%s>>>" % (stateout,keys['line'])
			Aout = "State %s" % (stateout)
			Cout = "  thread %s (%s) scheduled" % (threadout,threadindexout)

			'''
			#
			tid = int(self.__lastthreadID)##self.threadreversedindexes[int(self.__lastthreadID)] if int(self.__lastthreadID) in self.threadreversedindexes else 'main'
			fname = self.threadindextoname[int(self.__lastthreadID)]
			self.chunk(stateout,self.svcomplaststate,stateout,tid                ,lineout,lineout,'enterFunction',fname)
			self.svcomplaststate = stateout
			'''

			return Aout,"- - - - - - - - - - - - - - - - - - - - - - - - - - ",Cout

		# Special case: thread creation
		if lvalue == '__cs_threadID':
			threadout = ''
			threadindexout = ''
			fileout = ''
			tid = rvalue[:rvalue.find(' (')]   # id of created thread
			if 'line' in keys: lineout,fileout = self.sbizz(int(keys['line']))
			Aout = "State %s file %s line %s thread %s" % (stateout,fileout,lineout,self.__lastthreadID)
			Cout = '  pthread_create(thread %s)' % (tid)

			# SV-COMP nonsense
			# nodeid,edgesource,edgetarget,threadid,startline,endline,extrakey,extravalue
			self.chunk(stateout,self.svcomplaststate,stateout,self.__lastthreadID,lineout,lineout,'createThread',tid)
			self.svcomplaststate = stateout
			newstateout = str(stateout)+'-2'
			##self.chunk(newstateout,self.svcomplaststate,newstateout,self.__lastthreadID                ,lineout,lineout,'enterFunction',self.threadindextoname[int(tid)])
			self.chunk(newstateout,self.svcomplaststate,newstateout,tid                ,lineout,lineout,'enterFunction',self.threadindextoname[int(tid)])
			self.svcomplaststate = newstateout

			return Aout,"- - - - - - - - - - - - - - - - - - - - - - - - - - ",Cout


		# Special case: thread exit (i.e., last statement executed)
		if lvalue.startswith('__cs_pc[') and str(self.__lastthreadID) != '0': # and rvalue == self.threadsizes[self.__lastthreadID]:
			#self.log("---- - - - - - - - - - >>>>> <last:%s> " % (self.__lastthreadID))
			#self.log("---- - - - - - - - - - >>>>> <last:%s> " % self.threadindextoname[int(self.__lastthreadID)]   )

			#self.log("namesmap %s" % self.threadnamesmap)
			#self.log("indexes %s" % self.threadindexes)
			#self.log("reversedindexes %s" % self.threadreversedindexes)
			#self.log("sizes %s" % self.threadsizes)
			#self.log("endlines %s" % self.threadendlines)
			#self.log("indextoname %s" % self.threadindextoname)

			# Thread termination detection:
			# if the updated program counter for the simulated thread is exactly its size,
			# then the thread must have terminated.
			size = rvalue[:rvalue.find(' (')]   
			check = self.threadsizes[self.threadreversedindexes[int(self.__lastthreadID)]]

			if str(size) == str(check) and int(self.__lastthreadID) not in self.__terminatedthreadID:
				#int(self.__lastthreadID) in self.__terminatedthreadID
				self.__terminatedthreadID.append(int(self.__lastthreadID))

				#########self.log("terminatedid %s" % self.__terminatedthreadID)

				fileout = ''
				lineout = self.threadendlines[self.threadreversedindexes[int(self.__lastthreadID)]]
				Aout = "State %s file %s line %s thread %s" % (stateout,fileout,lineout,self.__lastthreadID)
				Cout = '  pthread_exit(thread %s)' % (self.__lastthreadID)
				
				tid = self.threadnamesmap[self.threadreversedindexes[int(self.__lastthreadID)]]
				self.chunk(stateout,self.svcomplaststate,stateout,self.__lastthreadID,lineout,lineout,'returnFrom',tid)
				self.svcomplaststate = stateout

				return Aout,"- - - - - - - - - - - - - - - - - - - - - - - - - - ",Cout

		# Special case: cond signal
		if lvalue == '__cs_cond_to_signal':
			threadout = ''
			threadindexout = ''
			fileout = ''
			if 'line' in keys: lineout,fileout = self.sbizz(int(keys['line']))
			Aout = "State %s file %s line %s thread %s" % (stateout,fileout,lineout,self.__lastthreadID)
			Cout = '  pthread_cond_signal(%s)' % (rvalue[:rvalue.find(' (')])
			return Aout,"- - - - - - - - - - - - - - - - - - - - - - - - - - ",Cout

		# Special case: cond wait
		if lvalue == '__cs_cond_to_wait_for':
			threadout = ''
			threadindexout = ''
			fileout = ''
			if 'line' in keys: lineout,fileout = self.sbizz(int(keys['line']))
			Aout = "State %s file %s line %s thread %s" % (stateout,fileout,lineout,self.__lastthreadID)
			Cout = '  pthread_cond_wait(%s,?)' % (rvalue[:rvalue.find(' (')])
			return Aout,"- - - - - - - - - - - - - - - - - - - - - - - - - - ",Cout

		# Special case: mutexes lock and unlock
		if lvalue == '__cs_mutex_to_lock' and 'function' in keys and not keys['function']=='pthread_cond_wait_2':
			threadout = ''
			threadindexout = ''
			fileout = ''
			if 'line' in keys: lineout,fileout = self.sbizz(int(keys['line']))
			Aout = "State %s file %s line %s thread %s" % (stateout,fileout,lineout,self.__lastthreadID)
			Cout = '  pthread_mutex_lock(%s)' % (rvalue[:rvalue.find(' (')])
			return Aout,"- - - - - - - - - - - - - - - - - - - - - - - - - - ",Cout

		if lvalue == '__cs_mutex_to_unlock' and 'function' in keys and not keys['function']=='pthread_cond_wait_1' :
			threadout = ''
			threadindexout = ''
			fileout = ''
			if 'line' in keys: lineout,fileout = self.sbizz(int(keys['line']))

			Aout = "State %s file %s line %s thread %s" % (stateout,fileout,lineout,self.__lastthreadID)
			Cout = '  pthread_mutex_unlock(%s)' % (rvalue[:rvalue.find(' (')])
			return Aout,"- - - - - - - - - - - - - - - - - - - - - - - - - - ",Cout

		# Special case: mutexes destroy
		if lvalue == '__cs_mutex_to_destroy':
			threadout = ''
			threadindexout = ''
			fileout = ''
			if 'line' in keys: lineout,fileout = self.sbizz(int(keys['line']))
			Aout = "State %s file %s line %s thread %s" % (stateout,fileout,lineout,self.__lastthreadID)
			Cout = '  pthread_mutex_destroy(%s)' % (rvalue[:rvalue.find(' (')])
			return Aout,"- - - - - - - - - - - - - - - - - - - - - - - - - - ",Cout

		# Special case: explicit __CSEQ_message().
		if lvalue== '__cs_message':
			threadout = ''
			threadindexout = ''

			if 'line' in keys: lineout,fileout = self.sbizz(int(keys['line']))

			if 'function' in keys:
				#if keys['function'] in self.threadindexes: threadout = self.threadindexes[keys['function']]
				if keys['function'] in self.threadnamesmap: functionout = self.threadnamesmap[keys['function']]

			if 'function' in keys:
				if keys['function'] in self.threadindexes: threadout = self.threadindexes[keys['function']]
				#if keys['function'] in self.threadnamesmap: functionout = self.threadnamesmap[keys['function']]

			message = rvalue[:rvalue.find(' (')][1:-1]
			Aout = "State %s thread %s" % (stateout,self.__lastthreadID)
			Cout = '  '+message
			return Aout,"- - - - - - - - - - - - - - - - - - - - - - - - - - ",Cout

		# Extended info: branching.
		if '__cs_tmp_if_cond_' in lvalue:
			threadout = ''
			threadindexout = ''
			fileout = ''
			functionout = ''
			branch = rvalue[:rvalue.find(' (')]   # should be 'TRUE or 'FALSE'
			if 'line' in keys: lineout,fileout = self.sbizz(int(keys['line']))
			#if keys['function'] in self.threadnamesmap: functionout = self.threadnamesmap[keys['function']]
			#if functionout != '': Aout = "State %s file %s line %s function %s thread %s" % (stateout,fileout,lineout,functionout,self.__lastthreadID)
			#else:
			Aout = "State %s file %s line %s thread %s" % (stateout,fileout,lineout,self.__lastthreadID)
			Cout = '  branch %s' % (branch)

			# SV-COMP nonsense
			# nodeid,edgesource,edgetarget,threadid,startline,endline,extrakey,extravalue
			last = self.svcomplaststate
			if branch == 'TRUE':
				self.chunk(stateout,last,stateout,self.__lastthreadID,lineout,lineout,'control','condition-true')
				self.chunk(stateout+'-2',last,'INK'  ,self.__lastthreadID,lineout,lineout,'control','condition-false')
			elif branch == 'FALSE':                
				self.chunk(stateout,last,stateout,self.__lastthreadID,lineout,lineout,'control','condition-false')
				self.chunk(stateout+'-2',last,'INK'  ,self.__lastthreadID,lineout,lineout,'control','condition-true')
			else:
				self.warn("unable to convert state %s" % stateout)

			self.svcomplaststate = stateout

			return Aout,"- - - - - - - - - - - - - - - - - - - - - - - - - - ",Cout

		# Extended info: branching (loop iteration).
		'''
		if '__cs_loop_' in lvalue:
			threadout = ''
			threadindexout = ''
			fileout = ''
			functionout = ''
			branch = rvalue[:rvalue.find(' (')]   # should be 'TRUE or 'FALSE'
			if 'line' in keys: lineout,fileout = self.sbizz(int(keys['line']))
			#if keys['function'] in self.threadnamesmap: functionout = self.threadnamesmap[keys['function']]
			#if functionout != '': Aout = "State %s file %s line %s function %s thread %s" % (stateout,fileout,lineout,functionout,self.__lastthreadID)
			#else:
			Aout = "State %s file %s line %s thread %s" % (stateout,fileout,lineout,self.__lastthreadID)
			Cout = '  branch branch branch branch branch branch branch branch branchbranch %s' % (branch)

			# SV-COMP nonsense
			# nodeid,edgesource,edgetarget,threadid,startline,endline,extrakey,extravalue
			last = self.svcomplaststate

			if branch == 'TRUE':
				#  (node_i_0) -> (node_i) -> node(i_2) 
				##if lineout not in self.times:
				if 1: #self.lastloophead != lineout:
					self.times[lineout] = 1
					self.lastloophead = lineout
					self.chunk(stateout+'-0',last,stateout+'-0',self.__lastthreadID,lineout,lineout,'enterLoopHead','true')

					self.chunk(stateout,stateout+'-0',stateout,self.__lastthreadID,lineout,lineout,'control','condition-true')
					self.chunk(stateout+'-2',stateout+'-0','INK',self.__lastthreadID,lineout,lineout,'control','condition-false')
				else:
					self.chunk(stateout,last,stateout,self.__lastthreadID,lineout,lineout,'control','condition-true')
					self.chunk(stateout+'-2',last,'INK'  ,self.__lastthreadID,lineout,lineout,'control','condition-false')
			elif branch == 'FALSE':
				if 1: #self.lastloophead != lineout:
					self.times[lineout] = 1
					self.lastloophead = lineout
					self.chunk(stateout+'-0',last,stateout+'-0',self.__lastthreadID,lineout,lineout,'enterLoopHead','true')

					self.chunk(stateout,stateout+'-0',stateout,self.__lastthreadID,lineout,lineout,'control','condition-false')
					self.chunk(stateout+'-2',stateout+'-0','INK',self.__lastthreadID,lineout,lineout,'control','condition-true')
				else:
					self.chunk(stateout,last,stateout,self.__lastthreadID,lineout,lineout,'control','condition-false')
					self.chunk(stateout+'-2',last,'INK'  ,self.__lastthreadID,lineout,lineout,'control','condition-true')
			else:
				self.warn("unable to convert state %s" % stateout)

			self.svcomplaststate = stateout

			return Aout,"- - - - - - - - - - - - - - - - - - - - - - - - - - ",Cout
		'''


		# State mapping for the lazy schema,
		# general case.
		fileout = functionout = ''
		lineout = 0
		# Truc -- dirty fix
		threadout = -1

		if 'line' in keys: lineout,fileout = self.sbizz(int(keys['line']))

		if 'function' in keys:
			if keys['function'] in self.threadindexes: threadout = self.threadindexes[keys['function']]
			if keys['function'] in self.threadnamesmap: functionout = self.threadnamesmap[keys['function']]

		# Truc
		# Cannot find the thread id from line map
		if threadout == -1: threadout = self.__lastthreadID

		if self.coordstofunctions is not None and (lineout,fileout) in self.coordstofunctions: functionout = self.coordstofunctions[lineout,fileout]

		fullvarname = lvalue

		if lvalue in self.varnamesmap:
			lvalue = self.varnamesmap[lvalue]

		rightvar = rvalue[:rvalue.rfind(' (')]

		if rightvar[0] != '&' and rightvar in self.varnamesmap: rvalue = rvalue.replace(rightvar,self.varnamesmap[rightvar],1)
		elif rightvar[0] == '&' and rightvar[1:] in self.varnamesmap: rvalue = '&'+rvalue.replace(rightvar,self.varnamesmap[rightvar[1:]],1)

		if not showbinaryencoding: rvalue = rvalue[:rvalue.rfind(' (')]

		if functionout != '': Aout = "State %s file %s line %s function %s thread %s" % (stateout,fileout,lineout,functionout,threadout)
		else: Aout = "State %s file %s line %s thread %s" % (stateout,fileout,lineout,threadout)

		Cout = "  %s=%s" % (lvalue,rvalue)





		fname = self.threadindextoname[int(self.__lastthreadID)]
		scope = ''

		if '__cs_enter_' in lvalue:#         and 1 in rvalue:
			self.warn("---> entering function %s" % lvalue[lvalue.rfind('_'):])
		elif lvalue.startswith('__cs_enter_') and 1 in rvalue:
			self.warn("---> exiting function %s" % lvalue[lvalue.rfind('_'):])





		# Filter out extra computations due to simulation code injected when translating.
		if lvalue.startswith('__cs_') and lvalue!= '__cs_message':
			return '','',''

		# Filter out __CPROVER internal states.
		if lineout == '?' and fileout == '?': return '','',''

		# Context switch detected!
		'''
		if self.lastlastlast != str(self.__lastthreadID):
			#self.warn("---> %s %s    (state: %s)" % (threadout, self.__lastthreadID,stateout))
			if str(self.__lastthreadID) != '0' and str(self.__lastthreadID) not in self.__startedthreadID:  # 1st statement for the thread
				self.__startedthreadID.append(str(self.__lastthreadID))
				self.lastlastlast = str(self.__lastthreadID)

				fname = self.threadindextoname[int(self.__lastthreadID)]
				self.chunk(stateout,self.svcomplaststate,stateout,self.__lastthreadID,lineout,lineout,'enterFunction',fname)
				self.svcomplaststate = stateout
			else:
				self.__startedthreadID.append(str(self.__lastthreadID))
				self.lastlastlast = str(self.__lastthreadID)

				fname = self.threadindextoname[int(self.__lastthreadID)]
				self.chunk(stateout,self.svcomplaststate,stateout,self.__lastthreadID,lineout,lineout,'enterFunction',fname)
				self.svcomplaststate = stateout
		'''



		'''
		fname = self.threadindextoname[int(self.__lastthreadID)]
		scope = ''


		if '&' not in rvalue and '{' not in rvalue:   # referencing in rvalue not accepted by witness checker
			if fullvarname.startswith('__cs_local_'):
				scope = fullvarname[len('__cs_local_'):]
				scope = scope[:-len(lvalue)-1]
				Cout = Cout.strip().replace('=','==')  + ';'
				self.chunk_doublekey(stateout,self.svcomplaststate,stateout,self.__lastthreadID,lineout,lineout,'assumption',Cout,'assumption.scope',scope)
				self.svcomplaststate = stateout
			else:  # global variable
				Cout = Cout.strip().replace('=','==') + ';'
				self.chunk(stateout,self.svcomplaststate,stateout,self.__lastthreadID,lineout,lineout,'assumption',Cout)
				self.svcomplaststate = stateout
		'''


		return (Aout,B,Cout)































