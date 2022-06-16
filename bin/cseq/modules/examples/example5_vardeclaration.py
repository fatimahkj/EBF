""" CSeq Module Example no.5:
	Change to  unsigned int  the type of every variable declared as  int.

	Example:

	int v; --> unsigned int v;

"""
import core.module

class example5_vardeclaration(core.module.Translator):
	def loadfromstring(self,string,env):
		self.comment = ''
		super(self.__class__, self).loadfromstring(string, env)

	def visit_Decl(self,n,no_type=False):
		s = super(self.__class__, self).visit_Decl(n,no_type)
		extra = ''

		if n.name and n.name in self.Parser.varNames[self.currentFunct]:
			if self.Parser.varType[self.currentFunct,n.name] == 'int':
				extra = 'unsigned '

		return extra+s
