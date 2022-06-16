""" CSeq C Sequentialization Framework
    Module sketch to understand pycparser's coord tracking capabilities.

Author:
    Omar Inverso

Changes:
    2021.01.04  -

To do:
  -

Notes:
  -

To do:
  -

"""
import core.module
import pycparser


class coords(core.module.Translator):
	def init(self):
		pass

	def loadfromstring(self,string,env):
		super(self.__class__, self).loadfromstring(string,env)
		self.output = ''

	def visit(self,node):
		method = 'visit_' + node.__class__.__name__

		if hasattr(node, 'coord'):
			print("COORDS:%s  TYPE:%s" % (node.coord, type(node)))
		else:
			print("no COORDS   TYPE:%s" % type(node))

		return getattr(self, method, self.generic_visit)(node)










