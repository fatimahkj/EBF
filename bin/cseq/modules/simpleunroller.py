""" CSeq C Sequentialization Framework
	loop unfolding module - basic version

	written by Omar Inverso.
"""
VERSION = 'simpleunroller-0.0-2017.03.01'    # re-introduced unwind bound
#VERSION = 'simpleunroller-0.0-2016.12.21'
#VERSION = 'unroller-0.0-2016.11.25'
#VERSION = 'unroller-0.0-2015.07.14'
#VERSION = 'unroller-0.0-2015.06.30'
#VERSION = 'unroller-0.0-2014.12.24'    # CSeq-1.0beta
#VERSION = 'unroller-0.0-2014.10.28'    # CSeq-Lazy-0.6: newseq-0.6a, newseq-0.6c, SVCOMP15
#VERSION = 'unroller-0.0-2014.10.26'
#VERSION = 'unroller-0.0-2014.10.07'     # this continues the old unroller, not the newest fork (slower but more robust)
#VERSION = 'unroller-0.0-2014.02.25'       !NOTE! code fork to try different unrolling (see )

"""

This module unrolls all  for  loops up to the given unwind bound.

Prerequisites:
	- no continue, break, labels, goto statements
	- no other loops than  for  loops

TODO:
	- make sure that  magicvariable  is never written in the  stmt  block (and that no pointers are used)
	- check for(;;)

Changelog:
	2016.12.21  first version

"""

import re
import pycparser.c_parser, pycparser.c_ast, pycparser.c_generator
import core.common, core.module, core.parser, core.utils


