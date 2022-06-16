""" CSeq Program Analysis Framework
    new function inlining module

Transformations:
	- inlining of all the function calls,
	  for functions which body is defined (except main() and __CSEQ_atomic_ functions)

	- in threads:
		- pthread_exit;  are converted into  goto thread_exit;  (pthread_exit() argument is ignored)
		- return;  and  return value;  are converted into  goto thread_exit;  (return value is ignored)

Authors:
	Omar Inverso (new inlining)
	Omar Inverso and Gennaro Parlato, University of Southampton (early version up to 2014)

Changes:
	2021.02.13 (Cseq 3.0)
    2021.02.07  disabled simplification of parameter passing (not ported to new symbol table)
    2021.02.05  no longer using Parser.varNames (old symbol table)
    2020.03.28 (CSeq 2.0)
    2020.03.28  block-based symbol table lookup (e.g., isglobal(), etc.)
    2019.11.27 [SV-COMP 2020]
    2019.11.27  bugfix: simplied argument passing of pointers for nested functions
    2019.11.24  simplified inlining when passing global variables or constants
    2019.11.20  variadic functions supported by only passing the fixed argument(s)
    2019.11.15 (CSeq 1.9) pycparserext
    2019.11.15  using __VERIFIER_xyz() primitives rather than __CSEQ_xyz()
    2018.11.25  new external flat to activate pointer simplification when inlining function calls (--simplify-args)
    2018.11.24  terminating when detecting nested function calls to inline
    2018.11.22  pointer simplification in passing local variables to inlined function calls (unstable, disabled)
    2018.11.22  removed non-deterministic initialisation of static variables (as a consequence of previous change below)
    2018.11.22  removed non-generic transformation of local variables (e.g. transforming variables into static, which is only needed for sequentialisation)
    2018.11.22  fully AST-based passing of parameters of inlined functions (replaces string-based version)
    2018.11.20  do not insert an atomic section for passing parameters (--atomic-parameters) when function takes no arguments
    2018.11.03  no longer using Parser.funcReferenced to check whether a function definition should disappear
    2018.11.03  rewritten method to check whether a functions needs to be inlined (needsinlining)
    2018.11.03  make sure that the parameters of a function call match the declaration of the function
    2018.10.29  fixed conversion of local const variables to static (rather than to static const).
    2018.05.26 (CSeq 1.5-parallel) [PPoPP 2020]
    2018.05.26  improved inlining of void functions, or functions with single exit points (i.e., a unique final return statement)
    2018.04.26 [SV-COMP 2016] to [SV-COMP 2018]
    2016.12.02  add option to keep parameter passing atomic
    2016.10.05  don't want to use __cs_init_scalar on pthread types (see initVar function)
    2016.09.27  fix bug: problem of init dynamic size array
    2016.09.27  fix bug: multiple inline of two functions use the same (global) variable as parameter
    2016.09.16  add option to keep static array declaration (no cast to pointer)
    2016.08.16  __cs_init_scalar less ubiquitous
    2015.10.19  fix in _inlineFunction
    2015.07.16  fix inlining function in a label statement (Truc)
    2015.07.15  fixed linemapping for inlined function blocks + expanded parameter passing (Truc)
    2014.12.24 (CSeq 1.0beta)
    2014.12.09  further code refactory to match the new organisation of the CSeq framework
    2014.10.31 (CSeq Lazy-0.6, newseq-0.6a, newseq-0.6c) [SV-COMP 2015]
    2014.10.31  bugfix: when dealing with expressions such as: if(!f(x)) would inline the function twice
    2014.10.28  inlining optimization: ....
    2014.03.14  further code refactory to match  module.Module  class interface
    2014.03.09  bugfix: external module  varnames.py  to fix regression overlapping variable names (see regression/102,103 )
    2014.03.06 (CSeq Lazy-0.2)
    2014.03.06  bugfix: inliner wrong handling array as parameters (see regression/100_inline_struct_array.c)
    2014.02.27  improved indentation in inlined blocks
    2014.02.25  switched to  module.Module  base class for modules
    2013.12.02  bugfix: local struct variables not converted into static struct variables (e.g. struct a --> static struct a;)
    2013.10.24 (Gennaro-Omar) first version

Notes:
  - no function calls in if, while, for conditions (e.g. if(f(g)), while(cond), ...) ???
   (use module extractor.py)
  - no overlapping variable names as in regression testcase 102
   (use module varnames.py)
  - pthread_exit() parameter is ignored
  - no two function in the same expression, nested, e.g.: g(f(x));

To do:
  - urgent: fix crashes with some variadic functions
  - urgent: remove the (remaining few) sequentialisation-specific transformations to the sequentialisation module
  - urgent: parameter simplifyargs should control the whole simplification part (now something is done anyway)
  - not urgent: pointer elimination in passed function parameters should be done in a separate module, compositional, and compound-based
  - handle function pointers as parameters for functions to be inlined
  - limit recursion depth (otherwise parsing recursive functions will give a python stack overflow)
  - handle nested function calls. f(g(x)):  g(x) is in n.args therefore at the moment would not be inlined?
  - rename labels (& corresponding gotos) in inlined blocks of code to avoid label duplication
   (use Parser.self.funcLabels)
  - is it still necessary to add pthread_exit() at the end of a thread fuction?
   (if not, this module could be concurrency-unaware, and thus use faster parsing)
   (anyway, probably the return->pthread_exit() transformation should be moved somewhere else, e.g.,
    sequentialization module, or duplicator).

"""
import copy,re
import pycparserext.ext_c_parser, pycparser.c_ast, pycparserext.ext_c_generator
from pycparser import c_ast
import core.module, core.parser, core.utils


