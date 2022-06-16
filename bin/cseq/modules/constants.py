""" CSeq Program Analysis Framework
    concurrency-aware constant propagation module

Transformation 1 (binary operations, including nested expressions):
e.g. 4 + 3*2  --->  10

Transformation 2:
Simple workaround for expressions that contains global (and thus potentially shared) variables

Author:
    Omar Inverso

Changes:
    2020.11.25  constant variables expansion [SV-COMP 2021] (CSeq 2.1)
    2020.03.25 (CSeq 2.0)
    2019.11.27 [SV-COMP 2020] this module uses the new symbol table in Parser()
    2019.11.27  evaluation of sizeof() (only 32-bit architecture for now)
    2019.11.20 (CSeq 1.9 pycparserext)
    2019.11.20  statement expression workaround to avoid breaking the syntax
    2019.11.16  moved internal parser to pycparserext
    2019.11.15  using __VERIFIER_xyz() primitives rather than __CSEQ_xyz()
    2018.10.28  merged binaryop handling from [ICCPS 2018] constantfolding module
    2018.05.26  handling integer division (when possible) and multiplication
    2017.07.21  started from scratch
    2015.11.07 (CSeq 1.0) [SV-COMP 2016]
    2014.12.24 (CSeq 1.0beta)
    2014.12.09  further code refactory to match the new organisation of the CSeq framework
    2014.10.26 (CSeq Lazy-0.6,newseq-0.6a,newseq-0.6c) [SV-COMP 2015]
    2014.10.26  removed dead/commented-out/obsolete code
    2014.10.15  removed visit() and moved visit call-stack handling to module class (module.py)
    2014.03.14 (CSeq Lazy-0.4)
    2014.03.14  further code refactory to match module.Module class interface
    2014.02.25 (CSeq Lazy-0.2) switched to module.Module base class for modules

To do:
  - urgent: store temporary expression in visit_assignment using the same type, not just 'int' (use Parser macros)
   (this should be possible with the new symbol table)
  - urgent: need full code review
  - urgent: need to move transformation 2 (non-atomicity of binary operations)
            of the sequentialisation stage.
  - only works on integer constants
  - transformation 2 uses int for temporary variables
  - transformation 2 only considers binary operations on the RHS
  - enumerators are constants and could be handled here.

"""
import pycparserext.ext_c_parser, pycparser.c_ast, pycparserext.ext_c_generator
import core.module, core.parser, core.utils
import re


#class MyParser(pycparserext.ext_c_generator.GnuCGenerator):
#	def __init__(self):
#		self.__considervar = ''
#		self.__hasConsidervar = False
#		self.indent_level = 0
#
#	def setConsidervar(self, string):
#		self.__considervar = string
#
#	def getHasConsidervar(self):
#		return self.__hasConsidervar
#
#	def setHasConsidervar(self, value):
#		self.__hasConsidervar = value
#
#	def visit(self, node):
#		method = 'visit_' + node.__class__.__name__
#		ret = getattr(self, method, self.generic_visit)(node)
#		if ret == self.__considervar:
#			self.__hasConsidervar = True
#		return ret


