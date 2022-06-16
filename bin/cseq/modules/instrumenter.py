""" CSeq Program Analysis Framework
    instrumentation module

Transformation 1 (convert function calls and add implementation):
	__CSEQ_assert()   -->   verifier-specific assert
	__CSEQ_assume()   -->   verifier-specific assume

Transformation 2 (convert bitvectors)
	convert any  int  or  unsigned int  for which there is
	__CSEQ_bitvector[k] --> ...

Transformation 3 (raw line injections and indentation):
	__CSEQ_rawline("string"); --> string

	this transformation uses
	separate indentation for raw and non-raw lines, where
	a raw line is a line inserted by __CSEQ_rawline()
	any other line is non-raw.
	Raw line are indentend fully left,
	non-raw are shifted to the right.

Author:
	Omar Inverso

Changes:
    2021.10.20  obsolete options removed
    2021.02.12  special treatment for empty structures no longer required
	2020.11.11  default initialisation for pthread_xyz_t to - 1 (necessary especially for mutexes) [SV-COMP 2021]
    2020.03.24 (CSeq 2.0)
    2020.03.24  header now reports module version from the changelog
	2020.03.23  default backend cbmc-ext (first used in PPoPP 2020 paper)
    2019.11.24 [SV-COMP 2020]
	2019.11.24  bugfix: now expanding typemaps[] with both c_ast.IdentifierType and c_ast.Typename
	2019.11.20  empty structures workaround for pycparser/pycparserext
    2019.11.15 (CSeq 1.9) pycparserext
	2019.11.15  limited pthread_xyz mapping as much as possible (and only for pthread types now)
	2019.04.12  disabling module hash for now
	2018.11.25  removing definitions for functions thar (statically detected) are never invoked
	2018.11.24  disabling assumptions on well-nestedness of locks when the program uses no locks
	2018.11.22  module option to assume locks are well-nested (replaces specific --svcomp option)
	2018.10.27  disabled automated typedef redeclaration of __cs_t, __cs_mutex_t, and __cs_cond_t
	            from int to bitvectors
	           (because on pthread-complex/bounded-buffer it breaks CBMC --32 up to version 5.10)
	2018.10.27  added extra input parameter for system headers extracted at merge-time
	2017.05.16  changed the header
	2016.12.06  add fix to type not integer (long)
	2016.12.02  add round integer types options
	2016.11.30  add svcomp option (disable assertions in lock/unlock)
	2016.11.29  disable hashed file number
	2016.09.26  add option to get more (system) headers
	2016.09.14  add more entry to nondet, and extra header to CBMC
	2016.08.15  set bits for structure and array
	2016.08.09  add backend Frama-C
	2015.07.15  back to output.strip to remove fake header content

To do:
  - urgent: remove concurrency-specific parts
  - general overhaul for custom-bitwidth transformations
  - header: add hash values for frontend (cseq.py)
  - header: show version numbers for every module in the chain
  - header: show actual parameters (e.g. unwind=3) for every input parameter of every module
  - handle typedefs

"""
from time import gmtime, strftime, localtime
import math, re
import core.utils
import pycparser.c_ast

_backends = ['cbmc', 'cbmc-ext', 'cbmc-svcomp2020', 'esbmc', 'llbmc', 'blitz', 'satabs', '2ls', 'klee', 'cpachecker', 'smack', 'ultimate', 'symbiotic']

fmap = {}

fmap['cbmc', '__VERIFIER_assume'] = '__CPROVER_assume'
fmap['cbmc', '__VERIFIER_assertext'] = '__CPROVER_assert'
fmap['cbmc', '__VERIFIER_assert'] = 'assert'
fmap['cbmc', '__VERIFIER_nondet_int'] = 'nondet_int'
fmap['cbmc', '__VERIFIER_nondet_uint'] = 'nondet_uint'
fmap['cbmc', '__VERIFIER_nondet_bool'] = 'nondet_bool'
fmap['cbmc', '__VERIFIER_nondet_char'] = 'nondet_char'
fmap['cbmc', '__VERIFIER_nondet_uchar'] = 'nondet_uchar'

