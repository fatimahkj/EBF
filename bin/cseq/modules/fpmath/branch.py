""" CSeq Program Analysis Framework
    Analysis of discontuinity errors under fixed-point arithmetics.

Author:
    Omar Inverso

Purpose:
    Work out the sets of fixed-point variables written,
    for each if-then-else statement.
   (Those sets are used later to encode discontinuity errors.)

Changes:
    2020.12.09  first version

To do:
  - handle array elements (e.g., a[3])
  - handle nested branches

"""
import pycparserext.ext_c_parser, pycparser.c_ast, pycparserext.ext_c_generator
import core.module, core.parser, core.utils


class branch(core.module.Translator):
	written_ids = []

	# Sets representing the variables altered in if-then-else statements,
	# indexed by the root node of the AST statement itself,
	# to be propagated across the module chain.
	W_s = {}
	W_s1 = {}
	W_s2 = {}
	T = {}
	E = {}
	I = {}
	C = {}

	# Coords to AST nodes (if-then-else statements only)
	ite_coords = {}

	visiting_cond = False


	def init(self):
		self.inputparam('error-control-flow', 'propagate errors across control-flow branches', '', default=False, optional=True)

		self.outputparam('W_s')
		self.outputparam('W_s1')
		self.outputparam('W_s2')
		self.outputparam('T')
		self.outputparam('E')
		self.outputparam('I')
		self.outputparam('C')


	def loadfromstring(self, string, env):
		self.controlflowerror = True if self.getinputparam('error-control-flow') is not None else False

		super(self.__class__, self).loadfromstring(string, env)

		self.setoutputparam('W_s',self.W_s)
		self.setoutputparam('W_s1',self.W_s1)
		self.setoutputparam('W_s2',self.W_s2)
		self.setoutputparam('T',self.T)
		self.setoutputparam('E',self.E)
		self.setoutputparam('I',self.I)
		self.setoutputparam('C',self.C)

		#print("W_s >>>%s<<<" % self.W_s)
		#print("W_s1 >>>%s<<<" % self.W_s1)
		#print("W_s2 >>>%s<<<" % self.W_s2)
		#print("W_T >>>%s<<<" % self.T)
		#print("W_E >>>%s<<<" % self.E)
		#print("W_I >>>%s<<<" % self.I)


	def visit_Assignment(self, n):
		x = self._extractID(n.lvalue)     # identifier-only lvalue (e.g., M)
		xfull = self.visit(n.lvalue)      # full lvalue (e.g., M[3][20948])
		blockdef = self.Parser.blockdefid(self.blockid,x)

		#self.debug("looking for variable %s occurring in block %s ---> %s" % (x,self.blockid,blockdef))

		node = self.Parser.var[blockdef,x]
		decl = self._generate_decl(node)

		#self.log("assignment --- variable %s, xfull %s, blockdef %s, currblock %s" % (x,xfull,blockdef, self.blockid))

		# Can't use precisions to figure out which variables are fixed-point yet
		if decl.startswith('fixedpoint '):
			if n.op=='=':
				self.written_ids.append(xfull)
			else:
				self.error("assignment of fixed point variable not allowed with this operator %s" %(n.op))
		else:
			pass   # not a fixed-point variable anyway

		return super(self.__class__, self).visit_Assignment(n)


	def visit_ID(self,n):
		if self.visiting_cond:
			self.cond_id.append(n.name)

		return n.name


	def visit_If(self, n):
		if not self.controlflowerror:
			return super(self.__class__, self).visit_If(n)

		lineno = self._mapbacklineno(self.currentinputlineno)[0]
		#self.debug("if-then-else at line %s" % lineno)

		W = W_s = W_s1 = W_s2 = C = []

		s = 'if ('

		self.visiting_cond = True
		self.cond_id = []
		if n.cond: s += self.visit(n.cond)
		#print("===== %s " % self.written_ids)
		C = self.cond_id
		self.visiting_cond = False

		s += ')\n'

		# Work out the variables being written in each branch.
		self.written_ids = []

		#print("--- blockid:%s    block:%s    blockd:%s    blockcound:%s" % (self.blockid,self.block,self.blockd,self.blockcount))

		# Work out the set W_s1 of variables modified in the 'then' branch.
		self.written_ids = []
		t = self._generate_stmt(n.iftrue, add_indent=True)
		W_s1 = self.written_ids

		# Work out the set W_s2 of variables modified in the 'else' branch.
		if n.iffalse:
			self.written_ids = []
			e = self._generate_stmt(n.iffalse, add_indent=True)
			W_s2 = self.written_ids

		# Derive the remaining sets required by the other modules
		# for the if-then-else transformation.
		W_s = set(W_s1 + W_s2)
		T = set(W_s) - set(W_s2)
		E = set(W_s) - set(W_s1)
		I = set(W_s1) & set(W_s2)

		self.W_s[lineno] = W_s
		self.W_s1[lineno] = W_s1
		self.W_s2[lineno] = W_s2
		self.T[lineno] = T
		self.E[lineno] = E
		self.I[lineno] = I
		self.C[lineno] = C

		#self.debug("     W(s): %s" % (','.join(W_s)))
		#self.debug("     W(s'): %s" % (','.join(W_s1)))
		#self.debug("     W(s\"): %s" % (','.join(W_s2)))
		#self.debug("     T(s): %s" % (','.join(T)))
		#self.debug("     E(s): %s" % (','.join(E)))
		#self.debug("     I(s): %s" % (','.join(I)))

		s += t
		s += self._make_indent() + 'else\n'
		s += e

		return s


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