class constants(core.module.Translator):
	deeppropagation = False    # evaluate sizeof (experimental)
	visitingfunction = False   # true while vising a function definition
	visitingcompound = False   # true while visiting a compound

	_tmpvarcnt = 0
	__globalMemoryAccessed = False
	__currentFunction = ''
	__atomicSection = False

	_ids = []   # list of variables potentially accessing the global memory


	def init(self):
		self.inputparam('deep-propagation', 'deep constant folding and propagation (exp)', '', default=None, optional=True)


	def loadfromstring(self, string, env):
		self.deeppropagation = True if self.getinputparam('deep-propagation') is not None else False
		a = super(self.__class__, self).loadfromstring(string, env)


	def visit_FuncDef(self, n):
		self.__currentFunction = n.decl.name
		decl = self.visit(n.decl)

		self.__atomicSection = False
		if n.decl.name.startswith("__VERIFIER_atomic_"):
			self.__atomicSection = True

		self.indent_level = 0

		body = self.visit(n.body)

		self.__currentFunction = ''

		if n.param_decls:
			knrdecls = ';\n'.join(self.visit(p) for p in n.param_decls)
			return decl + '\n' + knrdecls + ';\n' + body + '\n'
		else:
			return decl + '\n' + body + '\n'


	def visit_Assignment(self, n):
		# The original code below breaking statement expressions?!
		#rval_str = self._parenthesize_if(n.rvalue,lambda n: isinstance(n, pycparser.c_ast.Assignment))
		#return '%s %s %s' % (self.visit(n.lvalue), n.op, rval_str)

		oldids = self._ids
		lids = []
		rids = []

		self._ids = []
		lval_str = self.visit(n.lvalue)
		lids = self._ids

		self._ids = []
		rval_str = self._parenthesize_if(n.rvalue, lambda n: isinstance(n, pycparser.c_ast.Assignment))
		rids = self._ids

		commonids = [value for value in lids if value in rids]

		# TODO still wrongly detecting that
		#      the b in a.b and
		#      the b at the right of the assignment are the same identifier
		#     (a weird way of over-approximating..)
		if len(commonids) > 0 and n.op == '=':    # TODO handle +=, ...
			if type(self.stacknodes[-2]) == pycparser.c_ast.Assignment:
				self.warn("nested assignment statements involving potentially unsafe memory accesses")
			else:
				v = commonids[0]

				#self.warn("!!!! %s %s (%s)" % (lval_str, n.op, rval_str))
				#self.warn("!!!! left:[%s] right:[%s] common:[%s]" % (lids,rids,commonids))
				t = self.Parser.buildtype(self.blockid,v)

				if t.endswith(v): t = t[:t.rfind(v)]
				else:
					self.warn("storing temporary expression for '%s' as 'int'" % (t))
					t = 'int'  # TODO (but might still work fine for pointers &co.)

				# Declare a temporary variable for this statement
				semicolon = ';'  # TODO only when visiting a labelled statement
				ret = semicolon
				ret += ' %s __cs_temporary_%s = 0; __cs_temporary_%s = %s; ' % (t,self._tmpvarcnt,self._tmpvarcnt,rval_str)
				ret += '%s %s %s' % (lval_str, n.op, '__cs_temporary_%s' % self._tmpvarcnt)
				self._tmpvarcnt += 1

				#self.warn("[[[ %s ]]]\n\n\n" % ret)
				return ret

		ret = '%s %s (%s)' % (lval_str, n.op, rval_str)

		return ret


	def visit_Compound(self, n):
		old = self.visitingcompound
		self.visitingcompound = True

		s = super(self.__class__, self).visit_Compound(n)

		self.visitingcompound = old

		return s


	def visit_ID(self, n):
		## Find the block (if any) where n was declared.
		#scope = self._blockdefid(self.blockid,n.name)
		#ptr = self._ispointer(self.blockid,n.name)
		#
		#if scope and ptr:
		#	a = self.Parser._generate_type(self.Parser.vars[scope,n.name].type)
		#	self.warn("visiting id [%s,%s] scope:[%s] type:[%s] pointer:[%s]" % (self.blockid,n.name,scope,a,ptr))

		# If this ID corresponds either to a global variable,
		# or to a pointer...
		#
		if ((not self.visitingcompound and not self.visitingfunction and self.Parser.isglobalvariable(self.blockid,n.name) or self.Parser.ispointer(self.blockid,n.name)) and not n.name.startswith('__cs_thread_local_')):
			#self.warn("- - - - - id [%s,%s] potentially accessing global memory" % (self.blockid,n.name))
			#self.__globalMemoryAccessed = True
			self._ids.append(n.name)

		# For constants, replace their id with their actual value,
		# extracted from their declaration.
		m = self.Parser.decl(self.blockid,n.name)

		if m is not None and 'const' in m.quals and type(m.init) == pycparser.c_ast.Constant:
			return super(self.__class__,self).visit(m.init)

		return n.name


	def visit_FuncCall(self, n):
		self.visitingfunction = True

		fref = self._parenthesize_unless_simple(n.name)

		if fref == "__VERIFIER_atomic_begin": self.__atomicSection = True
		elif fref == "__VERIFIER_atomic_end": self.__atomicSection = False

		ret = fref + '(' + self.visit(n.args) + ')'

		self.visitingfunction = False

		return ret


	def visit_BinaryOp(self, n):
		lval_str = self._parenthesize_if(n.left, lambda d: not self._is_simple_node(d))
		rval_str = self._parenthesize_if(n.right, lambda d: not self._is_simple_node(d))

		# remove brackets enclosing constants (e.g. (1234) -> 1234)
		if lval_str.startswith('(') and lval_str.endswith(')') and self._isInteger(lval_str[1:-1]):
			lval_str = lval_str[1:-1]

		if rval_str.startswith('(') and rval_str.endswith(')') and self._isInteger(rval_str[1:-1]):
			rval_str = rval_str[1:-1]

		if self._isInteger(lval_str) and self._isInteger(rval_str):
			if n.op == '-': return str(int(lval_str) - int(rval_str))
			if n.op == '+': return str(int(lval_str) + int(rval_str))
			if n.op == '*': return str(int(lval_str) * int(rval_str))
			if n.op == '/' and (int(lval_str) % int(rval_str) == 0): return str(int(lval_str) / int(rval_str))

		return '%s %s %s' % (lval_str, n.op, rval_str)


	bytewidth = {}
	bytewidth['long'] = 4
	bytewidth['unsigned'] = 4
	bytewidth['signed'] = 4
	bytewidth['int'] = 4

	bytewidth['_Bool'] = 1
	bytewidth['char'] = 1
	bytewidth['short'] = 2
	bytewidth['long'] = 4
	bytewidth['long int'] = 4
	bytewidth['long long'] = 8
	bytewidth['float'] = 4
	bytewidth['double'] = 8
	bytewidth['*'] = 4

	def _simplify_type(self,typestring):
		if typestring.startswith('const '): typestring = typestring.replace('const ', '', 1)
		if typestring.startswith('unsigned '): typestring = typestring.replace('unsigned ', '', 1)
		if typestring.startswith('signed '): typestring = typestring.replace('signed ', '', 1)
		#if typestring.endswith(' *') and typestring.count('*') ==1: typestring = 'int'
		return typestring


	def visit_UnaryOp(self, n):
		operand = self._parenthesize_unless_simple(n.expr)
		if n.op == 'p++':
			return '%s++' % operand
		elif n.op == 'p--':
			return '%s--' % operand
		elif n.op == 'sizeof':
			# Always parenthesize the argument of sizeof since it can be a name.
			expr = self.visit(n.expr)


			#self.warn("-----> sizeof(%s)" % expr)
			a = None
			if self.deeppropagation: a = self._evaluate_sizeof(n.expr)

			if a:
				#self.warn("<----- %s\n\n" % a)
				self.debug("evaluating 'sizeof(%s)' to '%s'" % (expr,a))
				return '%s' % a
			else:
				#self.warn("not evaluating 'sizeof(%s)'" % (expr))
				#self.warn("<----- sizeof(%s)\n\n" % expr)
				return 'sizeof(%s)' % expr
		else:
			return '%s%s' % (n.op, operand)


	''' In order to achieve a deeper program simplification,
		evaluate sizeof().

		This is highly experimental.

		TODO: this assumes 32bits,
		      should add a parameter for 64bit byte width lookup tables for the basic datatypes.
	'''
	def _evaluate_sizeof(self, n, modifiers=[]):
		# This code has not been ported to the v3 framework.
		# Refer to CSeq 2.1 (SV-COMP 2021) for the previous working version.
		return None


	def _isInteger(self, s):
		if s[0] in ('-', '+'): return s[1:].isdigit()
		else: return s.isdigit()


