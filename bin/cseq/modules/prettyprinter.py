""" CSeq Program Analysis Framework

	This module doesn't do anything,
	just prints the program back.

Author:
    Omar Inverso

Changes:
    2020.12.13  1st version


"""
import pycparserext.ext_c_parser, pycparser.c_ast, pycparserext.ext_c_generator
import core.module, core.parser, core.utils


class prettyprinter(core.module.Translator):
	def init(self):
		pass


	def loadfromstring(self, string, env):
		super(self.__class__, self).loadfromstring(string, env)


