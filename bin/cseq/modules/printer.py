""" CSeq
	Pretty printing module

	written by Omar Inverso.
"""
VERSION = 'printer-2021.01.29'

"""

Changelog:
	2021.01.29  1st version

"""
import core.module, core.parser, core.utils


class printer(core.module.Translator):
	def loadfromstring(self,string,env):
		a = super(self.__class__, self).loadfromstring(string,env)
		print(a)