fmap['cbmc-ext', '__VERIFIER_assume'] = '__CPROVER_assume'
fmap['cbmc-ext', '__VERIFIER_assertext'] = '__CPROVER_assert'
fmap['cbmc-ext', '__VERIFIER_assert'] = 'assert'
fmap['cbmc-ext', '__VERIFIER_nondet_int'] = 'nondet_int'
fmap['cbmc-ext', '__VERIFIER_nondet_uint'] = 'nondet_uint'
fmap['cbmc-ext', '__VERIFIER_nondet_bool'] = 'nondet_bool'
fmap['cbmc-ext', '__VERIFIER_nondet_char'] = 'nondet_char'
fmap['cbmc-ext', '__VERIFIER_nondet_uchar'] = 'nondet_uchar'

fmap['cbmc-svcomp2020', '__VERIFIER_assume'] = '__CPROVER_assume'
fmap['cbmc-svcomp2020', '__VERIFIER_assertext'] = '__CPROVER_assert'
fmap['cbmc-svcomp2020', '__VERIFIER_assert'] = 'assert'
fmap['cbmc-svcomp2020', '__VERIFIER_nondet_int'] = 'nondet_int'
fmap['cbmc-svcomp2020', '__VERIFIER_nondet_uint'] = 'nondet_uint'
fmap['cbmc-svcomp2020', '__VERIFIER_nondet_bool'] = 'nondet_bool'
fmap['cbmc-svcomp2020', '__VERIFIER_nondet_char'] = 'nondet_char'
fmap['cbmc-svcomp2020', '__VERIFIER_nondet_uchar'] = 'nondet_uchar'

fmap['esbmc', '__VERIFIER_assume'] = '__ESBMC_assume'
fmap['esbmc', '__VERIFIER_assertext'] = '__ESBMC_assert'
fmap['esbmc', '__VERIFIER_assert'] = 'assert'
fmap['esbmc', '__VERIFIER_nondet_int'] = '__VERIFIER_nondet_int'
fmap['esbmc', '__VERIFIER_nondet_uint'] = '__VERIFIER_nondet_uint'
fmap['esbmc', '__VERIFIER_nondet_bool'] = '__VERIFIER_nondet_bool'
fmap['esbmc', '__VERIFIER_nondet_char'] = '__VERIFIER_nondet_char'
fmap['esbmc', '__VERIFIER_nondet_uchar'] = '__VERIFIER_nondet_uchar'

fmap['llbmc', '__VERIFIER_assume'] = '__llbmc_assume'
fmap['llbmc', '__VERIFIER_assertext'] = '__llbmc_assert'
fmap['llbmc', '__VERIFIER_assert'] = '__llbmc_assert'
fmap['llbmc', '__VERIFIER_nondet_int'] = 'nondet_int'
fmap['llbmc', '__VERIFIER_nondet_uint'] = 'nondet_int'
fmap['llbmc', '__VERIFIER_nondet_bool'] = 'nondet_bool'
fmap['llbmc', '__VERIFIER_nondet_char'] = 'nondet_char'
fmap['llbmc', '__VERIFIER_nondet_uchar'] = 'nondet_uchar'

fmap['blitz', '__VERIFIER_assume'] = '__CPROVER_assume'
fmap['blitz', '__VERIFIER_assertext'] = 'assert'
fmap['blitz', '__VERIFIER_assert'] = 'assert'
fmap['blitz', '__VERIFIER_nondet_int'] = 'nondet_int'
fmap['blitz', '__VERIFIER_nondet_uint'] = 'nondet_uint'
fmap['blitz', '__VERIFIER_nondet_bool'] = 'nondet_bool'
fmap['blitz', '__VERIFIER_nondet_char'] = 'nondet_char'
fmap['blitz', '__VERIFIER_nondet_uchar'] = 'nondet_uchar'

fmap['satabs', '__VERIFIER_assume'] = '__CPROVER_assume'
fmap['satabs', '__VERIFIER_assertext'] = 'assert'
fmap['satabs', '__VERIFIER_assert'] = 'assert'
fmap['satabs', '__VERIFIER_nondet_int'] = 'nondet_int'
fmap['satabs', '__VERIFIER_nondet_uint'] = 'nondet_uint'
fmap['satabs', '__VERIFIER_nondet_bool'] = 'nondet_bool'
fmap['satabs', '__VERIFIER_nondet_char'] = 'nondet_char'
fmap['satabs', '__VERIFIER_nondet_uchar'] = 'nondet_uchar'

