""" CSeq Module Example no.2:
	changes function calls from one function to another one.
"""
import core.module

class example2(core.module.Translator):
	def init(self):
		self.inputparam('oldname','original function','s','a',False)
		self.inputparam('newname','new function','d','b',False)

	def loadfromstring(self, string, env):
		self.oldname = self.getinputparam('oldname')
		self.newname = self.getinputparam('newname')

		super(self.__class__, self).loadfromstring(string, env)

	def visit_FuncCall(self,n):
		fref = self._parenthesize_unless_simple(n.name)
		args = self.visit(n.args)

		if fref == self.oldname:
			fref = self.newname

		return fref + '(' + args + ')'

