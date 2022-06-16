""" CSeq Program Analysis Framework
    dowhileconverter module

Removes  do..while  loops and performs lightweight loop transformation:
	- case 1: transform do..while  loops into equivalent  for+while  loops:
						do { block } while (cond)

						-->

						int i;
						for(i=0;i<1;i++){block};  // first iteration without condition check
						while(cond) {block}       // other iterations

              the first loop is bounded and will be executed only once,
              the unroller module should be able to detect this.
              the  for  is introduced as there may be  break  statements in the first iterations,
              thus just copying the  block  code would not work.

	- case 2, transform unbounded  for  loops into equivalent  while  loops:
						for (;;) { block }       -->   while(1) { block }

	- case 3, transform potentially unbounded  for  loops into equivalent  while  loops:
						for (;stmt;) { block }   -->   while(stmt) { block }

Author:
    Omar Inverso

Changes:
    2020.03.24 (CSeq 2.0)
	2019.11.16  fixed translation for labelled statements
    2014.12.24 (CSeq 1.0beta)
    2014.12.09  further code refactory to match the new organisation of the CSeq framework
	2014.06.03  new do..while translation
    2014.06.01 (CSeq Lazy-0.6,newseq-0.6a,newseq-0.6c) [SV-COMP 2015]
	2014.03.14  further code refactory to match module.Module class interface
	2014.02.25 (CSeq lazy-0.2) switched to module.Module base class for modules
	2013.10.19  added transformation of do..while loops
	2013.10.30  commented transformation of for loops

To do:
  - urgent: combine switchtransformer, dowhileconverter, and conditionextractor

"""

import os, sys, getopt, time
import pycparserext.ext_c_parser, pycparser.c_ast, pycparserext.ext_c_generator
import core.module, core.parser, core.utils


class dowhileconverter(core.module.Translator):
	__currentLoop = 0   # count  do..while  loops to introduce unique variables
	visitinglabelledstmt = False


	def visit_Compound(self, n):
		s = self._make_indent() + '{\n'
		self.indent_level += 1

		if n.block_items:
			for stmt in n.block_items:
				newStmt = self._generate_stmt(stmt)
				s += newStmt

		self.indent_level -= 1

		s += self._make_indent() + '}\n'

		return s


	def visit_While(self, n):
		cond = self.visit(n.cond) if n.cond else ''
		block = self._generate_stmt(n.stmt, add_indent=True)

		s = 'while (%s)\n' % cond + block

		return s


	def visit_DoWhile(self, n):
		self.__currentLoop += 1;
		var = '__cs_dowhile_onetime_%s' % self.__currentLoop

		self.indent_level =-1
		block = self._generate_stmt(n.stmt, add_indent=True)
		cond = self.visit(n.cond) if n.cond else ''
		self.indent_level =+1

		# Cannot insert an assignent right after a labelled statement,
		# so insert a semicolon before.
		semicolon = '; ' if self.visitinglabelledstmt else ''
		s = '%sint %s;' % (semicolon,var)
		s += 'for(%s=0;%s<1;%s++)' % (var,var,var) + block
		s += 'while (%s)\n' % self.visit(n.cond) + block

		return s


	def visit_Label(self, n):
		self.visitinglabelledstmt = True
		x = super(self.__class__, self).visit_Label(n)
		self.visitinglabelledstmt = False

		return x


	def visit_For(self, n):
		init = self.visit(n.init) if n.init else ''
		cond = self.visit(n.cond) if n.cond else ''
		next = self.visit(n.next) if n.next else ''
		block = self._generate_stmt(n.stmt, add_indent=True)

		if not n.init and not n.cond and not n.next:  # unbounded for
			s = 'while(1)' + block
		elif not n.init and not n.next:               # potentially unbounded for
			s = 'while(%s)' % cond + block
		else:                                         # potentially bounded for
			s = 'for (%s; %s; %s)' % (init, cond, next) + block

		return s