fmap['klee', '__VERIFIER_assume'] = 'KLEE_assume'
fmap['klee', '__VERIFIER_assertext'] = 'KLEE_assert'
fmap['klee', '__VERIFIER_assert'] = 'KLEE_assert'
fmap['klee', '__VERIFIER_nondet_int'] = 'KLEE_nondet_int'
fmap['klee', '__VERIFIER_nondet_uint'] = 'KLEE_nondet_uint'
fmap['klee', '__VERIFIER_nondet_bool'] = 'KLEE_nondet_bool'
fmap['klee', '__VERIFIER_nondet_char'] = 'KLEE_nondet_char'
fmap['klee', '__VERIFIER_nondet_uchar'] = 'KLEE_nondet_uchar'

fmap['cpachecker', '__VERIFIER_assume'] = '__VERIFIER_assume'
fmap['cpachecker', '__VERIFIER_assertext'] = '__VERIFIER_assert'
fmap['cpachecker', '__VERIFIER_assert'] = '__VERIFIER_assert'
fmap['cpachecker', '__VERIFIER_nondet_int'] = '__VERIFIER_nondet_int'
fmap['cpachecker', '__VERIFIER_nondet_uint'] = '__VERIFIER_nondet_uint'
fmap['cpachecker', '__VERIFIER_nondet_bool'] = '__VERIFIER_nondet_bool'
fmap['cpachecker', '__VERIFIER_nondet_char'] = '__VERIFIER_nondet_char'
fmap['cpachecker', '__VERIFIER_nondet_uchar'] = '__VERIFIER_nondet_uchar'

fmap['smack', '__VERIFIER_assume'] = '__VERIFIER_assume'
fmap['smack', '__VERIFIER_assertext'] = 'assert'
fmap['smack', '__VERIFIER_assert'] = 'assert'
fmap['smack', '__VERIFIER_nondet_int'] = '__VERIFIER_nondet_int'
fmap['smack', '__VERIFIER_nondet_uint'] = '__VERIFIER_nondet_uint'
fmap['smack', '__VERIFIER_nondet_bool'] = '__VERIFIER_nondet_bool'
fmap['smack', '__VERIFIER_nondet_char'] = '__VERIFIER_nondet_char'
fmap['smack', '__VERIFIER_nondet_uchar'] = '__VERIFIER_nondet_uchar'

fmap['ultimate', '__VERIFIER_assume'] = '__VERIFIER_assume'
fmap['ultimate', '__VERIFIER_assertext'] = '__VERIFIER_assert'
fmap['ultimate', '__VERIFIER_assert'] = '__VERIFIER_assert'
fmap['ultimate', '__VERIFIER_nondet_int'] = '__VERIFIER_nondet_int'
fmap['ultimate', '__VERIFIER_nondet_uint'] = '__VERIFIER_nondet_uint'
fmap['ultimate', '__VERIFIER_nondet_bool'] = '__VERIFIER_nondet_bool'
fmap['ultimate', '__VERIFIER_nondet_char'] = '__VERIFIER_nondet_char'
fmap['ultimate', '__VERIFIER_nondet_uchar'] = '__VERIFIER_nondet_uchar'

fmap['symbiotic', '__VERIFIER_assume'] = '__VERIFIER_assume'
fmap['symbiotic', '__VERIFIER_assertext'] = '__VERIFIER_assert'
fmap['symbiotic', '__VERIFIER_assert'] = '__VERIFIER_assert'
fmap['symbiotic', '__VERIFIER_nondet_int'] = '__VERIFIER_nondet_int'
fmap['symbiotic', '__VERIFIER_nondet_uint'] = '__VERIFIER_nondet_uint'
fmap['symbiotic', '__VERIFIER_nondet_bool'] = '__VERIFIER_nondet_bool'
fmap['symbiotic', '__VERIFIER_nondet_char'] = '__VERIFIER_nondet_char'
fmap['symbiotic', '__VERIFIER_nondet_uchar'] = '__VERIFIER_nondet_uchar'


_maxrightindent = 25   # max columns right for non-raw lines
_rawlinemarker = '__CSEQ_removeindent'


# Map thread-specific types (e.g., pthread_mutex_t -> cspthread_mutex_t)
# to avoid parsing clashes.
#
typemap = {}
typemap['pthread_barrier_t'] = 'cspthread_barrier_t'
typemap['pthread_cond_t'] = 'cspthread_cond_t'
typemap['pthread_mutex_t'] = 'cspthread_mutex_t'
typemap['pthread_t'] = 'cspthread_t'
typemap['pthread_key_t'] = 'cspthread_key_t'
typemap['pthread_mutexattr_t'] = 'cspthread_mutexattr_t'
typemap['pthread_condattr_t'] = 'cspthread_condattr_t'
typemap['pthread_barrierattr_t'] = 'cspthread_barrierattr_t'


