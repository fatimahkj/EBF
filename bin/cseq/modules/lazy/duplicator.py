""" CSeq Program Analysis Framework
    lazy sequentialisation: thread duplicator module

Last step to produce a bounded program (see CAV2014)
after running inliner+unroller on the input.

This module works on unfolded programs, and
it duplicates the functions used multiple times to create a thread,
so that each thread creation refers to a distinct function.

The number of copies is the number of times that the function
is used as an argument to pthread_create().

The copies share the body, and
the name of the function is indexed by adding a trailing counter.

The calls to pthread_create() are updated accordingly.

For example,
	the following input code:
		thread() { ... }

		pthread_create(thread);
		pthread_create(thread);

	will generate:
		thread_0() { ... }
		thread_1() { ... }

		pthread_create(thread_0);
		pthread_create(thread_1);

In case separate declarations for the functions are in the input,
this module will replicate the declarations as well as the definitions,
as in the following case:

	thread();                      // declaration

	main() {
    	pthread_create(thread);   // 1st spawning
    	pthread_create(thread);   // 2nd spawning
	}

	thread(...) { function body }  // definition.

Author:
	Omar Inverso

Changes:
    2021.02.13  re-written from scratch (new symbol table) (CSeq 3.0)
                - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
	2020.11.12  new option to bound the number of thread creations [SV-COMP 2021]
    2020.03.24 (CSeq 2.0)
    2019.11.15 [SV-COMP 2020] no longer mapping pthread_xyz function identifiers
    2018.11.23  handling the case of same function used to spawn threads and in explicit calls
    2015.07.15 [ASE 2015]
    2015.07.15  fixed linemapping not working for non-thread functions (e.g. atomic functions) (Truc,Omar)
    2015.07.13  fixed linemapping not working from the 2nd copy of a thread onwards (Omar)
    2015.06.23  re-implemented 3rd parameter extraction from the call to pthread_create()
    2014.12.24 (CSeq 1.0beta)
    2014.12.09  further code refactory to match the new organisation of the CSeq framework
    2014.10.26 (CSeq Lazy-0.6, newseq-0.6a, newseq-0.6c), [SV-COMP 2015]
    2014.10.26  removed dead/commented-out/obsolete code
    2014.10.15  removed visit() and moved visit call-stack handling to module class (module.py)
    2014.03.14 (CSeq Lazy-0.4) further code refactory to match  module.Module  class interface
    2014.02.25 (CSeq Lazy-0.2)switched to module.Module base class for modules

Notes:
  - the input needs to be completely unfolded, needs inliner+unroller first.

To do:
  -

"""
import re
import pycparserext.ext_c_parser, pycparser.c_ast, pycparserext.ext_c_generator
import core.module, core.parser, core.utils


