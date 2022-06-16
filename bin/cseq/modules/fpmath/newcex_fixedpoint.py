""" CSeq C Sequentialization Framework
	counterexample translation module (variable-precision fixed-point bitvectors)

	written by Omar Inverso.
"""
VERSION = 'cex-fixedpoint-2017.03.02'
#VERSION = 'cex-fixedpoint-2016.12.17'
#VERSION = 'cex-fixedpoint-2016.08.30'
#VERSION = 'cex-2015.07.16'
#VERSION = 'cex-2015.07.14'
#VERSION = 'cex-2015.07.07'
"""
(based on Lazy-CSeq's counter-example translation module, see notes below)
The counterexample generation implemented in this module
is specific for the Lazy schema (lazyseq.py) but most of it should in principle work
for any translation where the relationship betweeen the input of the first module and the output of the last module
is a points-to-set function, or equivalently,
the linemap from the output of the last module to the input of the first module
is a surjective (and therefore invertible) function.

TODO:
    - re-implement some of the checks to simplify the counterexample (see TODOs in the code)

	- fixed-point format binary representation to be extended to arrays and matrices

	- should parse structured (XML) output instead, really
	 (at least for CBMC and the other backends that provide it)

Changelog:
	2021.02.05  no longer using Parser.varNames (old symbol table)
	2020.07.14  cbmc-ext support
	2020.05.27  inherited from [ICCPS2017] [iFM?]
	2015.07.16  improved cbmc error trace readability by showing more simulated pthread states (Omar,Truc)
	2015.07.15  fixed line mapping for mutex destroy (Truc)
	2015.07.07  1st version
"""
import pycparser.c_parser, pycparser.c_ast, pycparser.c_generator
import core.module, core.parser, core.utils
import sys
import time

# Expressions to check for from the log to see whether the verification went fine.
verificationOK = {}
verificationOK['esbmc'] = 'VERIFICATION SUCCESSFUL'
verificationOK['cbmc'] = 'VERIFICATION SUCCESSFUL'
verificationOK['cbmc-ext'] = 'VERIFICATION SUCCESSFUL'
verificationOK['blitz'] = 'VERIFICATION SUCCESSFUL'
verificationOK['llbmc'] = 'No error detected.'
verificationOK['cpachecker'] = 'Verification result: TRUE.'
verificationOK['smack'] = 'Finished with 1 verified, 0 errors'
verificationOK['satabs'] = 'VERIFICATION SUCCESSFUL'
verificationOK['klee'] = 'DKJFHSDKJDFHSJKF' # no such thing for Klee?

# Expressions to check for from the log to see whether the verification failed.
verificationFAIL = {}
verificationFAIL['esbmc'] = 'VERIFICATION FAILED'
verificationFAIL['cbmc'] = 'VERIFICATION FAILED'
verificationFAIL['cbmc-ext'] = 'VERIFICATION FAILED'
verificationFAIL['blitz'] = 'VERIFICATION FAILED'
verificationFAIL['llbmc'] = 'Error detected.'
verificationFAIL['cpachecker'] = 'Verification result: FALSE.' #verificationFAIL['smack'] = 'Error BP5001: This assertion might not hold.\n'
verificationFAIL['smack'] = 'Finished with 0 verified,'
verificationFAIL['satabs'] = 'VERIFICATION FAILED'
verificationFAIL['klee'] = 'ASSERTION FAIL: '

# Backend reject/error.
backendERROR = {}
backendERROR['cbmc'] = 'CONVERSION ERROR'
backendERROR['cbmc-ext'] = 'CONVERSION ERROR'

