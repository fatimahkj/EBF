""" CSeq
	Concurrency-safe Constant Propagation module

	written by Omar Inverso.
"""
VERSION = 'constants-0.0-2019.11.20'  #  CSeq-1.9 pycparserext
#VERSION = 'constants-0.0-2018.10.28'  #
#VERSION = 'constants-0.0-2018.05.26'  #
#VERSION = 'constants-0.0-2017.07.21'  # started from scratch
#VERSION = 'constants-0.0-2015.11.07'  # CSeq-1.0-svcomp2016
#VERSION = 'constants-0.0-2014.12.24'  # CSeq-1.0beta
#VERSION = 'constants-0.0-2014.12.09'
##VERSION = 'constants-0.0-2014.10.26'    # CSeq-Lazy-0.6: newseq-0.6a, newseq-0.6c, SVCOMP15
###VERSION = 'constants-0.0-2014.10.15'
####VERSION = 'constants-0.0-2014.03.14' (CSeq-Lazy-0.4)
#####VERSION = 'constants-0.0-2014.02.25' (Cseq-Lazy-0.2)

"""
	Transformation 1 (binary operations, including nested expressions):
	e.g. 4 + 3*2  --->  10

	Transformation 2:
	Simple workaround for expressions that contains global (and thus potentially shared) variables

Limitations:
	- only works on integer constants
	- transformation 2 uses int for temporary variables
	- transformation 2 only considers binary operations on the RHS

TODO:
	(urgent) need full code review
	(urgent) need to move transformation 2 (non-atomicity of binary operations)
	         to the sequentialisation stage.

Changelog:
	2019.11.20  statement expression workaround to avoid breaking the syntax
	2019.11.16  moved internal parser to pycparserext
	2019.11.15  using __VERIFIER_xyz() primitives rather than __CSEQ_xyz()
	2018.10.28  borrowed visit_binaryop from ICCPS18's basic constantfolding module
	2018.05.26  added translation for integer division (when possible) and multiplication
	2015.10.22  add fix for ldv-races category in SVCOMP16 (Truc)
	2014.12.09  further code refactory to match the new organisation of the CSeq framework
	2014.10.26  removed dead/commented-out/obsolete code
	2014.10.15  removed visit() and moved visit call-stack handling to module class (module.py)
	2014.03.14  further code refactory to match  module.Module  class interface
	2014.02.25  switched to  module.Module  base class for modules

"""
import core.module, core.parser, core.utils
from pycparser import c_ast


class test(core.module.Translator):
	def loadfromstring(self, string, env):
		super(self.__class__,self).loadfromstring(string,env)
		return ''

	def visit_Decl(self,n):
		#ty = c_ast.TypeDecl(declname='_hidden',
		#quals=[],
		#type=c_ast.IdentifierType(['int']))

        #self.declname = declname
        #self.quals = quals
        #self.type = type
        #self.coord = coord
		#t = c_ast.TypeDecl(n.name,n.type)

		#t2 = self.visit(n.type)
		#print("GETTYPE ===== new declaration %s, type %s" % (n.name,  self.Parser.gettype(self.blockid,n.name  )))
		#print("BUIDLTYPE ===== new declaration %s, type %s" % (n.name,  self.Parser.buildtype(self.blockid,n.name  )))

		#print("block: %s" % self.blockid)
		#print("IS GLOBAL? %s (current function: %s)\n\n" % (self.Parser.isglobal(self.blockid,n.name  ),self.currentFunct ))
		#print("QUALS: %s" % (n.quals))
		#print("STORAE: %s" % (n.storage))

		#n.storage.append('static')

		#print("name1: %s" % n.name)

		'''
		if hasattr(n,'type'):
			if hasattr(n.type,'type'):
				if hasattr(n.type.type,'declname'):
					print("name2: %s" % n.type.type.declname)
		'''

		#print("n.name: %s   type:%s" % (n.name,   self.visit(m)))
		#m.declname = 'cazzl'
		#n.show()
		print("is %s a function? %s " % (n.name,self.Parser.isfunction('0',n.name)))

		return super().visit_Decl(n)





