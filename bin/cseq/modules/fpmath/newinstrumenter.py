""" CSeq backend instrumentation module
	written by Omar Inverso
"""
VERSION = 'instrumenter-0.0-2019.09.28'
#VERSION = 'instrumenter-0.0-2017.05.16' # ICCPS2018?
#VERSION = 'instrumenter-0.0-2016.12.13'
#VERSION = 'instrumenter-0.0-2016.09.06'
#VERSION = 'instrumenter-0.0-2015.07.15'
## VERSION = 'instrumenter-0.0-2015.07.09'
###VERSION = 'instrumenter-0.0-2015.06.25'
"""
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

	Transformation 4:
		inserts an additional header (passed as input parameter from previous module(s)) at the top
		of the input (linemap preserved) before preprocessing.
		the header can be an empty string, or any parsable code snippet, including macros and the like.

Changelog:
	2021.02.02  bitvector support for ESBMC
	2020.07.14  support for CBMC-EXT [IFM 2020]
	2020.06.21  adding +1 bit when converting from fixed-point to bitvector
	2020.06.21  added more explicit casts when promoting to larger bitwidth (mul,div,sum,sub)
	2020.05.28  added explicit casts when promoting to larger bitwidth (left shift case)
	2020.05.27  do not add explicit casts within an assignment statement when downcasting (CBMC-only?)
	2020.05.27  adapted from [ICCPS2017]
	2019.09.28  now introducing an explicit cast at the right hand side of any assignment statement to a custom-length bitvector (CBMC-only, improves ICCPS2018)
	2017.05.16  changed the header
	2016.12.13  replaced gmtime() with localtime() to timestamp header
	2016.10.19  signed/unsigned fixed-point types (__cs_fixedpoint, __cs_ufixedpoint)
	2016.09.06  bugfixes
	2015.07.15  back to output.strip to remove fake header content

"""
from time import strftime, localtime
import math, re
import core.module, core.utils
import pycparser.c_ast

_backends = ['cbmc', 'cbmc-ext', 'esbmc', 'llbmc', 'blitz', 'satabs', '2ls', 'klee', 'cpachecker']

fmap = {}

fmap['cbmc', '__CSEQ_assume'] = '__CPROVER_assume'
fmap['cbmc', '__CSEQ_assertext'] = '__CPROVER_assert'
fmap['cbmc', '__CSEQ_assert'] = 'assert'
fmap['cbmc', '__CSEQ_nondet_int'] = 'nondet_int'
fmap['cbmc', '__CSEQ_nondet_uint'] = 'nondet_uint'

fmap['cbmc-ext', '__CSEQ_assume'] = '__CPROVER_assume'
fmap['cbmc-ext', '__CSEQ_assertext'] = '__CPROVER_assert'
fmap['cbmc-ext', '__CSEQ_assert'] = 'assert'
fmap['cbmc-ext', '__CSEQ_nondet_int'] = 'nondet_int'
fmap['cbmc-ext', '__CSEQ_nondet_uint'] = 'nondet_uint'

fmap['esbmc', '__CSEQ_assume'] = '__ESBMC_assume'
fmap['esbmc', '__CPROVER_assume'] = '__ESBMC_assume'
fmap['esbmc', '__CSEQ_assertext'] = '__ESBMC_assert'
fmap['esbmc', '__CSEQ_assert'] = 'assert'
fmap['esbmc', '__CSEQ_nondet_int'] = '__VERIFIER_nondet_int'
fmap['esbmc', '__CSEQ_nondet_uint'] = '__VERIFIER_nondet_uint'

fmap['llbmc', '__CSEQ_assume'] = '__llbmc_assume'
fmap['llbmc', '__CSEQ_assertext'] = '__llbmc_assert'
fmap['llbmc', '__CSEQ_assert'] = '__llbmc_assert'
fmap['llbmc', '__CSEQ_nondet_int'] = 'nondet_int'
fmap['llbmc', '__CSEQ_nondet_uint'] = 'nondet_int'