class newcex_fixedpoint(core.module.BasicModule):
	_statecnt = 0

	debug = True
	extendedcex = False

	def init(self):
		self.inputparam('backend', 'backend', 'b', default='cbmc', optional=False)
		self.inputparam('linemap', 'show linemap', '', default=False, optional=True)
		self.inputparam('cex', 'show counterexample (CBMC only)', '', default=False, optional=True)
		self.inputparam('cexx', 'show extended counterexample (CBMC only)', '', default=False, optional=True)
		self.inputparam('errorp1', 'error precision integer part', 'i', default='8', optional=False)
		self.inputparam('errorp2', 'error precision fractional part', 'f', default='8', optional=False)
		self.inputparam('exitcode', 'backend exit-code', '', default=0, optional=True)
		#self.inputparam('threadnamesmap', 'map from thread copies to thread function', '', default=None, optional=True)
		#self.inputparam('threadindexes', 'map from thread copies to thread indexes', '', default=None, optional=True)
		#self.inputparam('threadindextoname', 'map from thread index to thread function name', '', default=None, optional=True)
		self.inputparam('varnamesmap', 'map for replaced variable names', '', default=None, optional=True)
		#self.inputparam('coordstofunctions', 'map from input coords to function ids', '', default=None, optional=True)

		self.inputparam('precision', 'precisions for each fixed-point variable', '', default=None, optional=False)
		#self.inputparam('sign', '...', '', default=None, optional=False)


	def loadfromstring(self, string, env):
		self.env = env

		self.precision = self.getinputparam('precision')
		self.sign = self.getinputparam('sign')
		self.backend = self.getinputparam('backend')
		self.code = self.getinputparam('exitcode')
		self.threadnamesmap = self.getinputparam('threadnamesmap')
		self.threadindexes = self.getinputparam('threadindexes')
		self.threadindextoname = self.getinputparam('threadindextoname')
		self.varnamesmap = self.getinputparam('varnamesmap')
		self.coordstofunctions = self.getinputparam('coordstofunctions')
		self.outputtofiles = self.env.outputtofiles
		self.error_i = int(self.getinputparam('errorp1'))
		self.error_f = int(self.getinputparam('errorp2'))

		if self.getinputparam('cex') is None and self.getinputparam('cexx') is None:
			self.output = self._shortanswer(string)
		else:
			if self.getinputparam('cexx') is not None:
				self.extendedcex = True
			self.output = self._translateCPROVERcex(string)
			self.output += self._shortanswer(string)


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
			if verificationFAIL[self.backend] in line:
				outcome = 'FAIL'
				break
			elif verificationOK[self.backend] in line:
				outcome = 'PASS'
				break
			elif self.backend == 'cbmc' and self.code == 6:
				outcome = 'BACKENDREJECT'
			elif self.backend == 'cbmc-ext' and self.code == 6:
				outcome = 'BACKENDREJECT'

		if outcome == '' and self.code == -9: outcome = 'TIMEOUT' # backend timeout
		elif outcome == '': outcome = 'UNKNOWN'

		#
		if outcome == 'UNKNOWN': result = core.utils.colors.YELLOW + outcome + core.utils.colors.NO
		elif outcome == 'BACKENDREJECT': result = core.utils.colors.BLUE + outcome + core.utils.colors.NO
		elif outcome == 'TIMEOUT': result = core.utils.colors.YELLOW + outcome + core.utils.colors.NO
		elif outcome == 'PASS': result = core.utils.colors.GREEN + outcome + core.utils.colors.NO
		elif outcome == 'FAIL': result = core.utils.colors.RED + outcome + core.utils.colors.NO

		h=''
		for o,a in self.env.opts:
			if a=='': h+='%s ' % (o)
			else: h+='%s %s ' % (o,a)

		h = h[:-1] + ', '

		#return "%s, %s%s, %0.2f" % (self.env.inputfile,h,result,time.time()-self.env.starttime)
		return "%s %s%s, %0.2fs" % (self.env.cmdline[0],h,result,time.time()-self.env.starttime)


	''' Full CPROVER-style counterexample translation.
	'''
	def _translateCPROVERcex(self,cex):
		if self.backend != 'cbmc' and self.backend != 'cbmc-ext':
			self.warn('error trace translation for backend %s not supported.' % self.backend)
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

				X,Y,Z = self._mapCPROVERstate(A,B,C)

				if X != '':
					translatedcex += '%s\n' % X
					if Y != '': translatedcex += '%s\n' % Y
					if Z != '': translatedcex += '%s\n' % Z
					########translatedcex += '\n'
			# case 2: final transation with property violation
			elif lines[k].startswith('Violated property'):
				Y,Z,W = self._mapCPROVERendstate(lines[k+1],lines[k+2],lines[k+3])

				translatedcex += 'Violated property:\n%s\n%s\n%s\n' % (Y,Z,W)
				translatedcex += '\nVERIFICATION FAILED'

			k+=1

		if len(translatedcex) > 0:
			translatedcex = "Counterexample:\n\n" + translatedcex + '\n\n'

		return translatedcex


	def _mapCPROVERstate(self,A,B,C,showbinaryencoding=False):
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

			# Avoid translating transitions related to function or variable identifiers
			# that do not belong to the initial program:
			#
			# 1. skip transitions related to functions that do not belong to the initial program..
			if (not self.extendedcex and 'function' in keys and keys['function'] and
				keys['function'] not in self.env.modules[0].Parser.funcName):
				#self.warn('(A) skipping counterexample state %s, function %s' % (keys['State'], keys['function']))
				#self.warn(A)
				#self.warn(B)
				#self.warn(C)
				#self.warn('\n\n')
				return ('','','')

			# 2. skip variables that do not belong to the initial program
			# TODO re-implement the commented checks below using the new symbol table
			if (not self.extendedcex and '[' not in lvalue and 'function' in keys and keys['function'] and
				######lvalue not in self.env.modules[0].Parser.varNames[keys['function']] and
				######lvalue not in self.env.modules[0].Parser.varNames[''] and
				not lvalue.endswith('__e')):
				#self.warn('(B) skipping counterexample state %s, lvalue %s' % (keys['State'], lvalue))
				return ('','','')

			# 3. skip error variables related to step 2
			# TODO re-implement the commented checks below using the new symbol table
			if (not self.extendedcex and 'function' in keys and keys['function'] and
				######lvalue[:-1] not in self.env.modules[0].Parser.varNames[keys['function']] and
				######lvalue[:-1] not in self.env.modules[0].Parser.varNames[''] and
				lvalue.endswith('__e')):
				#self.warn('(C) skipping counterexample state %s, lvalue %s' % (keys['State'], lvalue))
				return ('','','')

			# double-check parsing correctness
			if 'function' in keys: Aout = "State %s file %s line %s function %s thread %s" % (keys['State'],keys['file'],keys['line'],keys['function'],keys['thread'])
			else: Aout = "State %s file %s line %s thread %s" % (keys['State'],keys['file'],keys['line'],keys['thread'])

			Cout = "  %s=%s" % (lvalue,rvalue)

			if A != Aout or C != Cout:
				self.warn('unable to parse counterexample state %s' % keys['State'])
				return ('','','')
		except Exception as e:
			self.warn('unable to parse counterexample state %s' % keys['State'])
			###print "ERROR:%s" % (str(e))
			return (A,B,C+'\n')

		# State mapping adapted from the lazy schema, general case.
		fileout = functionout = ''
		lineout = threadout = 0

		if 'line' in keys: lineout,fileout = self.sbizz(int(keys['line']))

		if self.coordstofunctions is not None and (lineout,fileout) in self.coordstofunctions: functionout = self.coordstofunctions[lineout,fileout]

		if self.varnamesmap and lvalue in self.varnamesmap: lvalue = self.varnamesmap[lvalue]

		rightvar = rvalue[:rvalue.rfind(' (')]

		if self.varnamesmap and rightvar[0] != '&' and rightvar in self.varnamesmap: rvalue = rvalue.replace(rightvar,self.varnamesmap[rightvar],1)
		elif self.varnamesmap and rightvar[0] == '&' and rightvar[1:] in self.varnamesmap: rvalue = '&'+rvalue.replace(rightvar,self.varnamesmap[rightvar[1:]],1)

		if not showbinaryencoding: rvalue = rvalue[:rvalue.rfind(' (')]

		if functionout != '': Aout = "State %s file %s line %s function %s thread %s" % (stateout,fileout,lineout,functionout,threadout)
		else: Aout = "State %s file %s line %s thread %s" % (stateout,fileout,lineout,threadout)

		Cout = C

		# Annotate states related to assignments to fixed-point variables (incl. error variables)
		# with the corresponding binary and integer representations.
		#
		# So for example the assignment:
		#
		#      x__8_2__=508 (0111111100)
		#
		# is changed to:
		#
		#      x__8_2__=508 (0111111100) (01111111.00) (127.0)
		#
		# the same also applies when the variable name is either errorL, errorR, ...
		# ...
		try:
			fname = '' if 'function' not in keys else keys['function']

			binary = Cout[Cout.find('(')+1:Cout.find(')')]  # terrible I know ..TODO

			#print "AAAAA %s" % lvalue

			if '[' in lvalue and (lvalue[:lvalue.find('[')].endswith('__') or lvalue[:lvalue.find('[')].endswith('__e')) and not '{' in rvalue:
				####scope = fname if (fname,lvalue[:lvalue.find('[')]) in self.precision else ''
				scope = '0.0'  # assume we are in a simple program for now
				(precision1,precision2) = self.precision[scope,lvalue[:lvalue.find('[')]]
				#print "AAAAA A -> %s %s" %  (precision1,precision2)
				sign = 1 #self.sign[scope,lvalue[:lvalue.find('[')]]
				fixedpoint = self.binary2fixedpoint(binary,sign,precision1,precision2)
				Cout += ' <%s>' % fixedpoint
			elif (lvalue.endswith('__') or lvalue.endswith('__e')) and not '{' in rvalue:
				####scope = fname if (fname,lvalue) in self.precision else ''
				scope = '0.0'  # assume we are in a simple program for now
				(precision1,precision2) = self.precision[scope,lvalue]
				#print "AAAAA B -> %s %s" %  (precision1,precision2)
				sign = 1 #self.sign[scope,lvalue]
				fixedpoint = self.binary2fixedpoint(binary,sign,precision1,precision2)
				Cout += ' <%s>' % fixedpoint
			elif lvalue in ('__cs_errorL','__cs_errorR','__cs_lasterror','__cs_lasterrorabs'):
				(precision1,precision2) = (self.error_i,self.error_f)
				#print "AAAAA C -> %s %s" %  (precision1,precision2)
				sign = 1
				fixedpoint = self.binary2fixedpoint(binary,sign,precision1,precision2)
				Cout += ' <%s>' % fixedpoint
		except Exception as e:
			self.warn('unable to parse counterexample state %s (fixed-point assignment)' % keys['State'])
			self.warn('error ->' + str(e))
			return (A,B,C+'\n')

		# Filter out extra computations due to simulation code
		# injected at the moment of the translation
		# (excluding transitions that show error propagation)
		if (lvalue.startswith('__cs_') and lvalue!= '__cs_message' and
			lvalue not in ('__cs_errorL','__cs_errorR','__cs_lasterror','__cs_lasterrorabs')):
			return '','',''

		# Filter out __CPROVER internal states.
		#####if lineout == '?' and fileout == '?': return '','',''

		self._statecnt+=1
		return ('[%s] '%self._statecnt+Aout,B,Cout+'\n') #return (A,B,Cout)


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

		return (A,B,C)


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
	def parse_bin(self,s):
		t = s.split('.')
		#print "INPUT: %s" % s
		#print "output: %s" % str(int(t[0],2) + int(t[1],2) / 2.**len(t[1]))
		#print "output: %s" % t
		return int(t[0],2) + int(t[1],2) / 2.**len(t[1])


	''' Convert from a raw bitstring to a fixed-point number in the given precision.
	'''
	def binary2fixedpoint(self,binary,sign,precision1,precision2):
		#print "converting %s %s %s %s" % (binary,sign,precision1,precision2)

		precision1 = int(precision1)+1
		precision2 = int(precision2)
		minus = ''

		if sign and binary[0]=='1':  # two's complement
			l = len(binary)
			binary = int(binary,2)-1
			fmt = '0>'+str(l)+'b'
			binary = format(binary,fmt)
			binary = binary.replace('0','2').replace('1','0').replace('2','1')
			minus = '-'
		elif sign: minus = '+'

		if precision1>0:
			integerpart = binary[-precision1-precision2:-precision2]
		else:
			integerpart = ''

		if precision2>0:
			fractionalpart = binary[-precision2:]
		else:
			fractionalpart = ''

		boh = self.parse_bin(integerpart+'.'+fractionalpart)

		return minus+'('+str(integerpart)+'.'+str(fractionalpart)+') ' +minus+'('+str(boh)+')'



