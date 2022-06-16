""" CSeq Program Analysis Framework
    pre-instrumentation module

    - goto ERROR; ---> assert(0);
    - ERROR :;    ----> assert(0);

Author:
    Omar Inverso

Changes:
	2020.04.10  removed everything except error labels
    2020.03.25 (CSeq 2.0)
    2019.11.15  using __VERIFIER_xyz() primitives rather than __CSEQ_xyz()
    2019.11.15  no longer mapping from pthread_xyz to __cseq_xyz
    2018.10.20  no longer translating function calls to malloc()
    2018.10.20  no longer using core.common for mapping pthread_xyz ids
    2016.11.22  bugfix: false warning with pthread_t_ name
    2015.10.19  bugfix: parsing struct
    2015.07.02  merged with errorlabel-0.0-2015.06.25
    2015.06.25  first version

To do:
  - merge with instrumenter module?

"""
import core.module
import pycparser.c_ast


class preinstrumenter(core.module.Translator):
	__errorlabel = ''

	def init(self):
		self.inputparam('sv-comp', 'SV-COMP2021 mode', '', default=False, optional=True)
		self.inputparam('error-label', 'label for reachability check', 'l', 'ERROR', False)


	def loadfromstring(self, string, env):
		self.svcomp = True if self.getinputparam('sv-comp') is not None else False

		if self.svcomp: self.__errorlabel = ''


		self.__errorlabel = self.getinputparam('error-label')
		super(self.__class__, self).loadfromstring(string, env)


	def visit_Goto(self, n):
		if n.name == self.__errorlabel: return '__VERIFIER_error();' #return '__VERIFIER_assert(0);'
		else: return 'goto ' + n.name + ';'


	def visit_Label(self, n):
		if n.name == self.__errorlabel: return '__VERIFIER_error();' #return '__VERIFIER_assert(0);'
		else: return n.name + ':\n' + self._generate_stmt(n.stmt)


	'''
	def visit_FuncCall(self, n):
		fref = self._parenthesize_unless_simple(n.name)
		args = self.visit(n.args)

		#if fref in self.namesmapping: fref = self.namesmapping[fref]
		#elif fref.startswith('__VERIFIER_atomic_'): fref = '__CSEQ_atomic_'+fref[18:]

		#if fref in self.changeID: fref = self.changeID[fref]
		#if fref == 'malloc':

		return fref + '(' + args + ')'


	def visit_FuncDef(self, n):
		decl = self.visit(n.decl)

		self.indent_level = 0
		body = self.visit(n.body)


		if n.param_decls:
			knrdecls = ';\n'.join(self.visit(p) for p in n.param_decls)
			return decl + '\n' + knrdecls + ';\n' + body + '\n'
		else:
			return decl + '\n' + body + '\n'


	def visit_Decl(self, n, no_type=False):
		#print("declaration [%s] fspec:[%s] nstor:[%s] type:[%s]" % (s,(' '.join(n.funcspec) + ' '),(' '.join(n.storage) + ' '), self._generate_type(n.type)))
		#print("stack: %s\n" % (self.stack))

		# no_type is used when a Decl is part of a DeclList, where the type is
		# explicitly only for the first delaration in a list.
		#
		s = n.name if no_type else self._generate_decl(n)

		#if n.name and n.name.startswith('__VERIFIER_atomic_'):
		#    s = s.replace('__VERIFIER_atomic_', '__CSEQ_atomic_', 1)

		if n.bitsize: s += ' : ' + self.visit(n.bitsize)
		if n.init:
			if isinstance(n.init, pycparser.c_ast.InitList):
				s += ' = {' + self.visit(n.init) + '}'
			elif isinstance(n.init, pycparser.c_ast.ExprList):
				s += ' = (' + self.visit(n.init) + ')'
			else:
				s += ' = ' + self.visit(n.init)

		return s
	'''




