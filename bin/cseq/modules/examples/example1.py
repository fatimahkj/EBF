""" CSeq Module Example no.1:
	Converts any expression of the kind 'x++'
	to 'x = x + 1'
"""
import core.module

class example1(core.module.Translator):
	def visit_UnaryOp(self, n):
		if n.op == 'p++':
			id = self._parenthesize_unless_simple(n.expr)
			return '%s = %s + 1' % (id, id)
		
		return super(example1,self).visit_UnaryOp(n)

