""" CSeq Module Example no.4:
	Replace non-constant array indexes with temporary variables.

	The output of this module should be a program where
	each array index is either a constant or a variable identifier.

	Example:

	    a[x+123][10];

	is transformed into:

		int __index_0;
		  ...
		__index_0 = x+123;
	    a[__index_0][10];

"""
import core.module
import pycparser

class example4_arrayindexsimplifier(core.module.Translator):
	def loadfromstring(self,string,env):
		self.indexcnt = 0        # count extra variables
		self.assignments = []    # assignment(s) to extra variable(s) for the current statement
		super(self.__class__, self).loadfromstring(string,env)

		# at the end of the tranformation,
		# insert the declarations for the newly added variables
		# at the top of the program
		self.extradeclarations = ''
		for i in range(0,self.indexcnt):
			self.extradeclarations += 'int __index_%s;\n' % (i)

		self.output = self.extradeclarations+self.output 

	def visit(self,n):
 		s = super(self.__class__,self).visit(n)

 		# inserts initialization statement(s) right before
 		# the statement accessing the array
 		x = ''
 		if len(self.stacknodes)>0 and type(self.stacknodes[-1]) == pycparser.c_ast.Compound:
 			x = self.assignments[-1]
 			self.assignments[-1] = ''

		return x+s

	def visit_ArrayRef(self,n):
		arrref = self._parenthesize_unless_simple(n.name)
		index = self.visit(n.subscript)

		# introduce a new variable
		# when the index is not a constant, and
		# store the initialisation statement(s)
		if type(n.subscript) != pycparser.c_ast.Constant:
			self.assignments[-1] += '__index_%s = %s; ' % (self.indexcnt,index)
			index = '__index_%s' % (self.indexcnt)
			self.indexcnt += 1;

		return arrref+'['+index+']'

	def visit_Compound(self, n):
		self.assignments.append('')
		s = super(self.__class__, self).visit_Compound(n)
		self.assignments.pop()
		return s