fmap['blitz', '__CSEQ_assume'] = '__CPROVER_assume'
fmap['blitz', '__CSEQ_assertext'] = 'assert'
fmap['blitz', '__CSEQ_assert'] = 'assert'
fmap['blitz', '__CSEQ_nondet_int'] = 'nondet_int'
fmap['blitz', '__CSEQ_nondet_uint'] = 'nondet_uint'

fmap['satabs', '__CSEQ_assume'] = '__CPROVER_assume'
fmap['satabs', '__CSEQ_assertext'] = 'assert'
fmap['satabs', '__CSEQ_assert'] = 'assert'
fmap['satabs', '__CSEQ_nondet_int'] = 'nondet_int'
fmap['satabs', '__CSEQ_nondet_uint'] = 'nondet_uint'

# fmap['2ls', '__CSEQ_assume'] = '__CPROVER_assume'
# fmap['2ls', '__CSEQ_assertext'] = 'assert'
# fmap['2ls', '__CSEQ_assert'] = 'assert'
# fmap['2ls', '__CSEQ_nondet_int'] = 'nondet_int'
# fmap['2ls', '__CSEQ_nondet_uint'] = 'nondet_uint'

fmap['klee', '__CSEQ_assume'] = 'KLEE_assume'
fmap['klee', '__CSEQ_assertext'] = 'klee_assert'
fmap['klee', '__CSEQ_assert'] = 'klee_assert'
fmap['klee', '__CSEQ_nondet_int'] = 'KLEE_nondet_int'
fmap['klee', '__CSEQ_nondet_uint'] = 'KLEE_nondet_uint'

fmap['cpachecker', '__CSEQ_assume'] = '__VERIFIER_assume'
fmap['cpachecker', '__CSEQ_assertext'] = '__VERIFIER_assert'
fmap['cpachecker', '__CSEQ_assert'] = '__VERIFIER_assert'
fmap['cpachecker', '__CSEQ_nondet_int'] = '__VERIFIER_nondet_int'
fmap['cpachecker', '__CSEQ_nondet_uint'] = '__VERIFIER_nondet_uint'

_maxrightindent = 10   # max columns right for non-raw lines
_rawlinemarker = '__CSEQ_removeindent'