class simpleunroller(core.module.Translator):
	unwind = None                # unwinding bound for all loops
	unwindingassertions = None   #
	partialunwinding = None      #

	__loopID = []                # e.g. [0,1] -> 2nd internal loop within 1st external loop

	__loopDepth = 0              # depth of nesting for loops
	__oldloopDepth = 0

	__loopindex = None           # variable identifier used as index for the current loop
	__loopindexes = []           # variable identifiers (stack-like) for all loops currently being unrolled

	__loopindexvalue = 0         # current unwinding round for the loop currently unrolled
	__loopindexvalues = []       # current unwinding rounds for all loops currently being unrolled


	def init(self):
		self.inputparam('unwind', 'loop unwind bound', 'u', '0', False)
		self.inputparam('no-unwinding-assertions', 'do not insert loop unwinding assertions', '', False, True)
		self.inputparam('partial-unwinding', 'allow partial unwinding of statically bounded loops', '', False, True)


	def loadfromstring(self, string, env):
		self.unwind = int(self.getinputparam('unwind'))
		self.unwindingassertions = False if 'no-unwinding-assertions' in env.paramvalues else True
		self.partialunwinding = True if 'partial-unwinding' in env.paramvalues else False
		super(self.__class__, self).loadfromstring(string, env)


	def visit_For(self,n):
		incomplete = False  # complete unfolding of (statically bounded) loop?

		# work out the loop bound
		bound = self._calculateLoopBound(n) # this also sets some variables (such as magicvariable)

		'''
		if bound is None and self.unwind == 0: self.error('unable to calculate static loop bound (please use --unwind).', True)
		elif bound is None and self.unwind != 0:
			if not self.partialunwinding:
				self.error('unable to calculate static loop bound, please use --partial-unwinding')		
			else:
				self.warn('unable to calculate static loop bound, analysis may be incomplete')
				incomplete = True
				bound = self.unwind
		'''
		if bound is None: self.error('statically unbounded loops not supported.')
		elif bound is not None and self.unwind != 0:
			if self.unwind<bound and not self.partialunwinding:
				self.error('please use --partial-unwinding or at least --unwind %d for complete loop unfolding' % bound, True)
			elif self.unwind<bound and self.partialunwinding:
				self.warn('please use at least --unwind %d for complete loop unfolding' % bound)
				incomplete = True
				bound = bound = min(self.unwind,bound)
		elif bound is not None and self.unwind == 0: pass
		
		self.__loopindexes.append(self.__loopindex)
		self.__loopindexvalues.append(0)

		# A  for  statement has the following structure:
		#
		#   for (init; cond; next) { stmt }
		#
		init = self.visit(n.init)
		cond = self.visit(n.cond)
		if cond == '': cond = '1'

		self.__loopDepth += 1

		# work out the identifier of the current loop
		if self.__oldloopDepth == self.__loopDepth:  self.__loopID[-1] = str(int(self.__loopID[-1])+1)
		elif self.__oldloopDepth < self.__loopDepth: self.__loopID.append(str(0))
		elif elf.__oldloopDepth > self.__loopDepth:  self.__loopID.pop()

		oldloopIDs = self.__loopID
		loopID = '_'.join(self.__loopID)

		s = ''
		s += init + ';\n'

		for i in range(0,bound):
			self.__loopindexvalue = i
			self.__loopindexvalues[-1] = i

			# concatenate the loop body to the output
			oldlineslen = len(self.lines) # save the number of entries in self.lines so after the visit() we can revert them back
			block = self._generate_stmt(n.stmt, add_indent=False)
			''' TODO broken
			block = re.sub(r' *(.*)', r'\1', block)        # remove initial spaces..
			if block.startswith('{\n'): block = block[2:]  # ..and encloding compound brackets
			if block.endswith('}\n'): block = block[:-2]   # 
			'''
			s += block
			self.lines = self.lines[:oldlineslen] # revert back  self.lines  otherwise line mapping may not work properly (for example when duplicating threads)

			# update index for next iteration
			s += self.visit(n.next) + ';\n'

		'''
		if self.unwind!=0:
			if incomplete
				if self.unwindingassertions:
					#s += self._make_indent() + 'assert(!(%s)); __exit_loop_%s: ;\n' % (cond,loopID)
					s += 'assert(!(%s));' % (cond)
				#else:
					####s += self._make_indent() + '__exit_loop_%s: ;\n' % (loopID)
					#s += self._make_indent() + '\n'
			#else:
				#####s += self._make_indent() + '__exit_loop_%s: ;\n' % (loopID)
				#s += self._make_indent() + '\n'

		#if self.unwind==0:
			#s += self._make_indent() + '__exit_loop_%s: ;\n' % (loopID)
			####s += self._make_indent() + '\n'
		'''
		if self.unwind!=0 and incomplete and self.unwindingassertions:
			s += 'assert(!(%s));' % (cond)

		self.__loopID = oldloopIDs

		self.__oldloopDepth = self.__loopDepth
		self.__loopDepth -= 1
		self.__loopindexes.pop()
		self.__loopindexvalues.pop()

		return s


	def visit_Break(self,n): self.error('break statements not supported.', True)
	def visit_Continue(self,n): self.error('continue statements not supported.', True)
	def visit_DoWhile(self,n): self.error("do..while loops not supported.", True)
	def visit_Goto(self,n): self.error('goto statements not supported.', True)
	def visit_Label(self,n): self.error('labels not supported.', True)
	def visit_While(self,n): self.error("while loops not supported.", True)


	''' Checks whether a loop is bound to be executed exactly a fixed number of times
	   (this only handles the base case for now, i.e., i=0;i<max;i++)
	'''
	def _loopIsBounded(self,n):
		if (# init  is an assignment statement of one variable to a constant
			type(n.init) == pycparser.c_ast.Assignment and
			type(n.init.lvalue) == pycparser.c_ast.ID and
			type(n.init.rvalue) == pycparser.c_ast.Constant and

			# cond  is a binary op which left and right parts are a variable and a constant, respectively
			# TODO op must be '<'
			type(n.cond) == pycparser.c_ast.BinaryOp and
			type(n.cond.left) == pycparser.c_ast.ID and
			type(n.cond.right) == pycparser.c_ast.Constant and
			(n.cond.op) == '<' and

			# next  is a unary op ++
			type(n.next) == pycparser.c_ast.UnaryOp and
			type(n.next.expr) == pycparser.c_ast.ID and
			(n.next.op) == 'p++' and

			# all the three blocks  init, cond, next  refer to the same variable
			self.visit(n.init.lvalue) == self.visit(n.cond.left) == self.visit(n.next.expr)
			):

			# TODO make sure that magicvariable is never written in the  stmt  block, and
			#      that no dereferences are used (otherwise magicvariable might be
			#      written anyway)
			#
			magicvariable = self.visit(n.init.lvalue)
			self.__loopindex = magicvariable
			return True
		else:
			return False


	def _calculateLoopBasevalue(self,n):
		if self._loopIsBounded(n): return int(n.init.rvalue.value)
		else: return None

	def _calculateLoopBound(self,n):
		if self._loopIsBounded(n): return int(n.cond.right.value)
		else: return None

	def _calculateLoopIncr(self,n):
		if self._loopIsBounded(n): return 1;
		else: return None


