""" CSeq Program Analysis Framework
    loop unfolding module

This module unrolls all the loops up to the given unwind bound.

In this module, loops are handled according to the following categorisation:
	- potentially unbounded loops (i.e.  while  loops)
	- potentially bounded loops (i.e.  for  loops having an upper bound that is not computable)
	- definitely bounded loops (i.e.  for  loops having an upper bound that is exactly computable)

Author:
	Omar Inverso

Changes:
    2020.11.30  loop bound check [SV-COMP 2021] (CSeq 2.1)
    2020.03.24 (CSeq 2.0)
    2019.11.27 [SV-COMP 2020]
    2019.11.15 (CSeq 1.9) pycparserext
    2019.11.15  using __VERIFIER_xyz() primitives rather than __CSEQ_xyz()
    2018.11.28  external option to enable extra transitions on loop condition evaluation (useful to build error traces, but slower analysis)
    2018.11.19  extended handling of loop bounds to non-deterministically bounded loops
    2018.11.19  detection of non-deterministically-bounded for loops
    2016.11.24  now softunwindbound will fully unroll definite bounded loop (cap by unwind-for-max)
    2016.11.18  fixed problem when for does not have next in condition
    2015.10.19  fixed unrolling
    2015.07.14  fixed linemapping
    2015.06.30  major code refactory
    2014.12.24 (CSeq 1.0beta)
    2014.12.09  further code refactory to match the new organisation of the CSeq framework
    2014.10.28 (CSeq Lazy-0.6, newseq-0.6a, newseq-0.6c) [SV-COMP 2015]
    2014.10.28  bugfix (missing if (!cond) goto _exit_loop )
    2014.10.26  new -F loop unwind bounding parameter to limit unrolling of definitely bounded loops
    2014.10.26  removed dead/commented-out/obsolete code
    2014.10.07  continuing the old unroller, not the newest fork (slower but more robust)
    2014.10.07  bugfix (see regression/loop_unroll_*.c)
    2014.02.25  switched to module.Module base class for modules
    2013.10.31  optimisation in this case: for (i=constant_a; i < constant_b; i++) { block-without-access-to-i }

Notes:
  - no  do-while  loops - only  for  or  while  loops (use module remove.py)
  - no single statement blocks (e.g. after if or for, etc..)
  - no break statements used for anything else than for loop exit (e.g. in a switch..case block)
   (use module switchconverter.py)

To do:
  - handle more cases where it is possible to achieve full loop exploration, i.e.,
    extend _calculateLoopBasevalue(), _calculateLoopBound(), and _calculateLoopIncr()
    beyond the base case
  - check for(;;)

"""
import re
import pycparserext.ext_c_parser, pycparser.c_ast, pycparserext.ext_c_generator
import core.module, core.parser, core.utils