class duplicator(core.module.Translator):
	__actualthreads = 0	      # no. of calls to pthread_create so far (the extra thread for main() is not counted)
	__actualjoins = 0         # no. of calls to pthread_join so far

	__threadCallCnt = {}	  # number of pthread_create()s on the same function generated so far
	__threadsnamesmap = {}	  # from thread copy to original thread (example: threadf_10 --> threadf)
	__threadindexes = {}	  # index of thread copies by name (statically determined)
	__threadindextoname = {}  # from integer thread indexes to function names (not indexed)
	__threadindextoname[0] = 'main' # the first thread is always main()


	def init(self):
		super().extend()

		self.inputparam('threads', 'max. number of thread creation (0=unlimited)', 't', '0', False)  # == threads creations +1

		self.outputparam('threads')		   # no. of thread creations (statically determined)
		self.outputparam('threadnamesmap')	# map from thread copies to original threads
		self.outputparam('threadindexes')	 # map from thread copies (renamed id) to thread indexes
		self.outputparam('threadindextoname') # map from thread index to original thread/function name


	def loadfromstring(self,string,env):
		self.maxthreads = int(self.getinputparam('threads'))

		super().loadfromstring(string,env)

		self.setoutputparam('threads', self.__actualthreads)
		self.setoutputparam('threadnamesmap', self.__threadsnamesmap)
		self.setoutputparam('threadindexes', self.__threadindexes)
		self.setoutputparam('threadindextoname', self.__threadindextoname)


	def visit_Decl(self,n):
		# No transformation for non-threads.
		if not (self.blockid == '0' and self.Parser.isfunction('0',n.name) and self.Parser.threadCallCnt[n.name]>0):
			return super().visit_Decl(n)

		#print("thread function n.name:[%s]     is function:[%s]     threadcallcnt:[%s] " % (n.name,self.Parser.isfunction('0',n.name),self.Parser.threadCallCnt[n.name]))
		block = ''

		for i in range(0,self.Parser.threadCallCnt[n.name]):
			oldlineslen = len(self.lines) # save self.line to restore linemarking later

			oldname = n.name
			newname = n.name+'_'+str(i)

			self._replacefdeclname(n,newname)    # change the function identifier
			tmp = super().visit_Decl(n)  # re-visit function with new identifier
			self._replacefdeclname(n,oldname) # revert function identifier change

			self.__threadsnamesmap[newname] = oldname # remember the name change
			self.lines = self.lines[:oldlineslen]           # restore self.lines

			block += ';'+tmp


		cntoveralloccurrences = self.Parser.funcIdCnt[n.name]
		cntthreads = self.Parser.threadCallCnt[n.name]

		if cntoveralloccurrences > cntthreads:   # same function is used both to spawn threads and in explicit invocations
			self.warn("function %s used both to create threads and explicitly invoked" % (n.decl.name))
			block += super().visit_Decl(n)

		return block


	def visit_FuncCall(self,n):
		fref = self._parenthesize_unless_simple(n.name)
		args = ''

		if fref == 'pthread_create':
			if self.maxthreads==0 or (self.maxthreads > 0 and self.__actualthreads < self.maxthreads):
				self.__actualthreads += 1
				fName = self._extractfname(n.args.exprs[2]) # extract function name (3rd argument)

				# Append to the function name a different index
				# if the same function has been used to create many thread.
				if fName not in self.__threadCallCnt: self.__threadCallCnt[fName] = 0;
				else: self.__threadCallCnt[fName] += 1;

				fNameIndexed = fName +'_'+ str(self.__threadCallCnt[fName])

				# Update the function name in the pthread_create call.
				args += self.visit(n.args.exprs[0]) + ', '
				args += self.visit(n.args.exprs[1]) + ', '
				args += fNameIndexed + ', '
				args += self.visit(n.args.exprs[3])

				self.__threadindexes[fNameIndexed] = self.__actualthreads
				self.__threadindextoname[self.__actualthreads] = fName
			else:
				#self.warn("max number of threads exceeded")
				#fref = 'noop'
				self.error("max number of threads exceeded", snippet=True)
		elif fref == 'pthread_join':
			if self.maxthreads==0 or (self.maxthreads > 0 and self.__actualjoins < self.maxthreads):
				self.__actualjoins += 1
				args = self.visit(n.args)
			else:
				fref = 'noop'
		else:
			args = self.visit(n.args)

		return fref + '(' + args + ')'


	def visit_FuncDef(self,n):
		cntthreads = self.Parser.threadCallCnt[n.decl.name]

		# No transformation for non-threads.
		if n.decl.name == 'main' or cntthreads == 0: return super().visit_FuncDef(n)

		# Duplicate threads, but include the original function definition
		# in case it is also used otherwise (i.e.,
		# explicit calls or any other occurrence of the function's identifier,
		# such as references).
		block = ''
		cntoveralloccurrences = self.Parser.funcIdCnt[n.decl.name]

		if self.maxthreads != 0: cntthreads = min(self.maxthreads,cntthreads)

		for i in range(0,cntthreads):
			oldlineslen = len(self.lines) # save self.line to restore linemarking later

			oldname = n.decl.name
			newname = n.decl.name+'_'+str(i)

			self._replacefdeclname(n.decl,newname)    # change the function identifier
			tmp = super().visit_FuncDef(n)    # re-visits function with new identifier
			self._replacefdeclname(n.decl,oldname) # revert function identifier change

			self.__threadsnamesmap[newname] = oldname # remember the name change
			self.lines = self.lines[:oldlineslen]           # restore self.lines

			block += tmp

		if cntoveralloccurrences > cntthreads:   # same function is used both to spawn threads and in explicit invocations
			self.warn("function %s used both to create threads and explicitly invoked" % (n.decl.name))
			block += super().visit_FuncDef(n)

		return block


	''' Change the identifier of the function declared at the given node in the syntax tree.
	    If n is a Decl node, then use n as the node.
	    If n is a FuncDef node, then use n.decl as the node.
	'''
	def _replacefdeclname(self,node,newname):
		# Change the function identifier (location 1 in the syntax tree).
		node.name = newname

		# Change the function identifier (location 2 in the syntax tree).
		m = node
		while hasattr(m,'type'): # jump through enclosing declarations, e.g., ptr, struct, etc.
			m = m.type           # declname not yet found, keep going

			if hasattr(m,'declname'):
				m.declname = newname # <--- here it is
				break


	''' Extract the function identifier from a function call node.
	'''
	def _extractfname(self,n):
		# scan through parent nodes such as casts, unary operators, etc.
		# until an identifier is found.
		if type(n) == pycparser.c_ast.Cast: return self._extractfname(n.expr)
		if type(n) == pycparser.c_ast.UnaryOp: return self._extractfname(n.expr)
		if type(n) == pycparser.c_ast.ArrayRef:return self._extractfname(n.name)
		if type(n) == pycparser.c_ast.ID:
			return self.visit(n)

		print("error: unable to extract function identifier from expression '%s' for thread spawning (node type: '%s')" % (self.visit(n),type(n)))
		#print("error: symbol table: %s/%s unable to handle symbol '%s' of type %s" % (self.blockid,n.coord,n.name,type(n.type)))
		return self.visit(n)