class newinstrumenter(core.module.Translator):
	def init(self):
		self.inputparam('backend','backend to use for analysis, available choices are:\nbounded model-checkers: (blitz, cbmc, esbmc, llbmc)\nabstraction-based: (cpachecker, satabs)\ntesting: (klee)','b','cbmc',False)
		self.inputparam('bitwidth','custom bidwidths for integers','w',None,True)
		self.inputparam('header', 'raw text file to add on top of the instrumented file', 'h', '', True)
		self.inputparam('precision', '. . .(internal use only)', '', default=None, optional=True)


	def loadfromstring(self,string,env):
		self.env = env

		self.backend = self.getinputparam('backend')
		self.bitwidth = self.getinputparam('bitwidth')
		self.extheader = self.getinputparam('header')
		self.precision = self.getinputparam('precision')

		if self.backend not in _backends:
			raise core.module.ModuleError("backend '%s' not supported" % self.backend)

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

		# Transformation 4:
		# insert the top header, passed as an input parameter.
		self.insertheader(self.extheader)          # header passed by previous module
		self.insertheader(self._generateheader())  # top comment with translation parameters

		if self.backend == 'klee':
			self.insertheader(core.utils.printFile('modules/klee_extra.c'))
		if self.backend == 'cpachecker':
			self.insertheader(core.utils.printFile('modules/cpa_extra.c'))


	def visit_BinaryOp(self, n):
		castL = castR = ''

		# Type-cast to the larger bitwidth in case of different bitwidths.
		# Type-cast constant operands to the same type of the other operand.
		#
		#if n.op in ('<', '<=', '==', '>=', '>') and self.backend == 'esbmc':

		if n.op == '!=':
			self.error("cazzo")


		if n.op in ('*') and self.backend == 'esbmc':
			x = self._extractID(n.left)
			xfull = self._parenthesize_if(n.left, lambda d: not self._is_simple_node(d))
			bL = self._varbitwidth(self.blockid,x)

			y = self._extractID(n.right)
			yfull = self._parenthesize_if(n.right, lambda d: not self._is_simple_node(d))
			(p2,q2) = self._varprecision(self.blockid,y)
			bR = self._varbitwidth(self.blockid,y)

			if bL == None and bR == None:             pass
			if bL == None and bR != None:             castL = '(typeof(%s))' % (yfull)
			if bL != None and bR == None:             castR = '(typeof(%s))' % (xfull)
			if bL != None and bR != None and bL > bR: castR = '(typeof(%s))' % (xfull)
			if bL != None and bR != None and bL < bR: castL = '(typeof(%s))' % (yfull)

			if castL != '': self.debug('adding explicit cast for expression (%s)' % (xfull))
			if castR != '': self.debug('adding explicit cast for expression(%s)' % (yfull))

		lval_str = self._parenthesize_if(n.left,lambda d: not self._is_simple_node(d))
		rval_str = self._parenthesize_if(n.right,lambda d: not self._is_simple_node(d))

		return '%s%s %s %s%s' % (castL,lval_str,n.op,castR,rval_str)


	def visit_Assignment(self, n):
		lvalstr = self.visit(n.lvalue)      # lvalue, full expression, including any array indexes (e.g., M[3][20948])
		lvalID = self._extractID(n.lvalue)  # lvalue, identifier only (e.g., M)

		if n.op=='=' and self._isfixedpoint(self.Parser.blockdefid(self.blockid,lvalID),lvalID) and self.bitwidth is not None:
			w = self.bitwidth[self.Parser.blockdefid(self.blockid,lvalID),lvalID]+1
			rvalstr = self._parenthesize_if(n.rvalue,lambda n: isinstance(n, pycparser.c_ast.Assignment))

			cast = ''

			if self.backend == 'cbmc' or self.backend == 'cbmc-ext':
				# Add cast with x=y, with x of greater bitwidth.
				if ('0.0',lvalID) in self.precision and ('0.0',rvalstr) in self.precision:
					(p1,q1) = self.precision['0.0',lvalID]
					(p2,q2) = self.precision['0.0',rvalstr]

					# For assignments to another variable,
					# only add cast when promoting to a larger bitwidth.
					if p1+q1 > p2+q2: cast = '(__CPROVER_bitvector[%s])' % w
				elif type(n.rvalue)==pycparser.c_ast.BinaryOp and n.rvalue.op == '<<':
					# Add explicit cast for left shifts, which
					# by construction are always stored into a larger bitwidth.
					cast = '(__CPROVER_bitvector[%s])' % w
				elif type(n.rvalue)==pycparser.c_ast.BinaryOp and n.rvalue.op in ('+','-','*','/'):
					# Add explicit cast for +,-,*,/, which
					# by construction are always stored into a larger bitwidth.
					cast = '(__CPROVER_bitvector[%s])' % w

			out = '%s = %s%s' % (lvalstr,cast,rvalstr)
			return out
		#type(n.rvalue)==pycparser.c_ast.BinaryOp and n.rvalue.op == '<<'
		else:
			rval_str = self._parenthesize_if(n.rvalue,lambda n: isinstance(n, pycparser.c_ast.Assignment))
			return '%s %s %s' % (self.visit(n.lvalue), n.op, rval_str)


	def visit_Decl(self,n,no_type=False):
		# no_type is used when a Decl is part of a DeclList, where the type is
		# explicitly only for the first delaration in a list.
		#
		s = n.name if no_type else self._generate_decl(n)

		# In case  x  has a custom bitwidth (passed by a previous module), convert
		# 'int x'  to  'bitvectors[k] x', or
		# 'unsigned int x'  to  'unsigned bitvectors[k] x', or
		# '__cs_fixedpoint x' to 'bitvectors[k] x'm, or .
		# '__cs_ufixedpoint x' to 'unsigned bitvectors[k] x'm.

		#  y__2_14__=16399 (0100000000001111) <+(01.00000000001111) +(1.00091552734)>
		#  y__2_14__=24575 (0101111111111111) <+(01.01111111111111) +(1.49993896484)>
		ninitextra = ''

		if self.backend == 'cbmc' or self.backend == 'cbmc-ext':
			if self.bitwidth is not None:
				if s.startswith("fixedpoint ") and (self.blockid,n.name) in self.bitwidth:
					b = int(self.bitwidth[self.blockid,n.name])+1
					s = s.replace("fixedpoint ","__CPROVER_bitvector[%s] " % b,1)
					ninitextra = '(__CPROVER_bitvector[%s])' % b
				elif s.startswith("ufixedpoint ") and (self.blockid,n.name) in self.bitwidth:
					b = int(self.bitwidth[self.blockid,n.name])+1
					s = s.replace("ufixedpoint ","unsigned __CPROVER_bitvector[%s] " % b,1)
					ninitextra = '(__CPROVER_bitvector[%s])' % b

		if self.backend == 'esbmc':
			if self.bitwidth is not None:
				if s.startswith("fixedpoint ") and (self.blockid,n.name) in self.bitwidth:
					b = int(self.bitwidth[self.blockid,n.name])+1
					s = s.replace("fixedpoint ","_ExtInt(%s) " % b,1)
					ninitextra = '(_ExtInt(%s))' % b
				elif s.startswith("ufixedpoint ") and (self.blockid,n.name) in self.bitwidth:
					b = int(self.bitwidth[self.blockid,n.name])+1
					s = s.replace("ufixedpoint ","unsigned _ExtInt(%s) " % b,1)
					ninitextra = '(_ExtInt(%s))' % b

				#elif s.startswith("__cs_fixedpoint ") and (self.blockid,n.name) in self.bitwidth:
				#	s = s.replace("__cs_fixedpoint ","__CPROVER_bitvector[%s] " % self.bitwidth[self.blockid,n.name],1)
				#	ninitextra = '(__CPROVER_bitvector[%s])' % self.bitwidth[self.blockid,n.name]

		if n.bitsize: s += ' : ' + self.visit(n.bitsize)
		if n.init:
			if isinstance(n.init,pycparser.c_ast.InitList):
				s += ' = {' + self.visit(n.init) + '}'
			elif isinstance(n.init,pycparser.c_ast.ExprList):
				s += ' = (' + self.visit(n.init) + ')'
			else:
				s += ' = ' + ninitextra + self.visit(n.init)
		return s


	''' converts function calls '''
	def visit_FuncCall(self,n):
		fref = self._parenthesize_unless_simple(n.name)

		# Transformation 3.
		if fref == '__CSEQ_rawline':
			return self.visit(n.args)[1:-1]+_rawlinemarker

		args = self.visit(n.args)
		if (fref == '__CSEQ_assertext' and
				self.backend not in ('cbmc', 'esbmc')):
			args = self.visit(n.args.exprs[0])   # Only get the first expression

		if (self.backend, fref) in fmap:
			fref = fmap[self.backend, fref]

		return fref + '(' + args + ')'

	def _generateheader(self):
		masterhash_framework = '0000'
		masterhash_modulechain = '0000'

		h  = '/*\n'
		h += ' *  generated by CSeq [ %s / %s ] %s \n' % (masterhash_framework,masterhash_modulechain,strftime("%Y-%m-%d %H:%M:%S",localtime()))
		h += ' * \n'
		#h += ' *                    [ %s %s\n' % (core.utils.shortfilehash('cseq.py'),FRAMEWORK_VERSION)
		h += ' *                    [ %s %s\n' % (core.utils.shortfilehash('core/merger.py'),0)
		h += ' *                      %s %s\n' % (core.utils.shortfilehash('core/parser.py'),0)
		h += ' *                      %s %s ]\n' % (core.utils.shortfilehash('core/module.py'),0)
		##h += ' *\n'
		##h += ' *  %s\n' %strftime("%Y-%m-%d %H:%M:%S",localtime())
		h += ' *\n'
		h += ' *  params:\n'

		h += ' *    '
		for o,a in self.env.opts:
			 h+='%s %s, ' % (o,a)
		h+= '\n'
		h += ' *\n'

		h += ' *  modules:\n'

		for transforms,m in enumerate(self.env.modules):
			paramin = ' '.join(p.id for p in m.inputparamdefs)
			params = '(%s)'  % paramin
			hash = '0' #core.utils.shortfilehash('modules/%s.py' % m.name())
			h += ' *    %s %s%s %s\n' %(hash,m.name(),'',params) # m.VERSION

		h += ' *\n'
		h += ' */\n'
		return h


	''' Check whether a given (scope,variablename) correspond to a fixed-point variable.
	'''
	def _isfixedpoint(self,scope,name):
		scope = self.Parser.blockdefid(scope,name)
		return (scope,name) in self.precision


	''' Extract the variable identifier from the sub-AST rooted at n.

		Returns  None  if the node corresponds to a constant expression,
		the variable identifier if the node contains a simple variable occurrence,
		the array identifier (e.g. arr) in case the node
		is an array reference (e.g. arr[x][y]).

	    The identifier so obtained can then be used to look up the symbol table.
	'''
	def _extractID(self,n):
		if type(n) == pycparser.c_ast.Constant: return n.value
		if type(n) == pycparser.c_ast.ID: return self.visit(n)
		if type(n) == pycparser.c_ast.UnaryOp: return self._extractID(n.expr)

		if type(n) == pycparser.c_ast.ArrayRef:
			next = n

			while type(next.name) != pycparser.c_ast.ID:
				next = next.name

			return self.visit(next.name)

		return None
		# shouldn't really get to this point
		#self.error('unable to extract variable ID from AST-subtree: unknown node type (%s).' % type(n), True)

	def _isarray(self,block,var):
		scope = self.Parser.blockdefid(block,var)

		if scope is not None:
			if type(self.Parser.var[scope,var].type) == pycparser.c_ast.ArrayDecl: return True

		return False


	# Return the identifier of the error variable for the given variable.
	def _errorvar(self,block,var):
		block = self.Parser.blockdefid(block,var)

		if block is not None:
			if (block,var) in self.errorvar: return self.errorvar[block,var]

		return None


	def _varprecision(self,block,var):
		if (self.Parser.blockdefid(block,var),var) in self.precision:
			return self.precision[self.Parser.blockdefid(block,var),var]

		#self.error("unable to extract precision for variable %s, please double check declaration" % var, snippet=True)
		return (None,None) # might be a constant


	def _varbitwidth(self,block,var):
		if (self.Parser.blockdefid(block,var),var) in self.precision:
			return self.bitwidth[self.Parser.blockdefid(block,var),var]

		#self.error("unable to extract precision for variable %s, please double check declaration" % var, snippet=True)
		return (None) # might be a constant


	def _newtmpvar(self,block,id,i,f,suffix='T'):
		cnt = self._tmpvarcnt
		self._tmpvarcnt+=1

		name = '%s%s_%s__%s_%s__' % (suffix,id,self._tmpvarcnt,i,f)
		self.precision[block,name] = (i,f)
		self.bitwidth[block,name] = (i+f)
		self.sign[block,name] = 1

		return name








