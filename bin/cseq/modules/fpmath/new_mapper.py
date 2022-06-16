""" CSeq Program Analysis Framework
    mapper module

Maps from variables in the program to variables in the DIMACS formula by CBMC.
Can be used to steer the SAT solver with specific assumptions on some variables,
for instance.

Author:
    Omar Inverso

Changes:
	2020.07.18  fixed possible race condition during parallel analysis
    2020.03.24 (CSeq 2.0)
    2020.03.23  added to (round-bounded) lazy configuration [SV-COMP 2020]
    2018.05.24  [PPoPP 2020]
    2018.04.21  forked from latest stable feeder module
    2015.07.16  CSeq 1.0 [ASE 2015]

Notes:
  - currently only works for sequentialised programs with cba scheduler
  - CBMC-EXT is recommended (extended symbol map at the end of the DIMACS)
  - with very simple programs that trivially verify safe, the DIMACS is not generated

To do:
  - generalise the search to any variable
  - generalise to arbitary program structures (requires static analisys)
  - save to disk the full DIMACS and only load in the memory the map (as some instances are huge)
  - bugfix: no need to generate the DIMACS when --contexts 1
  - add explicit timeout parameter (now hardcoded) for generating the propositional formula
  - when the backend is not available, there should be an exception.

"""
import getopt, math, os, sys, shlex, signal, subprocess, time
import pycparser.c_parser, pycparser.c_ast, pycparser.c_generator
import core.module, core.parser, core.utils

command = {}
options = {}

command['cbmc-ext'] = 'backends/cbmc-ext'
options['cbmc-ext'] = '';


