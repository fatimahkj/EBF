""" CSeq Module Example no.6:
    - a naive, static array bounds check

"""
import core.module
import pycparser

class example6_arraybounds(core.module.Translator):

	def loadfromstring(self,string,env):
		self.comment = ''
		self.indexlevel = 0
		super(self.__class__, self).loadfromstring(string, env)

	def visit_ArrayRef(self, n):
		oldindexlevel = self.indexlevel
		self.indexlevel = self.indexlevel+1

		comment = ''

		arrref = self._parenthesize_unless_simple(n.name)
		index = self.visit(n.subscript)

		# when the index is not a constant value, show a warning message
		if type(n.subscript) != pycparser.c_ast.Constant:
			self.warn("array index [%s] is not a constant, analysys is imprecise" % index)

		# if the ID corresponds to a variable name,
		# extract information from the symbol table
		if self._variable(self.currentFunct,arrref):
			scope = None

			# variable scope
			if self._localvariable(self.currentFunct,arrref):
				scope = self.currentFunct
			elif self._globalvariable(self.currentFunct,arrref):
				scope = ''

			# bounds check
			maxindex = self.Parser.varSize[scope,arrref][self.indexlevel-self.Parser.varArity[scope,arrref]]
			if (index > str(maxindex)):
				raise core.module.ModuleError("index no.%s (i.e. [%s]) for array '%s' must be <%s" % (self.indexlevel-self.Parser.varArity[scope,arrref],index,arrref,maxindex))

		self.indexlevel = oldindexlevel

		return arrref + '[' + index + ']'

	# check whether identifier v is a variable name in function f
	def _variable(self,f,v):
		if self._localvariable(f,v): return True
		elif self._globalvariable(f,v): return True
		else: return False

	# check whether variable v is a local variable of function f
	def _localvariable(self,f,v):
		if v in self.Parser.varNames[f]: return True
		return False

	# check whether variable v is a global variable in function f
	def _globalvariable(self,f,v):
		if v in self.Parser.varNames['']: return True
		return False
	
