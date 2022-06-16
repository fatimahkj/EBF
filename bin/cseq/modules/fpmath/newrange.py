""" CSeq C Sequentialization Framework
    Bit-precise encoding of numerical error under fixed-point arithmetics.

Authors:
    Stella Simic, Omar Inverso

Purposes of this module:
  - extract the precision of eacy fixed-point variable
  - enforce syntactic restrictions needed for the other modules in the chain
  - implement the RANGE rules (except one)

Changes:
    2020.12.13  fixedpoint_raw_on() / fixedpoint_raw_off() to prevent transformations
    2020.12.12  no longer automatically adjusting error precision (required for simpler if-then-else handling)
    2020.06.21  fixed range rules for multiplication and division to avoid signed overflow (need one extra integer bit) [IFM 2020]
    2020.05.27  output precisions to next module
    2020.05.25  checking for undeclared variables
    2020.05.23  shift rules
    2020.05.17  reimplemented from scratch

Assumptions:
  - no global variables
  - no function calls (need inlining first)
  - ids ending with __ denote a fixed-point variable
  - a fixed-point variable is declared as x__P_Q__, where
    P and Q denote its integer and fractional precision, respectively.
  - no side effect within array indexes (e.g. a[++i))

Notes:
  - no support for unsigned arithmetics (i.e., no sign)
  - costant operands in a binary operation are assumed to be in the same precision as the other operand
   (might refine this in the future)
  - the precision and error variable maps are output to next modules;
    the next modules need to maintain such maps
   (e.g., when new variables are added).

"""
import core.module
import pycparser


