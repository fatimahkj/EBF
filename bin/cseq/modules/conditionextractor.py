""" CSeq Program Analysis Framework
    conditionextractor module

Transformation from:

       if (complex_cond) { block }
       while (complex_cond) { block }
       for (init; complex_cond; next) { block }

respectively into:

       _Bool tmp = complex_cond; if (tmp) { block }
       _Bool tmp = complex_cond;  while (tmp) { block; tmp = complex_cond }
       _Bool tmp = complex_cond;  for (init; tmp; next) { block; tmp = complex_cond }

where an expression is considered to be complex iff
it contains calls to functions which body is defined in the source.

Author:
    Omar Inverso

Changes:
    2021.02.11  switching to new symbol table
    2020.03.24 (CSeq 2.0)
    2018.11.20  in a labelled statement, insert a semicolon before a new temporary variable (or the syntax is broken)
    2018.10.28  fixed the way of checking for enclosing brackets (in visit_if, visit_while, visit_for)
    2018.05.26  avoid looking up in parser's stored function bodies, use funcBlockIn instead
    2015.07.17  fix exception call to module.ModuleError (Truc)
    2014.12.24 (CSeq 1.0beta)
    2014.12.09  further code refactory to match the new organisation of the CSeq framework
    2014.06.03 (CSeq Lazy-0.6, newseq-0.6a, newseq-0.6c) [SV-COMP 2015]
    2014.03.14  further code refactory to match  module.Module  class interface
    2014.02.25 (CSeq lazy-0.2) switched to  module.Module  base class for modules

Notes:
  - no  do..while  loops (need to transform them first)

To do:
  - review the whole module, especially the logic for self.funcCallFound
  - urgent: combine switchtransformer, dowhileconverter, and conditionextractor
  - support do..while  loops
    split complex lvalue assignments (etc) containing more than one function calls
    to many individual lvalue assignments each containing one single function call
   (module  inliner  assumes that for each assignment there is at most one function call).

"""

import os, sys
import pycparserext.ext_c_parser, pycparser.c_ast, pycparserext.ext_c_generator
import core.module, core.parser, core.utils


class conditionextractor(core.module.Translator):
	funcCallFound = False
	ifCondCount = whileCondCount = forCondCount = 0
	visitinglabelledstmt = False   # is a labelled statement being visited?


	def visit_If(self, n):
		extraBlock = ''

		s = 'if ('

		if n.cond:
			self.funcCallFound = False
			cond = self.visit(n.cond)

			###if self.funcCallFound == True:
			if True:   # force temporary variables regardless of the complexity of the expression
				#semicolon = ''
				semicolon = '; ' if self.visitinglabelledstmt else ''
				extraBlock = '%s_Bool __cs_tmp_if_cond_%s; __cs_tmp_if_cond_%s = (%s); ' % (semicolon,self.ifCondCount, self.ifCondCount, cond)
				s += '__cs_tmp_if_cond_%s' % (self.ifCondCount)
				s = extraBlock + '\n' + self._make_indent() + s
				self.ifCondCount += 1
			else:
				s += cond

		s += ')\n'

		# always add brackets when missing
		if type(n.iftrue) != pycparser.c_ast.Compound:
			self.indent_level+=1
			t = self._generate_stmt(n.iftrue, add_indent=True)
			self.indent_level-=1
			t = self._make_indent() + '{\n' + t + self._make_indent() + '}\n'
		else:
			t = self._generate_stmt(n.iftrue, add_indent=True)

		s += t

		if n.iffalse:
			s += self._make_indent() + 'else\n'

			# always add brackets when missing
			if type(n.iffalse) != pycparser.c_ast.Compound:
				self.indent_level+=1
				e = self._generate_stmt(n.iffalse, add_indent=True)
				self.indent_level-=1
				e = self._make_indent() + '{\n' + e + self._make_indent() + '}\n'
			else:
				e = self._generate_stmt(n.iffalse, add_indent=True)

			s += e

		return s


	def visit_DoWhile(self, n):
		raise core.module.ModuleError("do..while loop in input code.")


	def visit_Label(self, n):
		self.visitinglabelledstmt = True
		x = super(self.__class__, self).visit_Label(n)
		self.visitinglabelledstmt = False

		return x
		#self.funcLabels[self.currentFunct].append(n.name)
		#return n.name + ':\n' + self._generate_stmt(n.stmt)


	def visit_While(self, n):
		cond = ''
		extraBlock = ''

		s = 'while ('

		if type(n.stmt) != pycparser.c_ast.Compound:
			self.indent_level+=1
			t = self._generate_stmt(n.stmt, add_indent=True)
			self.indent_level-=1
			t = self._make_indent() + '{\n' + t + self._make_indent() + '}\n'
		else:
			t = self._generate_stmt(n.stmt, add_indent=True)

		if n.cond:
			self.funcCallFound = False
			cond = self.visit(n.cond)

			if self.funcCallFound == True:
				extraBlock = '_Bool __cs_tmp_while_cond_%s; __cs_tmp_while_cond_%s = (%s); ' % (self.whileCondCount, self.whileCondCount, cond)
				s += '__cs_tmp_while_cond_%s' % (self.whileCondCount)
				s = extraBlock + '\n' + self._make_indent() + s
				s += ')\n'

				t = t[:t.rfind('}')]
				t = t + self._make_indent() + '__cs_tmp_while_cond_%s = (%s);\n' % (self.whileCondCount, cond)
				t = t + self._make_indent() + '}'

				self.whileCondCount += 1
			else:
				s += cond
				s += ')\n'

		return s + t


	def visit_For(self, n):
		init = cond = next = ''
		extraBlock = ''

		if n.init: init = self.visit(n.init)
		if n.next: next = self.visit(n.next)
		if n.cond: cond = self.visit(n.cond)

		# always add brackets when missing
		if type(n.stmt) != pycparser.c_ast.Compound:
			self.indent_level+=1
			t = self._generate_stmt(n.stmt, add_indent=True)
			self.indent_level-=1
			t = self._make_indent() + '{\n' + t + self._make_indent() + '}\n'
		else:
			t = self._generate_stmt(n.stmt, add_indent=True)

		if n.cond:
			self.funcCallFound = False

			if self.funcCallFound == True:
				extraBlock = '_Bool __cs_tmp_for_cond_%s; __cs_tmp_for_cond_%s = (%s);\n' % (self.forCondCount, self.forCondCount, cond) + self._make_indent()

				t = t[:t.rfind('}')]
				t = t + self._make_indent() + '__cs_tmp_for_cond_%s = (%s);\n' % (self.forCondCount, cond)
				t = t + self._make_indent() + '}'

				cond = '; __cs_tmp_for_cond_%s' % (self.forCondCount)
				self.forCondCount += 1

		s = 'for (%s; %s; %s)' % (init, cond, next)

		return extraBlock + s + t


	def visit_FuncCall(self, n):
		fref = self._parenthesize_unless_simple(n.name)
		args = self.visit(n.args)

		#if fref in self.Parser.funcBlockIn: self.funcCallFound = True
		if ('0',fref) in self.Parser.fbody: self.funcCallFound = True

		inl = fref + '(' + args + ')'

		return inl







