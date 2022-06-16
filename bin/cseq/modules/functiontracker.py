""" CSeq Program Analysis Framework
    function tracker module

The purpose of this module is to generate a map
from line numbers in the input file to function identifiers.

The map (inputcoordstofunctions) is used later to build the counterexample
(the inlining will destroy all this information, so we need to store it beforehand).

Author:
    Omar Inverso

Changes:
	2020.03.24 (CSeq 2.0)
    2018.11.08 [SV-COMP 2019] [SV-COMP 2020]
    2018.11.08  new output parameter for the program's entry coords
    2018.10.20  moved atomic section well-nestedness check to workarounds module
    2015.07.02  merged with errorlabel-0.0-2015.06.25
    2015.06.25  forked from preinstrumenter-0.0-2015.06.25 module

"""
import core.module
import pycparser.c_ast


class functiontracker(core.module.Translator):
	currentfunctionname = ''
	inputcoordstofunctions = {}   # map from line numbers to function identifiers
	entrypoint = None


	def init(self):
		self.outputparam('coordstofunctions')
		self.outputparam('entry')   # the program's entry point (i.g. 1st line of main() functiomn)


	def loadfromstring(self, string, env):
		super().loadfromstring(string, env)
		self.setoutputparam('coordstofunctions', self.inputcoordstofunctions)
		self.setoutputparam('entry', self.entrypoint)


	def visit(self,node):
		if hasattr(node, 'coord') and self.currentinputlineno!=0 and self.currentfunctionname!='':
			#print("function %s, coords: %s" % (self.currentfunctionname,self.currentinputlineno))
			#print("function %s, origincoords: %s" % (self.currentfunctionname,self._mapbacklineno(self.currentinputlineno)))
			self.inputcoordstofunctions[self._mapbacklineno(self.currentinputlineno)] = self.currentfunctionname

		if hasattr(node, 'name'):
			if node.name == 'main':
				#print "FOUND!!!!!! line %s type:%s" % (self._mapbacklineno(self.currentinputlineno),type(node))
				self.entrypoint  = self._mapbacklineno(self.currentinputlineno)

		s = super().visit(node)
		return s


	def visit_FuncDef(self,n):
		self.currentfunctionname = n.decl.name
		s = super().visit_FuncDef(n)
		self.currentfunctionname = ''

		return s





