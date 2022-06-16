""" CSeq Module Example no.3:
	Comment every variable occurrence with details such as:

	scope (local or global),
	arity (0=scalar, >0=array),
	size ([]=scalar, [k] for a vector of size k, [k][h] for an array of size k*h, ...)

"""
import core.module

class example3_variablestats(core.module.Translator):
	def loadfromstring(self,string,env):
		self.comment = ''
		super(self.__class__, self).loadfromstring(string, env)
		self.output = self.comment  # overwrite module's output

	def visit_ID(self,n):
		inputcoords = self._mapbacklineno(self.currentinputlineno)

		# for each ID being parsed,
		# output current coords, function name, etc. 
		self.comment += 'new ID found...\n'
		self.comment += 'filename %s\n' % inputcoords[1]
		self.comment += 'lineno %s\n' % inputcoords[0]
		self.comment += 'function %s\n' % self.currentFunct
		self.comment += 'id %s\n' % n.name

		# if the ID corresponds to a variable name,
		# extract information from the symbol table
		if self._variable(self.currentFunct,n.name):
			scope = None

			# variable scope
			if self._localvariable(self.currentFunct,n.name):
				scope = self.currentFunct
				self.comment += 'local variable\n'
			elif self._globalvariable(self.currentFunct,n.name):
				scope = ''
				self.comment += 'global variable\n'

			# scalar or array?
			self.comment += 'arity %s\n' % self.Parser.varArity[scope,n.name]
			self.comment += 'size %s\n' % self.Parser.varSize[scope,n.name]

		self.comment += '\n'

		return n.name

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
	







	