""" CSeq C Sequentialization Framework
    Bit-precise encoding of numerical error under fixed-point arithmetics.

Authors:
    Stella Simic, Omar Inverso

Purposes of this module:
  - implement the only remaining RANGE rule

Changes:
    2020.12.21  Slight changes to support Python 3
    2020.12.13  fixedpoint_raw_on() / fixedpoint_raw_off() to prevent transformations
    2020.05.27  getting precisions from previous modules [IFM 2020]
    2020.05.17  reimplemented from scratch

Assumptions:
  - no global variables
  - no function calls (need inlining first)
  - no side effect within array indexes (e.g. a[++i))

Notes:
  - no support for unsigned arithmetics (i.e., no sign)
  - costant operands in a binary operation are assumed to be in the same precision as the other operand
   (might refine this in the future).

"""
import core.module
import pycparser


class newcast(core.module.Translator):
	precision = {}  # precision (i,f) for a fixed-point variable (blockid,id)
	errorvar = {}   # identifier of the error variable of each fp variable
	sign = {}       # signedness of the error variable of each fp variable (1 means signed)

	#sign = {}        # sign of fixed-point variables (0=signed, 1=unsigned)
	bitwidth = {}   # custom bitwidth for specific int variables, e.g. ['main','var'] = 4

	_tmpvarcnt = 0

	rawmode = False # True = no transformation


	def init(self):
		self.inputparam('error-i', 'error precision integer part', 'i', default='1', optional=False)
		self.inputparam('error-f', 'error precision fractional part', 'f', default='1', optional=False)
		self.inputparam('error-bound', 'max no. of bits allowed for the propagated error', 'e', default=1, optional=False)

		self.inputparam('precision', '. . .(internal use only)', '', default=None, optional=True)
		self.inputparam('errorvar', '. . .(internal use only)', '', default=None, optional=True)
		self.inputparam('tmpvarcnt', '. . .(internal use only)', 'e', default=1, optional=False)

		self.outputparam('precision')
		self.outputparam('bitwidth')
		self.outputparam('sign')
		self.outputparam('errorvar')
		self.outputparam('tmpvarcnt')
		self.outputparam('error-i')
		self.outputparam('error-f')
		self.outputparam('errorbound')


	def loadfromstring(self,string,env):
		self.precision = self.getinputparam('precision')
		self.bitwidth = self.getinputparam('bitwidth')
		self.errorvar = self.getinputparam('errorvar')
		self._tmpvarcnt = self.getinputparam('tmpvarcnt')
		self.error_i = int(self.getinputparam('error-i'))
		self.error_f = int(self.getinputparam('error-f'))
		self.errorbound = int(self.getinputparam('error-bound'))

		super(self.__class__, self).loadfromstring(string,env)

		self.setoutputparam('precision',self.precision)
		self.setoutputparam('bitwidth',self.bitwidth)
		self.setoutputparam('sign',self.sign)
		self.setoutputparam('errorvar',self.errorvar)
		self.setoutputparam('tmpvarcnt',self._tmpvarcnt)
		self.setoutputparam('error-i',self.error_i)
		self.setoutputparam('error-f',self.error_f)
		self.setoutputparam('errorbound',self.errorbound)


	def visit_Assignment(self, n):
		if self.rawmode: return super(self.__class__, self).visit_Assignment(n)

		x = self._extractID(n.lvalue)     # identifier-only lvalue (e.g., M)
		xfull = self.visit(n.lvalue)      # full lvalue (e.g., M[3][20948])
		blockdef = self.Parser.blockdefid(self.blockid,x)

		if self._isfixedpoint(self.blockid,x):
			(p,q) = self.precision[blockdef,x]

		#print("= - - -> %s" % (type(n.rvalue)) )

		#if type(n.rvalue) != pycparser.c_ast.BinaryOp:
		#	print("- - - -> %s" % (self._extractID(n.rvalue) ))

		# Assignment to another variable with
		# both different integer and fractional precision:
		# x = y
		# (9th Range Rule)
		#if n.op=='=' and type(n.rvalue) != pycparser.c_ast.BinaryOp and type(n.rvalue)!=pycparser.c_ast.Constant:
		if n.op=='=' and (type(n.rvalue) == pycparser.c_ast.ID or type(n.rvalue)==pycparser.c_ast.ArrayRef or type(n.rvalue)==pycparser.c_ast.ID):
			y = self._extractID(n.rvalue)
			yfull = self._parenthesize_if(n.rvalue, lambda d: not self._is_simple_node(d))
			(p1,q1) = self._varprecision(self.blockid,y)

			if p!=p1 and q!=q1:
				x1 = self._newtmpvar(self.blockid,'',p,q1,'R')

				out  = 'fixedpoint %s;' % x1
				out += '%s = %s;' % (x1,yfull)
				out += '%s = %s' % (xfull,x1)

				return out

		return super(self.__class__, self).visit_Assignment(n)


	def visit_Decl(self,n,no_type=False):
		s = n.name if no_type else self._generate_decl(n)

		# Safety check for precisions.
		if s.startswith("fixedpoint ") or s.startswith("__cs_fixedpoint "):
			if (self.blockid,n.name) not in self.precision:
				self.error('unable to extract precision of fixed-point variable (%s)' % n.name, snippet=True)

		return super(self.__class__, self).visit_Decl(n,no_type)


	def visit_FuncCall(self,n):
		fref = self._parenthesize_unless_simple(n.name)

		if fref=='fixedpoint_raw_on':
			self.debug("fixedpoint raw mode enabled")
			self.rawmode = True

		if fref=='fixedpoint_raw_off':
			self.debug("fixedpoint raw mode disabled")
			self.rawmode = False

		return super(self.__class__, self).visit_FuncCall(n)


	''' Check whether a given (scope,variablename) correspond to a fixed-point variable.
	'''
	def _isfixedpoint(self,scope,name):
		scope = self.Parser.blockdefid(scope,name)
		return (scope,name) in self.precision


	''' Extract the variable identifier from the sub-AST rooted at n.

		Returns  None  if the node corresponds to a constant expression,
		the variable identifier if the node contains a simple variable occurrence,
		the array identifier in case the node is an array reference (e.g. arr[x][y]).

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

		# shouldn't really get to this point
		self.error('unable to extract variable ID from AST-subtree: unknown node type (%s).' % type(n), True)


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


	def _newtmpvar(self,block,id,i,f,suffix='T'):
		cnt = self._tmpvarcnt
		self._tmpvarcnt+=1

		name = '%s%s_%s__%s_%s__' % (suffix,id,self._tmpvarcnt,i,f)
		self.precision[block,name] = (i,f)
		self.bitwidth[block,name] = (i+f)
		self.sign[block,name] = 1

		return name