class unroller(core.module.Translator):
	__whileunwind = 0

	__sourcecode = ''

	__labelCount = {}

	__loopCount = 0         # loops discovered so far
	__loopDepth = 0         # depth of nesting for loops
	__loopUnwindRound = 0   # current unwinding round for current loop

	__visitingGoto = False

	__lastContinueLabel = ''

	# __labelsDefined = []    # labels defined in the current block being unwound
	# label renaming in unwound loops to avoid duplicating label definitions, and keep in sync with goto stmts
	__labelNew = {}
	__labelToChange = []

	_loopheads = []    # for trace generation
	tmpcondvar = 0

	noextratracking = None


	def init(self):
		self.inputparam('unwind', 'loop depth', 'u', '1', False)
		self.inputparam('unwind-while', 'depth for potentially unbounded loops', 'u', None, True)
		self.inputparam('unwind-for', 'depth for potentially bounded loops', 'u', None, True)
		self.inputparam('unwind-for-max', 'definitely bounded loops (0 = no bound)', 'u', None, True)
		self.inputparam('softunwindbound', 'full unfolding of definitely bounded loops', '', False, True)
		self.inputparam('varnamesmap', 'map variable identifiers to original variable identifiers', '', default=None, optional=True)
		self.inputparam('varscopesmap', 'map variable identifiers to their original scopes', '', default=None, optional=True)
		self.inputparam('extra-tracking', 'mark loop condition checks', '', default=False, optional=True)
		self.inputparam('unwind-check', 'check loop unwinding assertions', '', default=False, optional=True)

		self.outputparam('loopheads') # 1st statements of loops


	def loadfromstring(self, string, env):
		# Set-up unrolling parameters:
		# --unwind has the priority over all others
		self.unwind = int(env.paramvalues['unwind'])

		if not self.unwind: self.unwind = 1   # Default value

		if 'unwind-for' not in env.paramvalues: self.forunwind = self.unwind
		else: self.forunwind = int(env.paramvalues['unwind-for'])

		if 'unwind-for-max' not in env.paramvalues: self.formaxunwind = None
		else: self.formaxunwind = int(env.paramvalues['unwind-for-max'])

		if 'unwind-while' not in env.paramvalues: self.whileunwind = self.unwind
		else: self.whileunwind = int(env.paramvalues['unwind-while'])

		if 'softunwindbound' not in env.paramvalues: self.softunwindbound = False
		else: self.softunwindbound = True

		self.varnamesmap = self.getinputparam('varnamesmap')
		self.varscopesmap = self.getinputparam('varscopesmap')

		#~print "for:%s formax:%s while:%s soft:%s" % (self.forunwind, self.formaxunwind, self.whileunwind, self.softunwindbound)
		if 'extra-tracking' not in env.paramvalues: self.extratracking = False
		else:
			self.extratracking = True
			self.log("enabling extra transitions at loop condition checks")

		if 'unwind-check' not in env.paramvalues: self.unwindcheck = False
		else: self.unwindcheck = True

		super(self.__class__, self).loadfromstring(string, env)
		#print "names - - - -> %s" %str(self.varnamesmap)
		#print "\n\n"
		#print "scope - - - -> %s" %str(self.varscopesmap)
		#print "\n\n"
		#print "varra - - - -> %s" %str(self.Parser.varrange)

		self.setoutputparam('loopheads', self._loopheads)


	''' Checks whether a loop is bound to be executed exactly a fixed number - of times
	   (this only handles the base case for now)
	'''
	def _loopboundfixed(self, n):
		#self.warn("checking a loop bounded by variable %s" % self.visit(n.cond.right))

		if (# init  is an assignment statement of one variable to a constant
			type(n.init) == pycparser.c_ast.Assignment and
			type(n.init.lvalue) == pycparser.c_ast.ID and
			type(n.init.rvalue) == pycparser.c_ast.Constant and

			# cond  is a binary op which left and right parts are a variable and a constant, respectively
			type(n.cond) == pycparser.c_ast.BinaryOp and
			type(n.cond.left) == pycparser.c_ast.ID and
			type(n.cond.right) == pycparser.c_ast.Constant and
			((n.cond.op) == '<' or (n.cond.op) == '<=') and

			# next  is a unary op ++
			type(n.next) == pycparser.c_ast.UnaryOp and
			type(n.next.expr) == pycparser.c_ast.ID and
			((n.next.op) == 'p++' or (n.next.op) == '++') and

			# all the three blocks  init, cond, next  refer to the same variable
			self.visit(n.init.lvalue) == self.visit(n.cond.left) == self.visit(n.next.expr)
			):

			# TODO magicvariable must not be accessed in the  stmt  block
			# TODO no breaks in the  stmt  block
			magicvariable = self.visit(n.init.lvalue)

			return True
		else:
			return False

	def _loopboundoverapprox(self, n):
		#self.warn("checking a loop bounded by non-deterministic variable %s" % self.visit(n.cond.right))
		#print "- - - - > ranges:%s " % str(self.Parser.varrange)
		#print "- - - -> BEFORE: %s, %s" % (self.currentFunct,self.visit(n.cond.right))
		#print "- - - -> AFTER:  %s, %s" % (self.varscopesmap[self.visit(n.cond.right)],self.varnamesmap[self.visit(n.cond.right)])
		#print "- - - -> %s (scope:%s,   name:%s)" % (str(self.Parser.varrange),self.varscopesmap[self.visit(n.cond.right)],self.varnamesmap[self.visit(n.cond.right)])
		right = self.visit(n.cond.right)
		###self.warn("examining symbol %s..." % right)

		# Resolve scope of n.cond.right
		scope = ''

		if right in self.varscopesmap:
			if (self.varscopesmap[right],right) in self.Parser.varrange:
				scope = self.varscopesmap[right]

		###self.warn("symbol <%s>'s scope is <%s>" % (right, scope))


		if (# init  is an assignment statement of one variable to a constant
			type(n.init) == pycparser.c_ast.Assignment and
			type(n.init.lvalue) == pycparser.c_ast.ID and
			type(n.init.rvalue) == pycparser.c_ast.Constant and

			# cond  is a binary op which left and right parts are a variable and a constant, respectively
			type(n.cond) == pycparser.c_ast.BinaryOp and
			type(n.cond.left) == pycparser.c_ast.ID and
			type(n.cond.right) == pycparser.c_ast.ID and
			#self.currentFunct,self.visit(n.cond.right) in self.Parser.varrange and
			(scope,right) in self.Parser.varrange and
			((n.cond.op) == '<' or (n.cond.op) == '<=') and

			# next  is a unary op ++
			type(n.next) == pycparser.c_ast.UnaryOp and
			type(n.next.expr) == pycparser.c_ast.ID and
			((n.next.op) == 'p++' or (n.next.op) == '++') and

			# all the three blocks  init, cond, next  refer to the same variable
			self.visit(n.init.lvalue) == self.visit(n.cond.left) == self.visit(n.next.expr)
			):

			# TODO magicvariable must not be accessed in the  stmt  block
			# TODO no breaks in the  stmt  block
			magicvariable = self.visit(n.init.lvalue)

			return True
		else:
			return False

	def _calculateLoopBasevalue(self, n):
		if self._loopboundfixed(n): return int(n.init.rvalue.value)
		elif self._loopboundoverapprox(n): return int(n.init.rvalue.value)
		else: return None

	def _calculateLoopIncr(self, n):
		if self._loopboundfixed(n): return 1   # TODO
		elif self._loopboundoverapprox(n): return 1    # TODO
		else: return None

	def _calculateLoopBound(self, n):
		if self._loopboundfixed(n):
			value = int(n.cond.right.value) - int(n.init.rvalue.value)

			if n.cond.op == '<=':
				value += 1

			return value
		elif self._loopboundoverapprox(n):
			return 10000

		return None

	'''
	def _calculateLoopBoundApprox(self, n):
		if self._loopboundoverapprox(n):
			return value

		return None
	'''

	def visit_For(self, n):
		# A  for  statement has the following structure:
		#
		#   for (init; cond; next) { block }
		#
		init = self.visit(n.init)
		cond = self.visit(n.cond)
		if cond == '': cond = '1'

		next = self.visit(n.next)

		self.__loopDepth += 1
		self.__loopCount += 1

		currentLoopID = self.__loopCount

		#if self.softunwindbound:
		#	if (self._calculateLoopBound(n) > self.forunwind):
		#		print "softbound useful: %s \n" % self._calculateLoopBound(n)
		#		exit(1)

		#~s = '/* ---------> UNROLLING loop_%s (depth:%s)  <----------------------- */\n' % (self.__loopCount, self.__loopDepth)
		s = self._make_indent() + init + ';\n'

		bound = self.forunwind


		if self.softunwindbound:
			''' Soft unwinding allows for loops to be unfolded beyond the main unwind bound (forunwind).
			    If a loop bound can be worked out, the loop will be fully unfolded.
			    Additionally, an optional parameter (formaxunwind) limits such full unfoldings.
			    If the calculated loop bound is less than formaxunwind, then unnecessary unfoldings
			    are avoided.
			    Note that the loop bound can be over-approximated in case of non-deterministic variables.

			'''
			#self.log("static bound calculating")
			staticbound = self._calculateLoopBound(n)

			if (staticbound is not None):
				if self.formaxunwind: bound = min(staticbound, self.formaxunwind)
				else: bound = staticbound

		#self.warn("unfolding %s times (unwind:%s,maxunwind:%s)" % (bound,self.forunwind,self.formaxunwind))
		try:
			self.debug("unfolding %s iterations loop at line %s" % (bound,self._mapbacklineno(self.currentinputlineno)[0]))
			self._loopheads.append(self._mapbacklineno(self.currentinputlineno)[0])
		except:
			self.debug("unfolding %s iterations loop at line (impossible to map back line numbers)" % bound)
			pass

		for i in range(0, bound):
			self.__loopUnwindRound = i

			# Loop header, repeated at each unwinding round.
			#
			if i == 0: s += self._make_indent() #~+ '/*  - - - - > loop %s, iter = 0 */\n' % currentLoopID
			else: s += self._make_indent()  #~+ '/*  - - - - > loop %s, iter = %s */\n' % (currentLoopID, i);

			#
			#
			if not self.extratracking:
				if self._loopboundfixed(n):
					if i == self._calculateLoopBound(n): break
				else:
					if cond != '1':
						s += self._make_indent() + 'if(!(' + cond + ')) { goto __exit_loop_%s; }\n' % currentLoopID
			########## s += self._make_indent() + 'if(!(' + cond + ')) { goto __exit_loop_%s; }\n' % currentLoopID
			##########s += self._make_indent() + '_Bool __cs_loop_cond_%s = 0; if(!(%s)) { goto __exit_loop_%s; }\n' % (self.tmpcondvar,cond,currentLoopID)  ## 180s fib11 (IV)
			else:
				s += self._make_indent() + '_Bool __cs_loop_cond_%s = %s;  if(!__cs_loop_cond_%s) { goto __exit_loop_%s; }\n' % (self.tmpcondvar,cond,self.tmpcondvar,currentLoopID)  ## 144s fib11 (IV)
				self.tmpcondvar += 1

			# Reset the list of labels before visiting the compound block,
			# after _generate_stmt this list is used to reconstruct
			# .....
			##
			# self.__labelsDefined = []
			self.__labelToChange.append({})

			#
			oldlineslen = len(self.lines) # save the number of entries in self.lines so after the visit() we can rever them back
			block = self._generate_stmt(n.stmt, add_indent=True)
			self.lines = self.lines[:oldlineslen] # revert back self.lines otherwise line mapping won't work properly when duplicating threads

			# Remove the coords of  next  block of the for stmt otherwise the linemarker
			# won't be generated the 2nd time.
			if n.next:
				linenumber = str(n.next.coord.line)
				linenumber = linenumber[linenumber.rfind(':')+1:]
				self.lines.remove(int(linenumber))
				block += self._make_indent() + self.visit(n.next) + ';\n'

			# Duplicate every Label defined in this loop,
			# adding to the label id the current unwind round and the loop number.
			#

			# Update the labels used in goto statements...
			#
			if len(self.__labelToChange[-1]) > 0:
				for l in self.__labelToChange[-1]:
					block = block.replace('goto %s;' % l, 'goto %s;' % self.__labelNew[l])
					# print "> changing in block: \n%s from :%s to %s\n result:%s\n\n\n\n" % (block, old, new, block.replace(old, new))
					# self.__labelsDefined.remove(l)
				self.__labelToChange[-1] = {}   # reset
			self.__labelToChange.pop()

			# Handling of break statements.
			#
			block = block.replace('<break-was-here>', 'goto __exit_loop_%s; ' % currentLoopID)

			# Handling of continue statements.
			#
			if '<continue-was-here>' in block:
				block = block.replace('<continue-was-here>', 'goto __continue_%s_loop_%s;  \n' % (i, currentLoopID))
				s += block + '\n' + self._make_indent() + '__continue_%s_loop_%s: ;\n' % (i, currentLoopID)
			else:
				s += block

		assumeorassert = '__VERIFIER_assert' if self.unwindcheck else '__VERIFIER_assume'

		if not self.extratracking and self.unwindcheck:
			s += self._make_indent() + '__VERIFIER_assert(!(__cs_loop_check & %s)); __exit_loop_%s: ;\n' % (cond, currentLoopID)   # case 3
		elif self.extratracking and not self.unwindcheck:
			s += self._make_indent() + '__VERIFIER_assume(!(%s)); __exit_loop_%s: ;\n' % (cond, currentLoopID)   # case 3
		else:
			s += self._make_indent() + '_Bool __cs_loop_%s = %s; __VERIFIER_assume(!__cs_loop_%s); __exit_loop_%s: ;\n' % (currentLoopID,cond,currentLoopID,currentLoopID)   # case 3

		self.__loopDepth -= 1

		return s


	def visit_DoWhile(self, n):
		self.error("error: unroller.py: do..while loop in input code.\n")


	def visit_While(self, n):
		# A  while  statement has the following structure:
		#
		#   while (cond) { block }
		#
		cond = self.visit(n.cond)

		self.__loopDepth += 1
		self.__loopCount += 1

		currentLoopID = self.__loopCount

		s = '' #~'/* ---------> UNROLLING loop_%s (depth:%s)  <----------------------- */\n' % (self.__loopCount, self.__loopDepth)

		try:
			self.debug("unfolding %s iterations loop at line %s" % (self.whileunwind,self._mapbacklineno(self.currentinputlineno)[0]))
			self._loopheads.append(self._mapbacklineno(self.currentinputlineno)[0])
		except:
			self.debug("unfolding %s iterations loop at line (impossible to map back line numbers)" % bound)
			pass

		for i in range(0, self.whileunwind):
			self.__loopUnwindRound = i

			# Loop header, repeated at each unwinding round.
			#
			if i == 0: s += self._make_indent() #~+ '/*  - - - - > loop %s, iter = 0 */\n' % currentLoopID
			else: s += self._make_indent()  #~+ '/*  - - - - > loop %s, iter = %s */\n' % (currentLoopID, i);

			if cond != '1':
				s += self._make_indent() + 'if(!(' + cond + ')) { goto __exit_loop_%s; }\n' % currentLoopID

			# Reset the list of labels before visiting the compound block,
			# after _generate_stmt this list is used to reconstruct
			# .....
			##
			# self.__labelsDefined = []
			self.__labelToChange.append({})

			oldlineslen = len(self.lines) # save the number of entries in self.lines so after the visit() we can rever them back
			block = self._generate_stmt(n.stmt, add_indent=True)
			self.lines = self.lines[:oldlineslen] # revert back self.lines otherwise line mapping won't work properly when duplicating threads

			# Duplicate every Label defined in this loop,
			# adding to the label id the current unwind round and the loop number.
			#

			# Update the labels used in goto statements...
			#
			if len(self.__labelToChange[-1]) > 0:
				for l in self.__labelToChange[-1]:
					block = block.replace('goto %s;' % l, 'goto %s;' % self.__labelNew[l])
					# print "> changing in block: \n%s from :%s to %s\n result:%s\n\n\n\n" % (block, old, new, block.replace(old, new))
					# self.__labelsDefined.remove(l)
				self.__labelToChange[-1] = {}  # reset
			self.__labelToChange.pop()

			# Handling of break statements.
			#
			block = block.replace('<break-was-here>', 'goto __exit_loop_%s; ' % currentLoopID)

			# Handling of continue statements.
			#
			if '<continue-was-here>' in block:
				block = block.replace('<continue-was-here>', 'goto __continue_%s_loop_%s;  \n' % (i, currentLoopID))
				s += block + '\n' + self._make_indent() + '__continue_%s_loop_%s: ;\n' % (i, currentLoopID)
			else:
				s += block

		s += self._make_indent() + '__VERIFIER_assume(!(%s)); __exit_loop_%s: ;\n' % (cond, currentLoopID)
		#~s += self._make_indent() + '/* --------->       END loop_%s (depth:%s)  <----------------------- */\n' % (currentLoopID, self.__loopDepth)

		self.__loopDepth -= 1

		return s


	def visit_FuncDef(self, n):
		# At each function,
		# reset the label occurrence counters.
		#
		self.__labelCount = {}

		decl = self.visit(n.decl)
		self.indent_level = 0
		body = self.visit(n.body)

		if n.param_decls:
			knrdecls = ';\n'.join(self.visit(p) for p in n.param_decls)
			return decl + '\n' + knrdecls + ';\n' + body + '\n'
		else:
			return decl + '\n' + body + '\n'


	def visit_Label(self, n):
		# Labels defined inside loops need to be renamed
		# to avoid multiple definition of the same label,
		# they are renamed using ........
		#
		#####print "label %s found, depth %s\n" % (n.name, self.__loopDepth)
		if self.__loopDepth > 0 and not self.__visitingGoto:
			# print "found label %s\n" % n.name
			if len(self.__labelToChange) == 0:
				self.error("error: unroller.py contains unknown error.\n")

			if n.name not in self.__labelCount:
				self.__labelCount[n.name] = 0
			else:
				self.__labelCount[n.name] += 1

			oldLabel = n.name
			newLabel = n.name + '_%s' % self.__labelCount[n.name]

			self.__labelNew[oldLabel] = newLabel
			self.__labelToChange[-1][n.name] = True
			return newLabel + ':\n' + self._generate_stmt(n.stmt)
		else:
			return n.name + ':\n' + self._generate_stmt(n.stmt)

	def visit_Goto(self, n):
		self.__visitingGoto = True
		s = 'goto %s;' % n.name
		self.__visitingGoto = False
		return s


	def visit_Continue(self, n):
		return '<continue-was-here>'


	def visit_Break(self, n):
		return '<break-was-here>'