class inliner(core.module.Translator):
	functionlines  = {}               # map function names to sets of line numbers
	linestofunctions = {}             # map from lines to function names

	currentFunction = ['']
	currentFunctionParams = []        # while parsing a function call, keeps the list of parameters used for the actual call

	inlinedStack = []                 # inlined function to add before a statement
	indexStack = []                   # current index (= functionname_inliningcountforthisfunction) used for labels and gotos

	# simplified passing of references to global variables
	parametersToRemoveStack = [[]]
	switchTo = []                     # Fix to avoid multiple inliner of two functions with take the same parameter (as a global var, pfscan)

	# simplified passing of global variables or constants
	variablerename = [{}]             # id of the variable (in the body of the function being inlined) to rewrite
	#paramnochange = []              # function parameter (number of) to simplify in a function call

	# old
	funcInlinedCount = {}             # number of times a function call has been inlined, by function

	atomicparameters = None           # prevent context-switching in between assignment statements for argument passing
	simplifyargs = None               #

	__globalMemoryAccessed = False    # delimit sequence points
	__hasatomicbegin = False
	__canbemerged = {}                # used to join atomic sections

	visitingfargs = 0


	def init(self):
		super().extend()

		self.inputparam('atomic-parameters', 'atomic argument passing for inlined functions', '', default=None, optional=True)
		self.inputparam('simplify-args', 'simplified pointer argument passing (exp)', '', default=None, optional=True)

	def loadfromstring(self, string, env):
		self.env = env
		self.atomicparameters = True if self.getinputparam('atomic-parameters') is not None else False
		self.simplifyargs = True if self.getinputparam('simplify-args') is not None else False

		super().loadfromstring(string,env)


	def visit_UnaryOp(self, n):
		operand = self._parenthesize_unless_simple(n.expr)

		if n.op == 'p++':
			return '%s++' % operand
		elif n.op == 'p--':
			return '%s--' % operand
		elif n.op == 'sizeof':
			# Always parenthesize the argument of sizeof since it can be
			# a name.
			return 'sizeof(%s)' % self.visit(n.expr)
		elif n.op == '*':
			for switchto in self.switchTo:
				if len(switchto) > 0 and operand in switchto:
					self.debug("simplifying '*%s' as '%s'" % (operand,switchto[operand]))
					return switchto[operand]

			return '%s%s' % (n.op, operand)


			#self.log("----> (%s) [%s]" % (operand,self.switchTo[-1]))
			#if len(self.switchTo) > 0 and operand in self.switchTo[-1]:
			#	self.log("----> (*%s) -> (%s)" % (operand,self.switchTo[-1][operand]))
			#	return self.switchTo[-1][operand]
			#else:
			#	#self.log("NO ----> (*%s)  (%s)" % (operand,self.switchTo))
			#	return '%s%s' % (n.op, operand)

		else:
			return '%s%s' % (n.op, operand)


	def visit_Compound(self, n):
		s = self._make_indent() + '{\n'
		self.indent_level += 1

		if n.block_items:
			globalMemoryAccessed = False

			if len(self.currentFunction) > 0:
				self.__canbemerged[self.currentFunction[-1]] = False

			for stmt in n.block_items:
				self.__globalMemoryAccessed = False
				self.__hasatomicbegin = False

				k = self._inlineIfNeeded(stmt)

				globalMemoryAccessed = self.__globalMemoryAccessed

				if self.__hasatomicbegin and not globalMemoryAccessed and len(self.currentFunction) > 0:
					self.__canbemerged[self.currentFunction[-1]] = True

				s += k

		self.indent_level -= 1
		s += self._make_indent() + '}\n'

		return s


	def visit_ID(self, n):
		# If this ID corresponds either to a global variable,
		# or to a pointer...
		#
		if (self.Parser.isglobalvariable(self.blockid,n.name) and not
			n.name.startswith('__cs_thread_local_')):
			self.__globalMemoryAccessed = True

		# Recursively replace what needs to be replaced across nested inlined functions.
		for depth in range(len(self.variablerename)-1,-1,-1):
			if n.name in self.variablerename[depth]:
				line = self._mapbacklineno(self.currentinputlineno)[0]
				self.debug('%s: rewriting variable %s as %s' % (line,n.name,self.variablerename[depth][n.name]))
				return self.variablerename[depth][n.name]

		return n.name


	def visit_ExprList(self, n):
		visited_subexprs = []

		for expr in n.exprs:
			if isinstance(expr, pycparser.c_ast.ExprList):
				visited_subexprs.append('{' + self.visit(expr) + '}')
			else:
				visited_subexprs.append(self.visit(expr))

		if visited_subexprs not in self.currentFunctionParams:
			self.currentFunctionParams.append(visited_subexprs)

		return ', '.join(visited_subexprs)


	''' The definitions of inlined functions are supposed to disappear,
	    excluding functions that may be invoked or referenced via function pointers
	   (this also includes the case when a function is used as an argument to create a thread)
	    as well as atomic functions (see needsinlining).

	    Note: function definition = function declaration + body.
	'''
	def visit_FuncDef(self,n):
		f = n.decl.name

		# Is this function definition supposed to disappear?
		# If so, replace with an empty string.
		if self.__needsInlining(n.decl.name):
			##self.log("removing function %s" % n.decl.name)
			return ''

		# Function definition not removed
		self.currentFunction.append(n.decl.name)
		##self.log("not removing function %s" % n.decl.name)

		decl = self.visit(n.decl)
		self.indent_level = 0
		body = self.visit(n.body)

		# At the bottom of each thread, add a pthread_exit() statement
		#
		returnStmt = ''

		if (self.currentFunction[-1] in self.Parser.threadName or self.currentFunction[-1] == 'main'):
			returnStmt = self.INDENT_SPACING + '__exit_%s: ; %s(0);\n' % (self.currentFunction[-1], 'pthread_exit')

		# Continue the visit.
		if n.param_decls:
			knrdecls = ';\n'.join(self.visit(p) for p in n.param_decls)
			body = body[:body.rfind('}')] + self._make_indent() + returnStmt + '}'
			block = decl + '\n' + knrdecls + ';\n' + body + '\n'
		else:
			body = body[:body.rfind('}')] + self._make_indent() + returnStmt + '}'
			block = decl + '\n' + body + '\n'

		self.currentFunction.pop()

		return block


	'''
	'''
	def visit_FuncCall(self,n):
		self.currentFunctionParams = []
		fref = self._parenthesize_unless_simple(n.name)
		#self.log("visiting call to function %s" % fref)

		# A call to pthread_exit() within thread function
		# is treated like a return statement from the same function, and
		# thus changed to a jump to the last statement.
		#
		# TODO pass pthread_exit()'s argument
		#
		#if fref == core.common.changeID['pthread_exit']:
		if fref == 'pthread_exit':
			if (n.args is not None): self.warn("thread exit argument ignored")
			return 'goto __exit_%s ' % (self.currentFunction[-1])

		if fref == '__VERIFIER_atomic_begin':
			self.__hasatomicbegin = True

		self.visitingfargs+=1
		args = self.visit(n.args)
		self.visitingfargs-=1
		###self.warn("--> %s(%s) <--" % (fref,args))

		s = fref + '(' + args + ')'

		if n.args is None:
			self.currentFunctionParams.append([])

		#if self.visitingfargs > 0 : ## and not fref.startswith('__CSEQ') and not fref.startswith('__cs_') and not fref.startswith('__VERIFIER_'):
		if self.visitingfargs > 0 and self.__needsExpandedHere(fref): ## and not fref.startswith('__CSEQ') and not fref.startswith('__cs_') and not fref.startswith('__VERIFIER_'):
			self.warn("[%s] nested function calls (to %s) not supported" % (self.env.inputfile,  fref),snippet=True)
		elif self.__needsExpandedHere(fref):    ####if self.__needsInlining(fref):
			if fref not in self.funcInlinedCount: self.funcInlinedCount[fref] = 0
			else: self.funcInlinedCount[fref] += 1

			self.indexStack.append('_%s_%s' % (fref,self.funcInlinedCount[fref]))
			#self.log("depth:%s --- full stack:<%s>" % (self.visitingfargs,self.indexStack))
			#self.log("depth:%s ---module stack:<%s>" % (self.visitingfargs,self.stack))

			self.inlinedStack[-1] += (self._inlineFunction(self.Parser.funcASTNode[fref],n,False))+'\n'

			node = self.Parser.decl('0',fref)
			isvoid = self.Parser.functionisvoid(node)

			if isvoid:
				s = '<a_function_call_was_here>'   # void function thus no value returned
			elif not isvoid and self.stack[-2] == 'Compound':
				s = '<a_function_call_was_here>'   # non-void function but return value not stored (because stack[-2] == compound)
			elif self.visitingfargs > 0:
				#self.warn("ci sono")
				pass
			else: s =  '__cs_retval_%s' % (self.indexStack[-1])   # <----- bug with nested function calls TODO

			self.indexStack.pop()

		return s


	def visit_Return(self, n):
		if len(self.indexStack) > 0:
			assign = ''
			jump = ''

			# if the function is non-void,
			# need to pass its return value
			node = self.Parser.decl('0',self.currentFunction[-1])
			isvoid = self.Parser.functionisvoid(node)

			if not isvoid:
				assign = '__cs_retval_%s = (%s);' % (self.indexStack[-1], self.visit(n.expr))

			# if the return statement is not the last statement of the function,
			# need a jump to the end of the function to correctly simulate the return
			if not (self.Parser.funcExitPointsCnt[self.currentFunction[-1]] == 1 and type(self.Parser.lastFuncStmtNode[self.currentFunction[-1]]) == pycparser.c_ast.Return):
				jump = 'goto __exit_%s;' % (self.indexStack[-1])

			return assign + jump

		if (self.currentFunction[-1] in self.Parser.threadName or self.currentFunction[-1] == 'main'):
			return 'goto __exit_%s; ' % (self.currentFunction[-1])

		s = 'return;' if not n.expr else 'return (' + self.visit(n.expr) + ');'

		return s


	########################################################################################

	def _inlineIfNeeded(self,stmt):
		# Truc comment this for method 2
		# self.inlinedStack.append('')

		# original = self._generate_stmt(stmt)
		# original = original.replace('<a_function_call_was_here>;\n', '')
		# original = self.inlinedStack[-1] + original

		# self.inlinedStack.pop()

		# Truc (method 2: Identify inlined function call by inlinedStacked
		# and change things according to type of statements)
		self.inlinedStack.append('')

		original = ''
		if isinstance(stmt, pycparser.c_ast.Label):
			label = stmt.name
			original = self._generate_stmt(stmt.stmt)
			if self.inlinedStack[-1] == '':  # If this statement doesn't contain inlined function
				original = label + ':\n' + original
			else:
				original = original.replace('<a_function_call_was_here>;\n', '')
				original = label + ':;\n' + self.inlinedStack[-1] + original
		else:
			original = self._generate_stmt(stmt)
			original = original.replace('<a_function_call_was_here>;\n', '')
			original = self.inlinedStack[-1] + original

		self.inlinedStack.pop()

		return original


	''' Generate the function body,
	    for either including it in a function definition, or
	    for inserting it into a statement
	'''
	def _inlineFunction(self,fdef,fcall,simple):
		fInput = fOutput = ''
		fname = fdef.decl.name

		#self.log("-----> inlining function %s" % fname)
		#self.log('new inlining: call to:(%s)   variablerename:(%s)' % (fname,self.variablerename))

		# Analysis of function-call parameters
		# in the attempt to optimise the inlined program.
		#
		self.parametersToRemoveStack.append([])
		self.switchTo.append({})

		paramnochange = []
		self.variablerename.append({})

		noargs = self._functiontakesnoargs(fdef)


		# Simplification of parameter passing (CASE 1)
		#
		'''
		if fcall.args is not None:
			for paramno,expr in enumerate(fcall.args.exprs):   # for each parameter in the function call
				self.debug("analysing parameter %s for function %s: %s)..." % (paramno,fname,self.Parser.funcParams[fname][paramno]))

				if (type(expr) == pycparser.c_ast.UnaryOp and expr.op == '&' and self.Parser.isglobalvariable(self.blockid,expr.expr.name)):
					oldcheck = len(self.Parser.varOccurrence[fname,self.Parser.funcParams[fname][paramno]])
					newcheck = self.Parser.countoccurrences(self.blockid,self.Parser.funcParams[fname][paramno])

					if oldcheck != newcheck:
						print("BOBO disagree on parameter %s of function %s   old:%s   new:%s" % (self.Parser.funcParams[fname][paramno],fname,oldcheck,newcheck))
					else:
						print("BOBO good")


				# 	case 1.1: references to global variables as function parameters
				#          (in this case, must also check that every time the variable under consideration occurs,
				#           it is dereferenced --otherwise the simplification is not possible)
				#   case 1.2: global variables
				#   case 1.3: constants
				if (type(expr) == pycparser.c_ast.UnaryOp and expr.op == '&' and
					self.Parser.isglobalvariable(self.blockid,expr.expr.name) and
					len(self.Parser.varOccurrence[fname,self.Parser.funcParams[fname][paramno]]) - len(self.Parser.varDeReferenced[fname,self.Parser.funcParams[fname][paramno]]) == 0):
					self.parametersToRemoveStack[-1].append('&'+expr.expr.name)  # parameter  expr.expr.name  in the call to  fname()  can to be removed
					self.switchTo[-1][self.Parser.funcParams[fname][paramno]] = expr.expr.name
					self.log("AAA removing reference to global variable &%s from the fuction call" % expr.expr.name)
					self.log("AAA changing in the function body (*%s) -> (%s)" % (self.Parser.funcParams[fname][paramno], expr.expr.name))
				elif (type(expr) == pycparser.c_ast.ID and
					self.Parser.isglobalvariable(self.blockid,expr.expr.name)):
					self.log("AAA %s: simplified passing of global variable '%s' as argument %s in call to '%s'" % (self._mapbacklineno(self.currentinputlineno)[0],expr.name,paramno,fname))
					paramnochange.append(paramno)
				elif type(expr) == pycparser.c_ast.Constant:
					self.log("AAA %s: simplified passing of constant value '%s' as argument %s in call to '%s'" % (self._mapbacklineno(self.currentinputlineno)[0],expr.value,paramno,fname))
					paramnochange.append(paramno)
		'''

		# Simulate passing of function arguments
		#
		# Make sure that the no. of actual parameters of a function call
		# match the no. of formal parameters declared within the function definition.
		apcnt = len(fcall.args.exprs) if fcall.args is not None else 0
		fpcnt = len(fdef.decl.type.args.params) if fdef.decl.type.args is not None else 0   #fp = len(self.Parser.funcParams[fname])

		if not noargs and apcnt != fpcnt: # and type(fdef.decl.type.args.params[-1]) != pycparser.c_ast.EllipsisParam:
			self.error("non-void function %s() invoked with %s parameters rather than %s (%s)" % (fname,apcnt,fpcnt,fdef.decl.type.args.params), snippet=True)


		if not noargs:
			for cnt in range(0,apcnt):
				fp = self.visit(fdef.decl.type.args.params[cnt],nolinemarkers=True)
				ap = self.visit(fcall.args.exprs[cnt],nolinemarkers=True)
				#self.log("          fp[%s] %s" % (cnt,fp))
				#self.log("          ap[%s] %s" % (cnt,ap))

				if fp != '...' and cnt in paramnochange:
					self.debug("rewriting formal parameter %s as %s" % (fdef.decl.type.args.params[cnt].name,ap))
					self.variablerename[-1][fdef.decl.type.args.params[cnt].name] = ap

				# Simplification of parameter passing (CASE 2)
				#
				# Attempt simplification of function passing parameters, by
				# checking for un-necessary referencing & defererencing of function parameters.
				#
				'''
				if self.simplifyargs and type(fdef.decl.type.args.params[cnt]) != pycparser.c_ast.EllipsisParam:
					if (type(fdef.decl.type.args.params[cnt].type) == pycparser.c_ast.PtrDecl and
						type(fcall.args.exprs[cnt]) == pycparser.c_ast.UnaryOp and
						fcall.args.exprs[cnt].op == '&'):

						# When applicable,
						# perform the following source tranformations:
						#
						#     1. remove reference operation in the function body: (*x) -> (x)
						#     2. remove reference operation in the function declaration: (type *y) -> (type y)
						#     3. remove dereference operation in the (simulated) function call: f(&z) -> f(z)
						#
						# Note: some of the subfields used below might not be available,
						# in which case the code below has no effect.
						#
						try:
							#self.log("---------- scanning passed parameters for call to function %s" % (fname))
							#self.log("parameter no.%s" % cnt)

							fpid = fdef.decl.type.args.params[cnt].name
							overalloccurrences  = len(self.Parser.varOccurrence[fname,fpid])
							overalldereferences = len(self.Parser.varDeReferenced[fname,fpid])

							#self.log("fpid[%s] ---- --- -- - > %s" % (cnt,fpid))
							#self.log("         ---- --- -- - > %s" % (overalloccurrences))
							#self.log("         ---- --- -- - > %s" % (overalldereferences))

							if overalldereferences == overalloccurrences:
								ap1 = ap.replace('&','') ###self.visit(fcall.args.exprs[cnt].expr,nolinemarkers=True)
								fp2 = self._generate_type(fdef.decl.type.args.params[cnt].type.type).replace("int ",'',1)
								fp1 = self.Parser.funcParams[fname][cnt]

								#self.log("simplifying call to %s(no.%s)" % (fname,cnt))
								#self.log("function defined here")
								#self.log("          ap[%s] %s" % (cnt,ap))
								#self.log("          fp[%s] %s" % (cnt,fp))
								#self.log("         ap1[%s] %s" % (cnt,ap1))
								#self.log("         fp1[%s] %s" % (cnt,fp1))
								#self.log("         fp2[%s] %s" % (cnt,fp2))
								#self.log("========== simplifying function call %s argument no.%s (%s)" % (fname,cnt,self.Parser.funcParams[fname][cnt]))

								# 1. change in the function body
								self.switchTo[-1][fp1] = ap1
								self.debug("simplifying '%s' as '%s'" %(fp1,ap1))

								# 2. change formal parameter type
								fp = fp1

								# 3. change actual parameter in the call
								ap = ap1
								continue
						except:
							self.warn("simplification of inlined function failed")
					'''

				if fp != '...' and cnt not in paramnochange:
					fInput += '%s = %s;' % (fp, ap)
				elif fp != '...' and cnt in paramnochange:
					##self.paramnochange.remove(cnt)
					# don't need temporary variables for passing constants or global variables
					pass
				else:
					self.warn('discarding extra arguments in call to variadic function')

		# Simulate output parameter returning.
		#
		if not self.Parser.functionisvoid(fdef.decl):
			#node = self.Parser.decl('0',fname)
			node = fdef.decl
			args = self.Parser.functionoutput(node)
			fOutput = self._make_indent()+'%s __cs_retval_%s;\n' % (args,self.indexStack[-1])
		else:
			fOutput = ''   # the function does not return anything

		# Truc - dirty fix, just inlude the line map of that function call
		fOutput = self._getmarker(fcall) + '\n' + fOutput

		# Transform the function body by:
		#
		#   1. adding the initialization statement(s) (if any) at the top
		#   2. adding one exit label at the bottom where to jump to in order to simulate return statements
		#   3. change return statements to goto statements pointing to the exit label added in previous step
		#   4. all the rest is unchanged
		#

		# body (adds one indent each line)
		self.currentFunction.append(fname)

		# save the old length so after the inlining self.lines can be trimmed back to its contents before the inlining,
		# this removes the elements added while inlining,
		# otherwise when inlining the same function more than once,
		# the linemapping is only generated on the first inlined function call.
		oldlineslen = len(self.lines)
		inlined = self.visit(self.Parser.funcASTNode[fname].body)
		self.functionlines[fname] = self.lines[oldlineslen:]
		self.lines = self.lines[:oldlineslen]

		# top
		#~inlined = inlined.replace(self.INDENT_SPACING+'{', '/*** INLINING START %s ***********************************/\n' % fname + self.INDENT_SPACING + fOutput + self._make_indent() +'{\n' + self._make_indent() + fInput, 1)
		inlined = inlined[inlined.find('{')+1:]

		bbb = len(fcall.args.exprs) if fcall.args is not None else 0

		if self.atomicparameters and bbb>=1:
			fInput = '__VERIFIER_atomic_begin();' + fInput

			if fname in self.__canbemerged and self.__canbemerged[fname]:
				inlined = inlined.replace('__VERIFIER_atomic_begin();', '', 1)
			else:
				fInput += '__VERIFIER_atomic_end();'

		addedheader = self.INDENT_SPACING + fOutput + self._make_indent() + '{\n' + self._make_indent(1) + fInput
		inlined = addedheader + inlined

		# bottom
		if self.Parser.funcExitPointsCnt[fname] == 0 and self.Parser.functionisvoid(fdef.decl):
			pass  # function is void and contains no return statement, don't need an exit label to simulate returns
		elif self.Parser.funcExitPointsCnt[fname] == 0 and not self.Parser.functionisvoid(fdef.decl):
			self.error("no return statements in non-void function '%s'." % fname, False)
		elif self.Parser.funcExitPointsCnt[fname] == 1 and type(self.Parser.lastFuncStmtNode[self.currentFunction[-1]]) == pycparser.c_ast.Return:
			pass  # function is non-void but the only return statement is at the very end, no exit label needed
		else:
			inlined = inlined[:inlined.rfind('}')] + '%s __exit_%s: ;  \n' % (self._make_indent(1), self.indexStack[-1]) + self._make_indent() +'}\n'
		#~inlined += '\n' + self._make_indent() + '/*** INLINING END %s **************************************/' % fname

		self.parametersToRemoveStack.pop()
		self.switchTo.pop()
		self.currentFunction.pop()
		self.variablerename.pop()

		return inlined


	''' Check whether function  f  needs to be inlined.
	'''
	def __needsInlining(self,f):
		# If the number of occurrences of the identifier of a given function
		# is greater than then number of explicit calls to that function,
		# then the function identifier is passed as a reference somewhere
		# (this includes when the function identifier is passed as an argument to
		#  pthread_create).
		# The definitions of any such function should be retained in the output.
		#
		cntoveralloccurrences = self.Parser.funcIdCnt[f]
		cntexplicitcalls = self.Parser.funcCallCnt[f]
		cntthreads = self.Parser.threadCallCnt[f]

		#self.log( "- - - -> function: %s   overall:%s   explicit:%s   threads:%s" % (f,cntoveralloccurrences,cntexplicitcalls,cntthreads))
		# function: check_gcd   overall:2   explicit:1   threads:0
		return (not f == 'main' and
			not f == '__CSEQ_assert' and
			not f == '__VERIFIER_assert' and
			not f.startswith('__VERIFIER_atomic') and
			not cntoveralloccurrences > cntexplicitcalls and  # this also counts threads
			not cntthreads >= cntoveralloccurrences and
			f in self.Parser.funcName)


	''' Check whether function call to  f  needs to be expanded.
	'''
	def __needsExpandedHere(self,f):
		#cntoveralloccurrences = self.Parser.funcIdCnt[f]
		#cntexplicitcalls = self.Parser.funcCallCnt[f]
		#cntthreads = self.Parser.threadCallCnt[f]

		#self.log( "= = = => function: %s   overall:%s   explicit:%s   threads:%s" % (f,cntoveralloccurrences,cntexplicitcalls,cntthreads))
		#self.log("= = = =  funcnames: %s" % (self.Parser.funcName))

		return (not f.startswith('__CSEQ_') and
			not f.startswith('__VERIFIER_') and
			#not cntoveralloccurrences > cntexplicitcalls and  # this also counts threads
			#not cntthreads >= cntoveralloccurrences and
			f in self.Parser.funcName)


	''' Return True if the function takes no arguments or takes (void).
	'''
	def _functiontakesnoargs(self,f):
		voidfunc = False

		fpcnt = len(f.decl.type.args.params) if f.decl.type.args is not None else 0

		if fpcnt > 1: voidfunc = False
		if fpcnt == 1:
			try:
				#if fdef.decl.type.args is not none and .params[0].type and fdef.decl.type.args.params[0].type.declname:
				voidfunc = (f.decl.type.args.params[0].type.declname is None)   # f(void)
			except: voidfunc = False

		##self.log("function %s is void? %s" % (f.decl.name,voidfunc))
		return voidfunc