class newrange(core.module.Translator):
	precision = {}  # precision (i,f) for a fixed-point variable (blockid,id)
	errorvar = {}   # identifier of the error variable of each fp variable
	sign = {}       # signedness of the error variable of each fp variable (1 means signed)

	bitwidth = {}   # custom bitwidth for specific int variables, e.g. ['main','var'] = 4
	errorvar = {}   # identifier of the error variable of each fp variable

	_tmpvarcnt = 0

	maxp = 0
	maxq = 0

	rawmode = False # True = no transformation


	def init(self):
		self.inputparam('error-i', 'error precision integer part', 'i', default='1', optional=False)
		self.inputparam('error-f', 'error precision fractional part', 'f', default='1', optional=False)
		self.inputparam('error-bound', 'max no. of bits allowed for the propagated error', 'e', default=1, optional=False)

		self.inputparam('precision', '. . .(internal use only)', '', default=None, optional=True)

		self.outputparam('bitwidth')
		self.outputparam('sign')
		self.outputparam('errorvar')
		self.outputparam('tmpvarcnt')
		self.outputparam('error-i')
		self.outputparam('error-f')
		self.outputparam('errorbound')


	def loadfromstring(self,string,env):
		self.error_i = int(self.getinputparam('error-i'))
		self.error_f = int(self.getinputparam('error-f'))
		self.errorbound = int(self.getinputparam('error-bound'))
		self.precision = self.getinputparam('precision')

		super(self.__class__, self).loadfromstring(string, env)

		for (block,var) in self.precision:
			(p,q) = self.precision[block,var]
			self.maxp = max(self.maxp,p)
			self.maxq = max(self.maxq,q)

		if self.error_i < self.maxp:
			#self.warn("increasing error precision from (%s.%s) to (%s.%s) to match overall max variable integer precision" % (self.error_i,self.error_f,self.maxp,self.error_f))
			self.error("increasing error precision from (%s.%s) to (%s.%s) to match overall max variable integer precision" % (self.error_i,self.error_f,self.maxp,self.error_f))
			self.error_i = self.maxp

		if self.error_f < self.maxq:
			#self.warn("increasing error precision from (%s.%s) to (%s.%s) to match overall max variable fractional precision" % (self.error_i,self.error_f,self.error_i,self.maxq))
			self.error("increasing error precision from (%s.%s) to (%s.%s) to match overall max variable fractional precision" % (self.error_i,self.error_f,self.error_i,self.maxq))
			self.errorbound += self.maxq-self.error_f
			self.error_f = self.maxq
			self.warn("adjusting error bound to (%s) accordingly" % (self.errorbound))

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

		# Check shift width k:
		#
		# 1. k cannot be greater than the variable to be shifted
		# 2. k cannot be greater than either of the error precisions (i,f)
		# 3. k must be a constant.
		if n.op=='=' and type(n.rvalue)==pycparser.c_ast.BinaryOp:
			if n.rvalue.op == '<<' or n.rvalue.op == '>>':
				y = self._extractID(n.rvalue.left)
				yfull = self._parenthesize_if(n.rvalue.left, lambda d: not self._is_simple_node(d))
				(p1,q1) = self._varprecision(self.blockid,y)

				if type(n.rvalue.right) != pycparser.c_ast.Constant:
					self.error("non-constant right operand in fixed-point shift", snippet=True)

				k = int(n.rvalue.right.value)

				if k>self.error_i:
					self.error_i = k
					#self.warn("increasing error precision to (%s.%s) due to shift operation" % (self.error_i,self.error_f), lineno=True)
					self.error("error precision needs to be at least (%s.%s) due to shift operation" % (self.error_i,self.error_f), lineno=True)

				if k>self.error_f:
					self.errorbound += k-self.error_f
					self.error_f = k
					#self.warn("increasing error precision to (%s.%s) due to shift operation" % (self.error_i,self.error_f))
					self.error("error precision needs to be at least (%s.%s) due to shift operation" % (self.error_i,self.error_f))
					self.warn("adjusting error bound to (%s) accordingly" % (self.errorbound))

				if k>p1+q1:
					self.error("shift beyond variable bitwidth", snippet=True)

		# x = y >> k (case 1)
		# (1st Range Rule)
		if n.op=='=' and type(n.rvalue)==pycparser.c_ast.BinaryOp:
			if n.rvalue.op == '>>':
				y = self._extractID(n.rvalue.left)
				yfull = self._parenthesize_if(n.rvalue.left, lambda d: not self._is_simple_node(d))
				(p1,q1) = self._varprecision(self.blockid,y)

				k = int(n.rvalue.right.value)

				if k<=p1 and k<=q1:
					if p!=p1-k or q!=q1:
						x1 = self._newtmpvar(self.blockid,'',p1-k,q1,'R')
						out  = 'fixedpoint %s;' % (x1)
						out += '%s = %s >> %s;' % (x1,yfull,k)
						out += '%s = %s' % (xfull,x1)
						return out

		# x = y >> k (case 2)
		# (2nd Range Rule)
		if n.op=='=' and type(n.rvalue)==pycparser.c_ast.BinaryOp:
			if n.rvalue.op == '>>':
				y = self._extractID(n.rvalue.left)
				yfull = self._parenthesize_if(n.rvalue.left, lambda d: not self._is_simple_node(d))
				(p1,q1) = self._varprecision(self.blockid,y)

				k = int(n.rvalue.right.value)

				if k>p1 and k<=q1:
					if p!=0 or q!=q1:
						x1 = self._newtmpvar(self.blockid,'',0,q1,'R')
						out  = 'fixedpoint %s;' % (x1)
						out += '%s = %s >> %s;' % (x1,yfull,k)
						out += '%s = %s' % (xfull,x1)
						return out

		# x = y >> k (case 3)
		# (3rd Range Rule)
		if n.op=='=' and type(n.rvalue)==pycparser.c_ast.BinaryOp:
			if n.rvalue.op == '>>':
				y = self._extractID(n.rvalue.left)
				yfull = self._parenthesize_if(n.rvalue.left, lambda d: not self._is_simple_node(d))
				(p1,q1) = self._varprecision(self.blockid,y)

				k = int(n.rvalue.right.value)

				if k>p1:
					if P!=p1-k and q!=q1:
						x1 = self._newtmpvar(self.blockid,'',p1-k,q1,'R')
						out  = 'fixedpoint %s;' % (x1)
						out += '%s = %s >> %s;' % (x1,yfull,k)
						out += '%s = %s' % (xfull,x1)
						return out

		# x = y << k
		# (4th Range Rule)
		if n.op=='=' and type(n.rvalue)==pycparser.c_ast.BinaryOp:
			if n.rvalue.op == '<<':
				y = self._extractID(n.rvalue.left)
				yfull = self._parenthesize_if(n.rvalue.left, lambda d: not self._is_simple_node(d))
				(p1,q1) = self._varprecision(self.blockid,y)

				k = int(n.rvalue.right.value)

				if p!=p1+k or q!=q1:
					x1 = self._newtmpvar(self.blockid,'',p1+k,q1,'R')
					out  = 'fixedpoint %s;' % (x1)
					out += '%s = %s << %s;' % (x1,yfull,k)
					out += '%s = %s' % (xfull,x1)
					return out

		# x = y + z
		# (5th Range Rule)
		if n.op=='=' and type(n.rvalue)==pycparser.c_ast.BinaryOp:
			if n.rvalue.op=='+':
				y = self._extractID(n.rvalue.left)
				yfull = self._parenthesize_if(n.rvalue.left, lambda d: not self._is_simple_node(d))
				(p1,q1) = self._varprecision(self.blockid,y)

				z = self._extractID(n.rvalue.right)
				zfull = self._parenthesize_if(n.rvalue.right, lambda d: not self._is_simple_node(d))
				(p2,q2) = self._varprecision(self.blockid,z)

				if (p1,q1)==(None,None) and (p2,q2)==(None,None):
					self.error("addition of two constants cannot be stored into a fixed-point variable", snippet=True)

				# Two variables of same precision, or a variable and a constant.
				if (p1,q1)==(p2,q2) or ((p1,q1)!=(None,None) or (p2,q2)!=(None,None)):
					if (p1,q1)==(None,None) and (p2,q2)!=(None,None):
						(p1,q1) = (p2,q2)
						coords = self._mapbacklineno(self.currentinputlineno)
						self.warn('assuming precision (%s.%s) for constant' % (p2,q2), lineno=True)
					elif (p2,q2)==(None,None) and (p1,q1)!=(None,None):
						(p2,q2) = (p1,q1)
						coords = self._mapbacklineno(self.currentinputlineno)
						self.warn('assuming precision (%s.%s) for constant' % (p1,q1), lineno=True)

					if (p1,q1)!=(p2,q2):
						coords = self._mapbacklineno(self.currentinputlineno)
						self.error('fixed-point addition requires operands of the same precision', snippet=True)

					if p!=p1+1 or q!=q1:
						x1 = self._newtmpvar(self.blockid,'',p1+1,q1,'R')
						out  = 'fixedpoint %s;' % (x1)
						out += '%s = %s %s %s;' % (x1,yfull,n.rvalue.op,zfull)
						out += '%s = %s' % (xfull,x1)
						return out

		# x = y - z
		# (6th Range Rule)
		if n.op=='=' and type(n.rvalue)==pycparser.c_ast.BinaryOp:
			if n.rvalue.op=='+' or n.rvalue.op=='-':
				y = self._extractID(n.rvalue.left)
				yfull = self._parenthesize_if(n.rvalue.left, lambda d: not self._is_simple_node(d))
				(p1,q1) = self._varprecision(self.blockid,y)

				z = self._extractID(n.rvalue.right)
				zfull = self._parenthesize_if(n.rvalue.right, lambda d: not self._is_simple_node(d))
				(p2,q2) = self._varprecision(self.blockid,z)

				if (p1,q1)==(None,None) and (p2,q2)==(None,None):
					self.error("subtraction of two constants cannot be stored into a fixed-point variable", snippet=True)

				# Two variables of same precision, or a variable and a constant.
				if (p1,q1)==(p2,q2) or ((p1,q1)!=(None,None) or (p2,q2)!=(None,None)):
					if (p1,q1)==(None,None) and (p2,q2)!=(None,None):
						(p1,q1) = (p2,q2)
						coords = self._mapbacklineno(self.currentinputlineno)
						self.warn('assuming precision (%s.%s) for constant' % (p2,q2), lineno=True)
					elif (p2,q2)==(None,None) and (p1,q1)!=(None,None):
						(p2,q2) = (p1,q1)
						coords = self._mapbacklineno(self.currentinputlineno)
						self.warn('assuming precision (%s.%s) for constant' % (p1,q1), lineno=True)

					if (p1,q1)!=(p2,q2):
						coords = self._mapbacklineno(self.currentinputlineno)
						self.error('fixed-point addition requires operands of the same precision', snippet=True)

					if p!=p1+1 or q!=q1:
						x1 = self._newtmpvar(self.blockid,'',p1+1,q1,'R')
						out  = 'fixedpoint %s;' % (x1)
						out += '%s = %s %s %s;' % (x1,yfull,n.rvalue.op,zfull)
						out += '%s = %s' % (xfull,x1)
						return out

		# x = y * z
		# (7th Range Rule)
		if n.op=='=' and type(n.rvalue)==pycparser.c_ast.BinaryOp:
			if n.rvalue.op == '*':
				y = self._extractID(n.rvalue.left)
				yfull = self._parenthesize_if(n.rvalue.left, lambda d: not self._is_simple_node(d))
				(p1,q1) = self._varprecision(self.blockid,y)

				z = self._extractID(n.rvalue.right)
				zfull = self._parenthesize_if(n.rvalue.right, lambda d: not self._is_simple_node(d))
				(p2,q2) = self._varprecision(self.blockid,z)

				if (p1,q1)==(None,None) and (p2,q2)==(None,None):
					self.error("multiplication of two constants cannot be stored into a fixed-point variable", snippet=True)

				# Two variables of same precision, or a variable and a constant.
				if (p1,q1)==(p2,q2) or ((p1,q1)!=(None,None) or (p2,q2)!=(None,None)):
					if (p1,q1)==(None,None) and (p2,q2)!=(None,None):
						(p1,q1) = (p2,q2)
						coords = self._mapbacklineno(self.currentinputlineno)
						self.warn('assuming precision (%s.%s) for constant' % (p2,q2), lineno=True)
					elif (p2,q2)==(None,None) and (p1,q1)!=(None,None):
						(p2,q2) = (p1,q1)
						coords = self._mapbacklineno(self.currentinputlineno)
						self.warn('assuming precision (%s.%s) for constant' % (p1,q1), lineno=True)

					if p!=p1+p2+1 or q!=q1+q2:
						x1 = self._newtmpvar(self.blockid,'',p1+p2+1,q1+q2,'R')
						out  = 'fixedpoint %s;' % (x1)
						out += '%s = %s * %s;' % (x1,yfull,zfull)
						out += '%s = %s' % (xfull,x1)
						return out

		# x = y / z
		# (8th Range Rule)
		if n.op=='=' and type(n.rvalue)==pycparser.c_ast.BinaryOp:
			if n.rvalue.op == '/':
				y = self._extractID(n.rvalue.left)
				yfull = self._parenthesize_if(n.rvalue.left, lambda d: not self._is_simple_node(d))
				(p1,q1) = self._varprecision(self.blockid,y)

				z = self._extractID(n.rvalue.right)
				zfull = self._parenthesize_if(n.rvalue.right, lambda d: not self._is_simple_node(d))
				(p2,q2) = self._varprecision(self.blockid,z)

				if (p1,q1)==(None,None) and (p2,q2)==(None,None):
					self.error("division of two constants cannot be stored into a fixed-point variable", snippet=True)

				# Two variables of same precision, or a variable and a constant.
				if (p1,q1)==(p2,q2) or ((p1,q1)!=(None,None) or (p2,q2)!=(None,None)):
					if (p1,q1)==(None,None) and (p2,q2)!=(None,None):
						(p1,q1) = (p2,q2)
						coords = self._mapbacklineno(self.currentinputlineno)
						self.warn('assuming precision (%s.%s) for constant' % (p2,q2), lineno=True)
					elif (p2,q2)==(None,None) and (p1,q1)!=(None,None):
						(p2,q2) = (p1,q1)
						coords = self._mapbacklineno(self.currentinputlineno)
						self.warn('assuming precision (%s.%s) for constant' % (p1,q1), lineno=True)

					if p!=p1+q2+1 or q!=p2+q1:
						x1 = self._newtmpvar(self.blockid,'',p1+q2+1,p2+q1,'R')
						out  = 'fixedpoint %s;' % (x1)
						out += '%s = %s / %s;' % (x1,yfull,zfull)
						out += '%s = %s' % (xfull,x1)
						return out

		# No transformation.
		return super(self.__class__, self).visit_Assignment(n)


	def visit_FuncCall(self,n):
		fref = self._parenthesize_unless_simple(n.name)

		if fref=='fixedpoint_raw_on':
			self.debug("fixedpoint raw mode enabled")
			self.rawmode = True

		if fref=='fixedpoint_raw_off':
			self.debug("fixedpoint raw mode disabled")
			self.rawmode = False

		return super(self.__class__, self).visit_FuncCall(n)


	def visit_ID(self,n):
		n = super(self.__class__, self).visit_ID(n)

		if n.endswith('__') and self._varprecision(self.blockid,n) == (None,None):
			if not (self.rawmode and n.startswith('err_')):
				self.error('undeclared fixed-point variable (%s)' %n, snippet=True)

		return n


	'''
	def visit_Decl(self,n,no_type=False):
		s = n.name if no_type else self._generate_decl(n)

		if s.startswith("fixedpoint ") or s.startswith("__cs_fixedpoint ") or s.startswith("ufixedpoint "):
			# Populate self.precision so that from now on isfixedpoint() can be used.
			######if n.init: self.error("init expression for variable (%s) ignored" % (n.name))
			if n.bitsize: self.error("bitsize not allowed for expression variable (%s)" % (n.name))

			if n.name.endswith('__'):
				try:
					(i,f) = [int(j) for j in n.name.split('_')[2:4]]
					self.precision[self.blockid,n.name] = (i,f)

					self.debug("Adding precision: %s,%s for variable %s block %s" % (i,f,n.name,self.blockid))
					#self.sign[self.blockid,n.name] = 0
					assert(i!=None and i!='' and i>=0)
					assert(f!=None and f!='' and f>=0)
				except Exception as e:
					self.error('unable to extract precision of fixed-point variable (%s), please use variable name suffix __i_f__ to declare precision:' % n.name, snippet=True)

				# Set the bitwidth of the variable as the sum of
				# the widths of the integer part and the fractional part, so
				# during the instrumentation they can be re-declared as
				#  s of appropriate size.
				(i,f) = self.precision[self.blockid,n.name]

				if s.startswith("ufixedpoint "): self.sign[self.blockid,n.name] = 0
				else: self.sign[self.blockid,n.name] = 1

				# [ICCPS2017] Unsigned variables need one extra bit to avoid sign extension.
				#if not self.sign[self.blockid,n.name]: self.bitwidth[self.blockid,n.name] = int(i)+int(f)+1
				#else: self.bitwidth[self.blockid,n.name] = int(i)+int(f)
				self.bitwidth[self.blockid,n.name] = int(i)+int(f)
		return super(self.__class__, self).visit_Decl(n,no_type)
	'''


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
		blk = self.Parser.blockdefid(block,var)
		#print ("======== variable %s current block %s defined in block %s" % (var,block,blk))
		#print ("======== %s" % (self.precision))

		if (self.Parser.blockdefid(block,var),var) in self.precision:
			return self.precision[self.Parser.blockdefid(block,var),var]

		#self.warn("unable to extract precision for variable %s, please double check declaration" % var)
		return (None,None) # might be a constant


	def _newtmpvar(self,block,id,i,f,suffix='T'):
		cnt = self._tmpvarcnt
		self._tmpvarcnt+=1

		name = '%s%s_%s__%s_%s__' % (suffix,id,self._tmpvarcnt,i,f)
		self.precision[block,name] = (i,f)
		self.bitwidth[block,name] = (i+f)
		self.sign[block,name] = 1

		return name