class new_mapper(core.module.BasicModule):
	def init(self):
		self.inputparam('backend', 'backend', 'b', default='cbmc', optional=False)
		#######self.inputparam('contexts', 'execution contexts', 'r', None, False)
		self.inputparam('contexts', 'execution contexts (replaces --rounds)', 'c', None, optional=True)
		self.inputparam('unwind', 'loop unwind bound', 'u', '1', False)
		##### #### ##### self.inputparam('assume', 'analyse under assumptions', 'a', default='',optional=True)
		#self.inputparam('time', 'analysis time limit (in seconds)', 't', '3600000', False)
		#self.inputparam('savemap', 'save map ', '', default=False, optional=True)
		self.inputparam('cores', 'cores for parallel analysis (0 = auto)', 'c', '1', False)
		#self.inputparam('physical-cores', 'number of physical cores for parallel analysis (default = same as --cores)', 'p', default=0, optional=True)
		self.inputparam('no-simplify', 'no propositional simplification in the backend', '', default=False, optional=True)
		self.inputparam('reuse-dimacs', 're-use existing DIMACS formula for symbol lookup', '', default=False, optional=True)
		self.outputparam('extrargs')

		self.inputparam('split-var', 'non-deterministic variable for propositinal search space splitting', 'v', '', False)
		self.inputparam('split-offset', 'non-deterministic variable offsets (=bits) for splitting (e.g., 0,4,8)', 'o', '', False)
		#self.inputparam('split-value', 'splitting values to force for propositional variables (e.g., 0,1,0)', 'v', '', False)


	def loadfromstring(self, string, env):
		extrargs = []
		cmdline = ''

		contexts = int(self.getinputparam('contexts')) if self.getinputparam('contexts') is not None else 0
		cores = int(self.getinputparam('cores'))
		backend = self.getinputparam('backend').lower()
		unwind =  int(self.getinputparam('unwind'))
		nodimacs = True	if self.getinputparam('reuse-dimacs') is not None else False
		splitvar = self.getinputparam('split-var')
		splitoffset = self.getinputparam('split-offset').split(',')

		#splitvalue = self.getinputparam('split-value').split(',')
		#if len(splitoffset) != len(splitvalue):
		#	self.error('argument length mismatch for propositional splitting (%s offsets vs %s split values)' % (len(splitoffset),len(splitvalue)))

		#print("--> [%s] [%s] <--" % (splitoffset,splitvalue))

		log = int(math.log(float(cores),2.0))

		'''
		if contexts == 0:
			self.debug("mapping only required for parallel context-bounded analysis, skipping")
			self.output = string
			return
		'''

		if cores <= 1:
			self.debug("mapping only required for parallel context-bounded analysis, skipping")
			self.output = string
			return

		if backend != "cbmc-ext":
			self.warn("backend [%s] not supported, please use [cbmc-ext]" % backend)
			self.output = string
			return

		# Save the _cs_ file and the DIMACS for it, if needed.
		seqfile = core.utils.filepathprefix(env.inputfile,'_cs_')
		seqfile = seqfile[:-2] + '.c' if seqfile.endswith('.i') else seqfile
		core.utils.saveFile(seqfile,string)
		outfile = '%s.u%sc%s.dimacs' % (seqfile,unwind,contexts)

		if nodimacs: self.log("reusing DIMACS file [%s]" % outfile)
		else:
			#cmdline = command[backend] + " " + seqfile + " --dimacs | grep \"c \""    #--outfile " + seqfile+".dimacs"
			cmdline = command[backend] + " " + seqfile + " --dimacs --outfile " + outfile
			self.debug("generating DIMACS instance: %s" % cmdline)
			p = core.utils.Command(cmdline)
			out,err,code,memsize = p.run(timeout=int(36000))   # store stdout, stderr, process' return value

		dimacs = core.utils.printFile(outfile)

		if dimacs is None:
			self.error('unable to open DIMACS file (%s)' % outfile)
			#print("NOT NONE nonetype:%s" % isinstance(dimacs, type(None)))

		####function = 'main'
		####variable = '__cs_out_0_1'
		####key = 'c %s::1::%s!0@1#1 ' %(function,variable)
		dimacs = dimacs.splitlines()

		'''
		key = 'c main::1::__cs_out_0_1!0@1#1 '
		firstvar = lastvar = 0
		lines = dimacs.splitlines()

		if len(lines) == 1:
			self.error('no map generated due to program trivially verified safe')

		for line in lines:
			if line.startswith(key):
				line = line[len(key):]
				firstvar = int(line[:line.find(' ')])   # least significant digit
				lastvar = int(line[line.rfind(' '):])   # most significant digit

		if firstvar == 0:
			#self.warn('unable to find map entry for the given variable')
			self.error('unable to find map entry for the given variable')

		#print "[[[%s..%s]]]" %(firstvar, lastvar)
		#print "CONTEXTS: %s" % contexts
		#print "boh: %s" %(sizeofoneelement)

		#
		sizeofoneelement = (lastvar-firstvar+1)/(contexts+1)

		'''

		varset = []

		#tid_key = 'c main::1::__cs_tid!0@1#1 '  # DIMACS line prefix  for __cs_tid in the C program
		#cs_key = 'c main::1::__cs_cs!0@1#1 '    # DIMACS line prefix for __cs_cs in the C program
		key = 'c main::1::%s!0@1#1 ' % splitvar

		#tid_bitwidth = self.findpropositionalvar_bitwidth(dimacs,tid_key)/contexts
		#cs_bitwidth = self.findpropositionalvar_bitwidth(dimacs,cs_key)/contexts

		baseindex = self.findpropositionalvar(dimacs,key)
		self.log("key:[%s] baseindex:[%s] " % (key,baseindex))

		if (baseindex == 0):
			self.error('splitting variable:[%s] key:[%s] not found' % (splitvar,key))

		tid_bitwidth = self.findpropositionalvar_bitwidth(dimacs,key)
		self.log("key:[%s] bitwidth:[%s] " % (key,tid_bitwidth))

		for i in range(0,len(splitoffset)):
			#print("---> %s=%s " % (splitoffset[i],splitvalue[i]))
			varset.append(baseindex+int(splitoffset[i]))


		#tid_bitwidth = self.findpropositionalvar_bitwidth(dimacs,'c main::1::bnondet__3_4__!0@1#1 ')
		#print("---> %s " % test)

		# split on least significant digits of the symbolic variables
		# representing the context-switch points, i.e.,
		# lsd(_cs_tid[0]), lsd(_cs_tid[1]), ...
		#if cores >= 2: varset.append(self.findpropositionalvar(dimacs,tid_key,1*tid_bitwidth))
		#if cores >= 4: varset.append(self.findpropositionalvar(dimacs,tid_key,2*tid_bitwidth))
		#if cores >= 8: varset.append(self.findpropositionalvar(dimacs,tid_key,3*tid_bitwidth))
		#if cores >= 16: varset.append(self.findpropositionalvar(dimacs,tid_key,4*tid_bitwidth))
		#if cores >= 32: varset.append(self.findpropositionalvar(dimacs,tid_key,5*tid_bitwidth))
		#if cores >= 64: varset.append(self.findpropositionalvar(dimacs,tid_key,6*tid_bitwidth))
		#if cores >= 128: varset.append(self.findpropositionalvar(dimacs,tid_key,7*tid_bitwidth))
		#if cores >= 256: varset.append(self.findpropositionalvar(dimacs,tid_key,8*tid_bitwidth))
		#if cores >= 512: varset.append(self.findpropositionalvar(dimacs,tid_key,9*tid_bitwidth))
		#if cores >= 1024: varset.append(self.findpropositionalvar(dimacs,tid_key,10*tid_bitwidth))

		'''
		if cores >= 2: varset.append(self.findpropositionalvar(dimacs,cs_key,1*cs_bitwidth))
		if cores >= 4: varset.append(self.findpropositionalvar(dimacs,cs_key,2*cs_bitwidth))
		if cores >= 8: varset.append(self.findpropositionalvar(dimacs,cs_key,3*cs_bitwidth))
		if cores >= 16: varset.append(self.findpropositionalvar(dimacs,cs_key,4*cs_bitwidth))
		'''

		'''
		if cores >= 2: varset.append(self.findpropositionalvar(dimacs,tid_key,1*tid_bitwidth))
		if cores >= 4: varset.append(self.findpropositionalvar(dimacs,cs_key,1*cs_bitwidth))
		if cores >= 8: varset.append(self.findpropositionalvar(dimacs,tid_key,2*tid_bitwidth))
		if cores >= 16: varset.append(self.findpropositionalvar(dimacs,cs_key,2*cs_bitwidth))
		'''

		'''
		if cores >= 2: varset.append(self.findpropositionalvar(dimacs,cs_key,1*cs_bitwidth))
		if cores >= 4: varset.append(self.findpropositionalvar(dimacs,tid_key,1*tid_bitwidth))
		if cores >= 8: varset.append(self.findpropositionalvar(dimacs,cs_key,2*cs_bitwidth))
		if cores >= 16: varset.append(self.findpropositionalvar(dimacs,tid_key,2*tid_bitwidth))
		'''

		'''
		if cores >= 2: varset.append(self.findpropositionalvar(dimacs,tid_key,1*tid_bitwidth))
		if cores >= 4: varset.append(self.findpropositionalvar(dimacs,cs_key,2*cs_bitwidth))
		if cores >= 8: varset.append(self.findpropositionalvar(dimacs,cs_key,1*cs_bitwidth))
		if cores >= 16: varset.append(self.findpropositionalvar(dimacs,tid_key,2*tid_bitwidth))
		'''

		if cores > 1:
			binary = lambda x,n: format(x,'b').zfill(n)

			for k in range(0,cores):
				extrarg = " --assume "
				boh = '%s' % binary(k,log)
				i = 0

				for v in varset:
					a = 0 if boh[i]=='0' else 1
					b = ',' if i<len(varset)-1 else ''
					extrarg += "%s=%s%s" %(v,a,b)
					i+=1

				extrargs.append(extrarg)

		#if 'warning' in err: self.warn('warnings on stderr from the backend')

		self.setoutputparam('extrargs', extrargs)  # to parallel feeder
		self.output = string


	''' Find the propositional variable that encodes in the DIMACS
	    the least significant digit of the program variable
	    associated with the given key.
	'''
	def findpropositionalvar(self,dimacs,key,offset=0):
		# Scan the (comments in the) DIMACS encoding to
		# extract the identifiers of the propositional variables for the
		# given local variable of the given function.
		#
		# Example key: 'c main::1::__cs_out_0_1!0@1#1 '.
		firstvar = lastvar = 0

		if len(dimacs) == 1:
			self.warn('no map generated due to program trivially verified safe')

		for line in dimacs:
			if line.startswith(key):
				line = line[len(key):]
				firstvar = int(line[:line.find(' ')])   # least significant digit
				lastvar = int(line[line.rfind(' '):])   # most significant digit

		if int(firstvar)+int(offset) <= int(lastvar):
			return int(firstvar)+int(offset)
		else:
			return None


	# TODO: error check, e.g. when var = 401 402 F F F F this fails.
	def findpropositionalvar_bitwidth(self,dimacs,key):
		firstvar = lastvar = 0

		if len(dimacs) == 1:
			self.warn('no map generated due to program trivially verified safe')

		for line in dimacs:
			if line.startswith(key):
				line = line[len(key):]
				firstvar = int(line[:line.find(' ')])   # least significant digit
				lastvar = int(line[line.rfind(' '):])   # most significant digit

		return int(lastvar)-int(firstvar)+1


