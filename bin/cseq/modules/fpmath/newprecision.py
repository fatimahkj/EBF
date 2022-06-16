""" CSeq C Sequentialization Framework
    Analysis of discontuinity errors under fixed-point arithmetics.

Author:
    Omar Inverso

Purposes of this module:
  - extract the precision of each fixed-point variable

Changes:
    2020.12.12  implemented from scratch (forked from newrange.py, and divided from it)

Assumptions:
  - no global variables
  - no function calls (need inlining first)
  - ids ending with __ denote a fixed-point variable
  - a fixed-point variable is declared as x__P_Q__, where
    P and Q denote its integer and fractional precision, respectively.
  - no side effect within array indexes (e.g. a[++i))

Notes:
  - no support for unsigned arithmetics (i.e., no sign)
  - costant operands in a binary operation are assumed to be in the same precision as the other operand
   (might refine this in the future)
  - the precision and error variable maps are output to next modules;
    the next modules need to maintain such maps
   (e.g., when new variables are added).

"""
import core.module
import pycparser


class newprecision(core.module.Translator):
	precision = {}  # precision (i,f) for a fixed-point variable (blockid,id)
	errorvar = {}   # identifier of the error variable of each fp variable
	sign = {}       # signedness of the error variable of each fp variable (1 means signed)

	bitwidth = {}   # custom bitwidth for specific int variables, e.g. ['main','var'] = 4
	errorvar = {}   # identifier of the error variable of each fp variable

	_tmpvarcnt = 0

	maxp = 0
	maxq = 0


	def init(self):
		self.inputparam('error-i', 'error precision integer part', 'i', default='1', optional=False)
		self.inputparam('error-f', 'error precision fractional part', 'f', default='1', optional=False)
		self.inputparam('error-bound', 'max no. of bits allowed for the propagated error', 'e', default=1, optional=False)

		self.outputparam('precision')
		self.outputparam('bitwidth')
		self.outputparam('sign')
		self.outputparam('errorvar')
		self.outputparam('tmpvarcnt')
		self.outputparam('error-i')
		self.outputparam('error-f')
		self.outputparam('errorbound')


	def loadfromstring(self,string,env):
		self.error_i = int(self.getinputparam('error-i'))
		self.error_f = int(self.getinputparam('error-f'))
		self.errorbound = int(self.getinputparam('error-bound'))

		super(self.__class__, self).loadfromstring(string, env)

		for (block,var) in self.precision:
			(p,q) = self.precision[block,var]
			self.maxp = max(self.maxp,p)
			self.maxq = max(self.maxq,q)

		if self.error_i < self.maxp:
			self.error("need to increase error precision from (%s.%s) to (%s.%s) to match overall max variable integer precision" % (self.error_i,self.error_f,self.maxp,self.error_f))
			self.error_i = self.maxp

		if self.error_f < self.maxq:
			self.error("need to increase error precision from (%s.%s) to (%s.%s) to match overall max variable fractional precision" % (self.error_i,self.error_f,self.error_i,self.maxq))
			self.errorbound += self.maxq-self.error_f
			self.error_f = self.maxq
			self.error("adjusting error bound to (%s) accordingly" % (self.errorbound))

		self.setoutputparam('precision',self.precision)
		self.setoutputparam('bitwidth',self.bitwidth)
		self.setoutputparam('sign',self.sign)
		self.setoutputparam('errorvar',self.errorvar)
		self.setoutputparam('tmpvarcnt',self._tmpvarcnt)
		self.setoutputparam('error-i',self.error_i)
		self.setoutputparam('error-f',self.error_f)
		self.setoutputparam('errorbound',self.errorbound)


	def visit_ID(self,n):
		n = super(self.__class__, self).visit_ID(n)

		if n.endswith('__') and self._varprecision(self.blockid,n) == (None,None):
			self.error('undeclared fixed-point variable (%s)' %n, snippet=True)

		return n


	def visit_Decl(self,n,no_type=False):
		s = n.name if no_type else self._generate_decl(n)

		if s.startswith("fixedpoint ") or s.startswith("__cs_fixedpoint ") or s.startswith("ufixedpoint "):
			# Populate self.precision so that from now on isfixedpoint() can be used.
			######if n.init: self.error("init expression for variable (%s) ignored" % (n.name))
			if n.bitsize: self.error("bitsize not allowed for expression variable (%s)" % (n.name))

			if n.name.endswith('__'):
				try:
					(i,f) = [int(j) for j in n.name.split('_')[2:4]]
					self.precision[self.blockid,n.name] = (i,f)

					self.debug("Adding precision: %s,%s for variable %s block %s" % (i,f,n.name,self.blockid))
					#self.sign[self.blockid,n.name] = 0
					assert(i!=None and i!='' and i>=0)
					assert(f!=None and f!='' and f>=0)
				except Exception as e:
					self.error('unable to extract precision of fixed-point variable (%s), please use variable name suffix __i_f__ to declare precision:' % n.name, snippet=True)

				# Set the bitwidth of the variable as the sum of
				# the widths of the integer part and the fractional part, so
				# during the instrumentation they can be re-declared as
				#  s of appropriate size.
				(i,f) = self.precision[self.blockid,n.name]

				if s.startswith("ufixedpoint "): self.sign[self.blockid,n.name] = 0
				else: self.sign[self.blockid,n.name] = 1

				# [ICCPS2017] Unsigned variables need one extra bit to avoid sign extension.
				#if not self.sign[self.blockid,n.name]: self.bitwidth[self.blockid,n.name] = int(i)+int(f)+1
				#else: self.bitwidth[self.blockid,n.name] = int(i)+int(f)
				self.bitwidth[self.blockid,n.name] = int(i)+int(f)
		return super(self.__class__, self).visit_Decl(n,no_type)



	def _varprecision(self,block,var):
		if (self.Parser.blockdefid(block,var),var) in self.precision:
			return self.precision[self.Parser.blockdefid(block,var),var]

		#self.warn("unable to extract precision for variable %s, please double check declaration" % var)
		return (None,None) # might be a constant














