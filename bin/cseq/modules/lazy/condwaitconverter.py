""" CSeq Program Analysis Framework
    lazy sequentialisation: wait converter module

Simply split __cs_cond_wait() into two separate function calls,
to add one context-switch point in __cs_cond_wait().
This allows the lazyseq module to insert a context-switch pount in the middle.

Author:
	Omar Inverso

Changes:
	2020.04.26  the call being transformed can occur within a complex expression
    2020.03.24 (CSeq 2.0)
    2019.11.23 [SV-COMP 2020] bugfix: avoid inserting newlines as they break linemapping
    2019.11.15 (CSeq 1.9) pycparser
    2019.11.15  no longer mapping pthread_xyz function identifiers (and using consistent names for cont_wait_1 etc.)
    2016.10.05  add support for pthread barrier wait function call (experimental)
    2015.07.10  1st version

To do:
	- this pass should be merged into the lazy schema

"""
import pycparserext.ext_c_parser, pycparser.c_ast, pycparserext.ext_c_generator
import core.module, core.parser, core.utils


class condwaitconverter(core.module.Translator):
	prefix = None

	def visit_Compound(self, n):
		s = self._make_indent() + '{\n'
		self.indent_level += 2

		if n.block_items:
			for stmt in n.block_items:
				s += self._generate_stmt(stmt)

				if self.prefix:
					s = self.prefix + s
					self.prefix = None

		self.indent_level -= 2
		s += self._make_indent() + '}\n'

		return s


	def visit_FuncCall(self, n):
		fref = self._parenthesize_unless_simple(n.name)

		if (fref == 'pthread_cond_wait' or fref == 'pthread_cond_timedwait'):
			c = self.visit(n.args.exprs[0])
			m = self.visit(n.args.exprs[1])

			out = ''

			# For nested expressions (e.g., int x = pthread_cond_wait()),
			# keep the first call (to pthread_cond_wait_1) for the innermost
			# compound statement, such that it can be inserted right after the
			# statement.
			if self.stack[-2] == 'Compound':
				out += 'pthread_cond_wait_1(%s,%s); ' % (c,m)
			else:
				self.prefix = 'pthread_cond_wait_1(%s,%s); ' % (c,m)

			out += 'pthread_cond_wait_2(%s,%s)' % (c,m)
			return out

		if (fref == 'pthread_barrier_wait'):
			c = self.visit(n.args)

			out = ''

			# See above.
			if self.stack[-2] == 'Compound':
				out += 'pthread_barrier_wait_1(%s); ' % (c)
			else:
				self.prefix += 'pthread_barrier_wait_1(%s); ' % (c)

			out += 'pthread_barrier_wait_2(%s);' % (c)
			return out

		return super(self.__class__, self).visit_FuncCall(n)


