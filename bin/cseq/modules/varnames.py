""" CSeq Program Analysis Framework
    variable renaming module

This module performs variable renaming based on variable scope,
so that no two functions share a variable id after it.

to make function inlining easier:
(doing so avoids future problems with the inliner module, see regression/102,103 )

At the end of the renaming, the map of variable name changes
is available in newIDs (useful for counterexamples,
to translate back variable names to the corrisponding original name).

Transformation:
	int f(int P) {
		int L;
	}

into:
	int f(int __cs_f_P) {
		int __cs_f_L;
	}

Author:
    Omar Inverso

Changes:
	2021.02.05  Migrated to the new block-based symbol table
    2020.03.25 (CSeq 2.0)
    2019.11.13  module almost entirely rewritten from scratch (and got rid of _generate_type())
    2015.07.08  map with variable renames returned as an output parameter
    2014.12.24 (CSeq 1.0beta)
    2014.12.09  further code refactory to match the new organisation of the CSeq framework
    2014.10.27  different prefixes for local variables and function parameters
    2014.10.26 (CSeq Lazy-0.6, newseq-0.6a, newseq-0.6c) [SV-COMP 2015]
    2014.10.26  changed  __stack  to  stack  (to inherit stack handling from module.py)
    2014.10.15  removed visit() and moved visit call-stack handling to module class (module.py)
    2014.03.14  further code refactory to match  module.Module  class interface
    2014.03.08  first version (CSeq Lazy-0.2)

To do:
  - urgent: still need this?
  - make sure the new variables do not shadow existing symbols

"""

import inspect, os, sys, getopt, time
import pycparserext.ext_c_parser, pycparser.c_ast, pycparserext.ext_c_generator
import core.module, core.parser, core.utils


class varnames(core.module.Translator):
	localprefix = '__cs_local_'   # prefix for local variables
	paramprefix = '__cs_param_'   # prefix for function params

	visitingparamlist = False  # visiting the parameters in a function declaration
	visitingstructref = False   # to avoid considering struct fields as local variables
	#visitingfuncdef = False

	varmap = {}          # map from new to old variable names
	                     # (the scope is not an index, as the prefix guarantees the new id to be unique)

	varscope = {}        # scopes of new variable ids

	varmapreverse = {}   # map of old variable names and scopes to new variable names
	                     # (here the scope is an index as the id may not be unique)


	def init(self):
		super().extend()
		self.outputparam('varnamesmap')
		self.outputparam('varscopesmap')


	def loadfromstring(self, string, env):
		super().loadfromstring(string, env)
		self.setoutputparam('varnamesmap', self.varmap)
		self.setoutputparam('varscopesmap', self.varscope)


	def visit_Decl(self, n, no_type=False):
		#print("--> visiting decl:[%s]  scope:[%s]" % (n.name,self.currentFunct))
		#print("     stack: "+  str(self.stack) + '   prev:' + str(self.stack[len(self.stack)-2]))

		# Detect declaration of function parameters
		if self.currentFunct != '' and self.visitingparamlist:
			newname = self.paramprefix + self.currentFunct + '_' + n.name
			self.varmap[newname] = n.name
			self.varscope[newname] = self.currentFunct
			self.varmapreverse[self.currentFunct,n.name] = newname
			oldid = self.changeid(n,newname)

		# Detect declaration of local variables
		if self.currentFunct != '' and not self.visitingparamlist and n.name and not self.currentFunct==n.name:
			newname = self.localprefix + self.currentFunct + '_' + n.name
			self.varmap[newname] = n.name
			self.varscope[newname] = self.currentFunct
			self.varmapreverse[self.currentFunct,n.name] = newname

			###print("::::::")
			###print(self.Parser.fblock)
			###print(":::::::")

			###print("AAA index1: [%s]      index2: [%s]" % (self.currentFunct,n.name))
			###blkid = self.Parser.blockdefid(self.Parser.fblock[self.currentFunct],n.name)
			###print("AAA looking up [%s] block id [%s]" % (n.name,blkid))
			####print("ABC (B) obtaining declnode for [%s,%s] ----> %s" % (self.Parser.fblock[self.currentFunct],n.name,blkid))
			#blkid = self.Parser.blockdefid(self.blockid,n.name)
			#print("ABC (B) obtaining declnode for [%s,%s] ----> %s" % (self.blockid,n.name,blkid))

			oldid = self.changeid(n,newname)

		return super(self.__class__,self).visit_Decl(n)


	def visit_ParamList(self,n):
		oldvisitingparam = self.visitingparamlist
		self.visitingparamlist = True

		out = ''
		for i, p in enumerate(n.params):
			spacer = '' if i==0 else ', '
			out += spacer + self.visit(p)

		#return ', '.join(self.visit(param) for param in n.params)
		self.visitingparamlist = oldvisitingparam

		return out


	def visit_StructRef(self,n):
		sref = self._parenthesize_unless_simple(n.name)
		oldvisitingStructRef = False
		self.visitingstructref = True
		retval = sref + n.type + self.visit(n.field)
		self.visitingstructref = 	oldvisitingStructRef
		return retval


	def visit_ID(self,n):
		###print("ABC --> visiting id:[%s]   scope:[%s]   block:[%s]" % (n.name,self.currentFunct,self.blockid))
		#if self.currentFunct != '' and n.name in self.Parser.varNames[self.currentFunct] and not self.visitingstructref:
		boh = self.Parser.blockdefid(self.blockid,n.name)

		if self.currentFunct != '' and boh is not None and not self.Parser.isglobalvariable(boh,n.name) and not self.visitingstructref:
			if (self.currentFunct,n.name) in self.varmapreverse:
				varid = super().visit_ID(n)
				###print("ABC --> BEFORE %s" % n.name)
				n.name = self.varmapreverse[self.currentFunct,n.name]
				###print("ABC --> AFTER %s" % n.name)

		return super().visit_ID(n)


	''' Change the identifier in the sub-AST rooted at n to be newid.
	'''
	def changeid(self,n,newid):
		# In the base case (i.e., int x) the loop below will
		# terminate immediately after one iteration.
		#
		# For more complex expressions,
		# go through any pointer declaration (e.g., int *x), or
		# array declaration (e.g., int a[][]), until
		# a c_ast.TypeDecl node is found.
		#
		scan = n

		while type(scan.type) != pycparser.c_ast.TypeDecl:
			scan = scan.type

		oldid = scan.type.declname
		scan.type.declname = newid

		return oldid


