""" CSeq Program Analysis Framework
    spinlock handling module

Remove spinlocks such as:
    while (cond) {}     --->     assume(!cond);
    while (cond) {;}    --->     assume(!cond);
which is safe to do only when  cond   has no side-effects.

Author:
    Omar Inverso

Changes:
    2020.03.24 (CSeq 2.0)
    2019.11.15 (CSeq 1.9) [SV-COMP 2020] pycparserext
    2019.11.15  using __VERIFIER_xyz() primitives rather than __CSEQ_xyz()
    2018.10.28  fixed the way of checking for enclosing brackets (visit_while)
    2014.12.24 (CSeq 1.0beta)
    2014.12.09  further code refactory to match the new organisation of the CSeq framework
    2014.10.02 (CSeq Lazy-0.6,newseq-0.6a,newseq-0.6c) [SV-COMP 2015]
    2014.10.02  added case 2
    2014.03.14  further code refactory to match  module.Module  class interface
    2014.02.25  switched to  module.Module  base class for modules

To do:
  - move to the unrolling or concurrency-handling modules

"""
import os, sys, getopt, time
import pycparserext.ext_c_parser, pycparser.c_ast, pycparserext.ext_c_generator
import core.module, core.parser, core.utils


class spinlock(core.module.Translator):
	__currentLoop = 0
	parsingSideEffect = False   # set when parsing a statement with side effects (i.e., function call, assignment, unary op)


	def visit_FuncCall(self, n):
		self.parsingSideEffect = True

		fref = self._parenthesize_unless_simple(n.name)
		return fref + '(' + self.visit(n.args) + ')'


	def visit_While(self, n):
		#
		# How do we check for side effects?
		#
		# Before visiting a while condition block ( while(....) ),
		# flag self.parsingSideEffect is reset.
		#
		# If after the visit the flag is set, then the condition block
		# contains at least one assignment statement, a unary op or a function call.
		#
		# If after visiting the condition block it is still not set,
		# it means that no assignment stmts, unary ops or function call are present.
		# The flag is in fact set by visit_... methods for each of these ast nodes.
		#
		self.parsingSideEffect = False

		s = 'while ('
		if n.cond: s += self.visit(n.cond)
		#if self.parsingSideEffect: s += ' SIDE EFFECT HERE '
		#else: s+= ' NO SE HERE '
		s += ')\n'

		# always add brackets when missing
		if type(n.stmt) != pycparser.c_ast.Compound:
			self.indent_level+=1
			t = self._generate_stmt(n.stmt, add_indent=True)
			self.indent_level-=1
			t = self._make_indent() + '{\n' + t + self._make_indent() + '}\n'
		else:
			t = self._generate_stmt(n.stmt, add_indent=True)

		# When the while condition has no side effects,
		# and the while block is either the empty statement (;) or the empty block ({}),
		# the following transformation is done:
		#
		#     while (cond) {}     --->     assume(!cond);
		#     while (cond) {;}    --->     assume(!cond);
		#
		if not self.parsingSideEffect:
			if (not n.stmt.block_items) or (
				n.stmt.block_items and len(n.stmt.block_items) == 1 and type(n.stmt.block_items[0]) == pycparser.c_ast.EmptyStatement):  # (case 1) or (case 2)
				s = s.replace('while (', '__VERIFIER_assume(!(', 1)
				s = s[:len(s)-2] + '));\n'
				t = ''

		s += t
		return s


	def visit_UnaryOp(self, n):
		self.parsingSideEffect = True
		return super(self.__class__, self).visit_UnaryOp(n)


	def visit_Assignment(self, n):
		self.parsingSideEffect = True
		return super(self.__class__, self).visit_Assignment(n)