class instrumenter(core.module.Translator):
	__visitingstruct = False
	__structstack = []			   # stack of struct name
	__avoid_type = []
	#emptystructs = []


	def init(self):
		self.inputparam('backend','backend to use for analysis, available choices are:\nbounded model-checkers: (Blitz, CBMC, CBMC-EXT, ESBMC, LLBMC)\nabstraction-based: (CPAchecker, SATABS, Frama-C)\nsymbolic execution: (KLEE)','b','CBMC-EXT',False)
		self.inputparam('bitwidth','custom bidwidths for integers','w',None,True)
		self.inputparam('header', 'raw text file to add on top of the instrumented file', 'h', '', True)
		#self.inputparam('emptystructs', '...', '', '', optional=True)


	def loadfromstring(self,string,env):
		self.env = env

		self.backend = self.getinputparam('backend').lower()
		self.bitwidths = self.getinputparam('bitwidth')
		self.extheader = self.getinputparam('header')
		self.systemheaders = self.getinputparam('systemheaders')
		#self.emptystructs = self.getinputparam('emptystructs')

		self.__intervals = env.intervals if hasattr(env, 'intervals') else {}

		if self.backend not in _backends:
			raise core.module.ModuleError("backend '%s' not supported" % self.backend)

		#self.__avoid_type = [core.common.changeID[x] for x in core.common.changeID]
		self.__avoid_type = [typemap[x] for x in typemap]

		super(self.__class__,self).loadfromstring(string,env)
		self.lastoutputlineno = 0
		self.removelinenumbers()
		# self.output = core.utils.strip(self.output)
		# self.inputtooutput = {}
		# self.outputtoinput = {}
		# self.generatelinenumbers()


		# Transformation 3:
		# shift indentation of raw lines fully left
		# removing the trailing marker _rawlinemarker+semicolon, and
		# shift any other line to the right depending to the longest rawline, and
		# in any case no longer than _maxrightindent.
		maxlinemarkerlen = max(len(l) for l in self.output.splitlines()) - len(_rawlinemarker+';')-2
		maxlinemarkerlen = min(maxlinemarkerlen,_maxrightindent)

		newstring = ''

		for l in self.output.splitlines():
			if l.endswith(_rawlinemarker+';'):
				newstring += l[:-len(_rawlinemarker+';')].lstrip() + '\n'
			else:
				newstring += ' '*(maxlinemarkerlen)+l+'\n'

		self.output = newstring

		self.insertheader(self.extheader)		  # header passed by previous module

		if self.backend == 'klee': self.insertheader(core.utils.printFile('modules/klee_extra.c'))
		if self.backend == 'cpachecker': self.insertheader(core.utils.printFile('modules/cpa_extra.c'))
		if self.backend == 'cbmc': self.insertheader(core.utils.printFile('modules/cbmc_extra.c'))
		if self.backend == 'cbmc-ext': self.insertheader(core.utils.printFile('modules/cbmc_extra.c'))
		if self.backend == 'cbmc-sv-comp-2020': self.insertheader(core.utils.printFile('modules/cbmc_extra.c'))
		if self.backend == 'smack': self.insertheader("#include <smack.h>\n")

		if self.backend == 'ultimate':
			self.output = self.output.replace('<insert-or-here>', ' || ')
		else:
			self.output = self.output.replace('<insert-or-here>', ' | ')

		# Insert external 'system' header if there are (from the file)
		#if hasattr(self.env, "\"):
		#	self.insertheader(getattr(self.env, "systemheaders"))
		##self.systemheaders += '#include <pthread.h>'
		#self.systemheaders = '//#include <stdio.h>\n'
		self.insertheader(self.systemheaders)
		self.insertheader(core.utils.printFile('modules/pthread_defs.c'))
		self.insertheader(self._generateheader())  # top comment with translation parameters


	def visit(self,n):
		out = super(self.__class__,self).visit(n)

		if isinstance(n,pycparser.c_ast.IdentifierType) or isinstance(n,pycparser.c_ast.Typename):
			if out in typemap: out = typemap[out]

		return out


	def visit_Decl(self,n,no_type=False):
		# Map pthread-specific types.
		#
		#print("declaration [%s] fspec:[%s] nstor:[%s] type:[%s]" % (s,(' '.join(n.funcspec) + ' '),(' '.join(n.storage) + ' '), self._generate_type(n.type)))
		#print("stack: %s\n" % (self.stack))
		checkforinit = False

		if type(n.type) == pycparser.c_ast.TypeDecl:
			if type(n.type.type) == pycparser.c_ast.IdentifierType:
				if n.type.type.names[0] in typemap:
					#print("type:[%s] typedecl:[%s]" % (self.visit(n.type.type),n.type.type.names[0]))
					n.type.type.names[0] = typemap[n.type.type.names[0]]
					#self.warn("---> [%s]." % (n.type.type.names[0]))
					if n.init:
						checkforinit = True
						#self.warn("---> [%s]" % (self.visit(n.init)))

		# no_type is used when a Decl is part of a DeclList, where the type is
		# explicitly only for the first delaration in a list.
		#
		s = n.name if no_type else self._generate_decl(n)

		if n.name == '__VERIFIER_assert' and self.backend == 'smack':
			s2 = s.replace('__VERIFIER_assert','__renamed__VERIFIER_assert',1)
			#print("REPLACING %s->%s" % (s,s2))
			s = s2


		# In case  x  has a custom bitwidth (passed by a previous module), convert
		# 'int x'  to  'bitvectors[k] x' or
		# 'unsigned int x'  to  'unsigned bitvectors[k] x'.
		ninitextra = ''
		prefix = ''

		if self.backend in ('cbmc','cbmc-ext'):
			if s.startswith('static '):
				s = s[7:]	# remove static
				prefix = 'static '

			if s.startswith("_Bool "):
				pass
			elif self.bitwidths is not None:
				if self.__visitingstruct and len(self.__structstack) > 0:
					if (self.__structstack[-1], n.name) in self.bitwidths:
						if s.startswith("unsigned int "):
							s = s.replace("unsigned int ","unsigned __CPROVER_bitvector[%s] " % self.bitwidths[self.__structstack[-1],n.name],1)
						elif s.startswith("int "):
							s = s.replace("int ","__CPROVER_bitvector[%s] " % self.bitwidths[self.__structstack[-1],n.name],1)
						else:
							temp = s.split()   # split the declaration
							for i, item in enumerate(temp):
								if item.lstrip('*') == n.name and i > 0 and temp[i-1] not in self.__avoid_type and temp[i-1] in ('long', 'short', 'char',):   # temp[i-1] is the type
									temp[i-1] = '__CPROVER_bitvector[%s]' % self.bitwidths[self.__structstack[-1],n.name]
									break
							s = " ".join(temp)
				else:
					currentFunct = self.currentFunct if self.currentFunct != 'main_thread' else 'main'
					if s.startswith("unsigned int ") and (currentFunct,n.name) in self.bitwidths:
						s = s.replace("unsigned int ","unsigned __CPROVER_bitvector[%s] " % self.bitwidths[currentFunct,n.name],1)
						ninitextra = '(unsigned __CPROVER_bitvector[%s])' % self.bitwidths[currentFunct,n.name]
					elif s.startswith("int ") and (currentFunct, n.name) in self.bitwidths:
						numbit = self.bitwidths[currentFunct, n.name]
						s = s.replace("int ","C __CPROVER_bitvector[%s] " % numbit,1)
						ninitextra = '(__CPROVER_bitvector[%s])' % numbit
					elif (currentFunct, n.name) in self.bitwidths:
						numbit = self.bitwidths[currentFunct, n.name]
						temp = s.split()
						for i, item in enumerate(temp):
							if item.lstrip('*') == n.name and i > 0 and temp[i-1] not in self.__avoid_type and temp[i-1] in ('long', 'short', 'char',):
								temp[i-1] = '__CPROVER_bitvector[%s]' % numbit
								break
						s = " ".join(temp)
			if prefix != '':
				s = prefix + s

		# Experimental: ESBMC with bitvectors
		if self.backend in ('esbmc'):
			currentFunct = self.currentFunct if self.currentFunct != 'main_thread' else 'main'

			if currentFunct == 'main':
				if n.name:
					if n.name.startswith('__cs_tmp_t'):
						#print ("---> %s <---" % n.name)
						norobin = True if self.getinputparam('norobin') is not None else False

						if not norobin:
							s = s.replace("unsigned int ","unsigned _ExtInt(%s) " % self.bitwidths[self.currentFunct,n.name],1)

		if n.bitsize: s += ' : ' + self.visit(n.bitsize)

		pthread_init_dict = {
			#'pthread_mutex_t' : 'PTHREAD_MUTEX_INITIALIZER',
			#'pthread_cond_t'  : 'PTHREAD_COND_INITIALIZER',
			#'pthread_rwlock_t' : 'PTHREAD_RWLOCK_INITIALIZER'
			'pthread_mutex_t' : '0',
			'pthread_cond_t'  : '0',
			'pthread_rwlock_t' : '0'
		}

		# Default initialisation for pthread_xyz types
		if n.init:
			if isinstance(n.init, pycparser.c_ast.InitList):
				if checkforinit:
					s += ' = -1' # e.g., pthread_mutex_t t = .... -> cspthread_mutex_t t = -1;
				else:
					s += ' = {' + self.visit(n.init) + '}'

			elif isinstance(n.init, pycparser.c_ast.ExprList):
				s += ' = (' + self.visit(n.init) + ')'
			else:
				s += ' = ' + ninitextra + '(' + self.visit(n.init) + ')'

		return s


	def _generate_struct_union(self, n, name):
		""" Generates code for structs and unions. name should be either
			'struct' or union.
		"""
		s = name + ' ' + (n.name or '')
		# There should be no anonymous struct, handling in workarounds module
		self.__visitingstruct = True
		if n.name:
			self.__structstack.append(n.name)
		if n.decls:
			s += '\n'
			s += self._make_indent()
			self.indent_level += 2
			s += '{\n'
			for decl in n.decls:
				s += self._generate_stmt(decl)
			self.indent_level -= 2
			s += self._make_indent() + '}'
		self.__visitingstruct = False
		if n.name:
			self.__structstack.pop()
		return s


	'''
	def visit_Struct(self, n):
		out = super(self.__class__, self).visit_Struct(n)

		# empty structure has no fields
		if n.decls is None and self.stack[-2] == 'Decl' and self.stack[-3] != 'Struct' and n.name in self.emptystructs:
			out += '{ char dummy; }'
			self.emptystructs.remove(n.name)

		return out
	'''


	def visit_Typedef(self, n):
		s = ''
		if n.storage: s += ' '.join(n.storage) + ' '
		s += self._generate_type(n.type)

		return s


	''' converts function calls '''
	def visit_FuncCall(self,n):
		fref = self._parenthesize_unless_simple(n.name)

		if fref == 'pthread_create': fref = 'pthread_create_2'

		# Transformation 3.
		if fref == '__CSEQ_rawline':
			return self.visit(n.args)[1:-1]+_rawlinemarker

		args = self.visit(n.args)

		if (fref == '__VERIFIER_assertext' and self.backend not in ('cbmc','cbmc-ext','esbmc')):
			args = self.visit(n.args.exprs[0])   # Only get the first expression

		if (self.backend, fref) in fmap:
			fref = fmap[self.backend, fref]

		return fref + '(' + args + ')'


	def _generateheader(self):
		masterhash_framework = '0000'
		masterhash_modulechain = '0000'

		h  = '/***\n'
		h += ' ***  generated by CSeq [ %s / %s ] %s\n' % (masterhash_framework,masterhash_modulechain,strftime("%Y-%m-%d %H:%M:%S",localtime()))
		h += ' ***\n'

		# details of each core/ component
		for i,filename in enumerate(sorted(core.utils.listfiles('core','*.py'))):
			file = core.utils.printFile(filename)
			lines = file.splitlines()
			maxlines = len(lines)

			for j,l in enumerate(lines):
				if l.startswith('Changes:'):
					date = core.utils.validatedate(lines[j+1].split()[0],'%Y.%m.%d')
					if date.startswith(' '):
						self.warn('unable to extract date from changelog in module %s' % filename)

					h += ' ***                      %s %s %s\n' % (core.utils.shortfilehash(filename),date,filename[:-3])

		# details for each module in the chain
		h += ' ***\n'
		h += ' ***  params:\n'
		h += ' ***    ' +' '.join(opt[0]+' '+opt[1] for opt in self.env.opts) + '\n'
		h += ' ***\n'
		h += ' ***  modules:\n'

		for m in self.env.modules:
			params = '(' + ' '.join(p.id for p in m.inputparamdefs) + ')'
			hash = core.utils.shortfilehash('modules/%s.py' % m.name())
			h += ' ***    %s %s%s %s\n' %(hash,m.name(),'',params) # m.VERSION

		h += ' ***\n'
		h += ' ***/\n'

		return h

