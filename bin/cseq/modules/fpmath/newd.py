""" CSeq C Sequentialization Framework
    Bit-precise encoding of numerical error under fixed-point arithmetics.

Authors:
    Stella Simic, Omar Inverso

Changes:
    2020.05.27  first version [IFM 2020]

"""
import core.module
import pycparser


class newd(core.module.Translator):
	precision = {}  # precision (i,f) for a fixed-point variable (blockid,id)
	errorvar = {}   # identifier of the error variable of each fp variable
	sign = {}       # signedness of the error variable of each fp variable (1 means signed)

	#sign = {}        # sign of fixed-point variables (0=signed, 1=unsigned)
	bitwidth = {}   # custom bitwidth for specific int variables, e.g. ['main','var'] = 4

	_noerrorcheck = False
	_nooverflowcheck = False
	_nodeltacheck = False

	_tmpvarcnt = 0

	def init(self):
		self.inputparam('error-i', 'error precision integer part', 'i', default='1', optional=False)
		self.inputparam('error-f', 'error precision fractional part', 'f', default='1', optional=False)
		self.inputparam('error-bound', 'max no. of bits allowed for the propagated error', 'e', default=1, optional=False)

		self.inputparam('precision', '. . .(internal use only)', '', default=None, optional=True)
		self.inputparam('errorvar', '. . .(internal use only)', '', default=None, optional=True)
		self.inputparam('tmpvarcnt', '. . .(internal use only)', 'e', default=1, optional=False)

		#self.inputparam('sign', '. . .(internal use only)', '', default=None, optional=True)
		#self.inputparam('no-error', 'disable error bound check', '', default=True, optional=True)
		#self.inputparam('no-overflow', 'disable overflow check', '', default=False, optional=True)
		#self.inputparam('no-deltacheck', 'disable delta check', '', default=False, optional=True)
		#self.inputparam('eps', 'epsilon for delta assertion checking', 'e', default='0x1', optional=False)

		self.outputparam('precision')
		self.outputparam('bitwidth')
		self.outputparam('sign')
		self.outputparam('errorvar')
		self.outputparam('tmpvarcnt')
		self.outputparam('error-i')
		self.outputparam('error-f')
		self.outputparam('errorbound')

		self.error_i = self.error_f = self.error_if = self.errorbound = None


	def loadfromstring(self,string,env):
		if self.getinputparam('no-error') is not None: self._noerrorcheck = True
		if self.getinputparam('no-overflow') is not None: self._nooverflowcheck = True
		if self.getinputparam('no-deltacheck') is not None: self._nodeltacheck = True

		self.precision = self.getinputparam('precision')
		self.bitwidth = self.getinputparam('bitwidth')
		self.errorvar = self.getinputparam('errorvar')
		self._tmpvarcnt = self.getinputparam('tmpvarcnt')
		self.error_i = int(self.getinputparam('error-i'))
		self.error_f = int(self.getinputparam('error-f'))
		self.errorbound = int(self.getinputparam('error-bound'))
		self.eps = self.getinputparam('eps')

		#miniheader = "typedef int fixedpoint; typedef int  __cs_fixedpoint; "
		miniheader = ''
		super(self.__class__, self).loadfromstring(miniheader+string, env)

		self.setoutputparam('precision',self.precision)
		self.setoutputparam('bitwidth',self.bitwidth)
		self.setoutputparam('sign',self.sign)
		self.setoutputparam('errorvar',self.errorvar)
		self.setoutputparam('tmpvarcnt',self._tmpvarcnt)
		self.setoutputparam('error-i',self.error_i)
		self.setoutputparam('error-f',self.error_f)
		self.setoutputparam('errorbound',self.errorbound)


	def visit_Assignment(self, n):
		ei = self.error_i
		ef = self.error_f
		eb = self.errorbound

		x = self._extractID(n.lvalue)     # identifier-only lvalue (e.g., M)
		xfull = self.visit(n.lvalue)      # full lvalue (e.g., M[3][20948])
		blockdef = self.Parser.blockdefid(self.blockid,x)

		#if self._isfixedpoint(self.blockid,x):
		#	(p,q) = self.precision[blockdef,x]

		# No transformation.
		if not self._isfixedpoint(self.blockid,x):
			return super(self.__class__, self).visit_Assignment(n)

		if type(n.rvalue) == pycparser.c_ast.TernaryOp:    # ternary assignments
			return super(self.__class__, self).visit_Assignment(n)

		# Not handled.
		if n.op != '=':  #  <<=, >>=, +=, etc.
			self.error('unsupported operation (%s) on fixed-point variables' % n.op, snippet=True)

		if n.op=='=' and type(n.rvalue)==pycparser.c_ast.FuncCall:
			if self._parenthesize_unless_simple(n.rvalue.name)=='e_d':
				y = n.rvalue.args.exprs[0].name
				yfull = self.visit(n.rvalue.args.exprs[0])

				y1 = n.rvalue.args.exprs[1].name
				y1full = self.visit(n.rvalue.args.exprs[1])

				k = int(n.rvalue.args.exprs[2].value)

				#ybar = self._errorvar(self.blockid,y)
				ybar = yfull.replace(y,self._errorvar(self.blockid,y),1)

				t = self._newtmpvar(self.blockid,'t',ei,ef)
				t1 = self._newtmpvar(self.blockid,'t1',ei,ef)
				u = self._newtmpvar(self.blockid,'u',ei,ef)
				u1 = self._newtmpvar(self.blockid,'u1',ei,ef)
				t2 = self._newtmpvar(self.blockid,'t2',ei-k,ef+k)

				out  = 'fixedpoint %s;' % (t)
				out += 'fixedpoint %s;' % (t1)
				out += 'fixedpoint %s;' % (u)
				out += 'fixedpoint %s;' % (u1)
				out += 'fixedpoint %s;' % (t2)

				out += '%s = e_c(%s);' % (u,yfull) #out += '%s = e_c1(%s);' % (u,y)
				out += '%s = e_add(%s,%s);' % (t,u,ybar)
				out += '%s = e_c(%s);' % (u1,y1full) #out += '%s = e_c1(%s);' % (u1,y1)
				out += '%s = e_sub(%s,%s);' % (t1,t,u1)
				out += '%s = %s;' % (t2,t1)
				out += '%s = e_c(%s)' % (xfull,t2) #out += '%s = e_c2(%s)' % (xfull,t2)

				return out

		return super(self.__class__, self).visit_Assignment(n)


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


	def _newtmpvar(self,block,id,i,f,suffix='T'):
		cnt = self._tmpvarcnt
		self._tmpvarcnt+=1

		name = '%s%s_%s__%s_%s__' % (suffix,id,self._tmpvarcnt,i,f)
		self.precision[block,name] = (i,f)
		self.bitwidth[block,name] = (i+f)
		self.sign[block,name] = 1

		return name















