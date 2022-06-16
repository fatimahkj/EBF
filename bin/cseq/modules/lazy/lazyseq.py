""" CSeq Program Analysis Framework
    lazy sequentialisation: main module

Implements the lazy sequentialization schema
(see Inverso, Tomasco, Fischer, La Torre, Parlato, CAV'14).

Author:
	Omar Inverso

Changes:
    2021.11.05  use a counter to keep track of nested atomic sections
    2021.10.20  obsolete options removed
    2021.02.13 (Cseq 3.0)
    2021.02.05  no longer using Parser.varNames (old symbol table)
    2021.02.01  major decluttering (~30% of code stripped away for good)
    2021.02.01  local variables are no longer non-deterministically initialised (it should not happen here anyway)
    2021.02.01  visit_Decl reimplemented from scratch (removed all old ancillary variables, etc.)
    2021.01.31  removed ispointer() and isglobal() macros (using those in the Parser now)
    2020.11.28  error on static storage class for mutexes - TODO
    2020.11.26  error on pthread_mutex_trylock - TODO
    2020.11.13  fix in visit_decl no longer using malloc for static-size arrays
    2020.10.29  fixed size for __cs_pc_cs (k+1 -> k)
    2020.10.29  fix in the context-bounded scheduler cs_cs bitwidth
    2020.10.29  fix in the context-bounded scheduler not updating __cs_thread_index
    2020.04.18  replaced | in the jump marco with a placeholder to be instrumented either to | or ||
    2020.03.28 (CSeq 2.0)
    2020.03.28  block-based symbol table lookup (e.g., isglobal(), etc.)
    2020.03.22  merged context-bounded scheduler [SV-COMP 2020] + [PPoPP 2020]
    2019.11.20 [SV-COMP 2020]
    2019.11.20  static storage class for locks
    2019.11.15  using __VERIFIER_xyz() primitives rather than __CSEQ_xyz()
    2019.11.15 (CSeq 1.9) pycparserext
    2019.11.15  no longer relying on mapped pthread_xyz identifiers
    2019.11.13  support for pycparser 2.19 (backward compatibility preserved)
    2018.11.25  output params for thread endlines and thread sizes (used to build a more detailed error trace)
    2018.11.22  fixed insertion of cs-points for labeled statements
    2018.11.22  insert context-switch point before any mutex operation
    2018.11.21 [SV-COMP 2019]
    2018.11.21  transformation of local variables into static and separation of init exprs (previously done in inliner module, see visit_Decl)
    2018.11.21  always insert the first context-switch point at the very beginning of a thread (and not after the local declarations)
    2018.11.03  merged with [SV-COMP 2016] to [SV-COMP 2018] (after removing a lot of clutter)
    2018.11.10  improved modelling of thread-specific data management (+key destructors)
    2018.11.10  sequentialised threads now always end with a call to __cs_exit() (instead than STOP_VOID or STOP_NONVOID)
    2018.11.03  renamed __currentThread as currentfunction (bnot every function is a thread)
    2018.11.03  no longer using Parser.funcReferenced to check whether a function might be referenced
    2018.11.03  fixed detection of return statements within threads
    2018.11.02  added support for thread-specific data management (getspecific, setspecific, keys, etc.)
    2016.11.30  handling of main()'s argc and argv parameters disabled as not implemented properly
    2016.11.22  fix problem with function pointer reference (smacker benchmarks)
    2016.09.21  fix small bug that causes the injection of GUARD in atomic function
    2016.08.12  support for preanalysis from framac to guess the number of bits for each variable
    2016.01.19  code review to make it more uniform with the cba version
    2015.10.19 (CSeq 1.3) for unfinished journal
    2015.10.19  fix bug of __CSEQ_atomic_begin (definitely have a context switch before this statement) (Truc)
    2015.07.18 (CSeq 1.0) [ASE 2015]
    2015.07.18  new --schedule parameter to set schedule restrictions (Omar)
    2015.07.15  changed visit of atomic function definitions (Truc,Omar)
    2015.07.10  no context switch between __CSEQ_atomic_begin() and __CSEQ_atomic_end()
    2015.06.30  major refactory (converted to stand-alone instrumentation, etc.)
    2015.04.23  _globalAccess()  was causing  if(cond)  blocks to disappear
    2015.02.22  __CSEQ_assume() without occurrences of shared vars produces no context switch points
    2015.01.12  back to [CAV 2014]-style constraints in the main driver
    2015.01.27  using macros rather than functions to model pthread_mutex_lock/unlock() avoids using ptrs and thus yields faster analysis
    2014.01.17  main driver: first thread execution context must have length > 0 (faster analysis)
    2014.12.24  linemap (overrides the one provided by core.module)
                bugfixes, code maintenance
    2014.12.09  further code refactory to match the new organisation of the CSeq framework
    2014.10.29 (CSeq 1.0beta) (newseq-0.6c) [SV-COMP 2015]
    2014.10.29  bitvector encoding for all control variables (pc, pc_cs, ...)
                new main driver where guessed jump lenghts are all at the top (this allows inserting p.o.r. constraints right after them)
    2014.10.26 (newseq-0.6a) removed dead/commented-out/obsolete code
    2014.10.15  removed visit() and moved visit call-stack handling to module class (module.py)
    2014.06.26 (CSeq Lazy-0.4) improved backend-specific instrumentation
    2014.06.26  added new backend Klee
    2014.03.14 (CSeq Lazy-0.3) further code refactory to match module.Module class interface
    2014.02.25 (CSeq Lazy-0.2) switched to module.Module base class for modules
    2014.01.19  fixed assert()s missing their stamps at the beginning

Notes:
  - all functions should have been inlined, except the main(), all thread functions, all __CSEQ_atomic_ functions, and function __CSEQ_assert
  - all loops should have been unrolled
  - no two threads refers to the same thread function (use module duplicator.py)
  - in the simulated pthread_xyz(), the id of the main thread is 1 (not 0!), e.g.
    mutex lock and unlock operations use thread_index+1.
    Index 0 is for unitialised global variables (which may include global mutexes).....

To do:
  - urgent: use AST-based handling of parameters for function main()
  - rather than turning local variables into static local variables,
    make them global (static local variables default to 0, global variables do not,
    so the semantics would be more consistent w.r.t. the original program -- this would
    also eliminate the need for any explicit initialisation to be taken care here)
  - check handling of __thread_local's
  - fix 'uninitialised local variable' warning (should trigger it when variable read or referenced without initialising first)
  - check the STOP() inserting mechanism
  - this schema assumes no mutex_lock() in main() - is this fine?

"""
import math, re
from time import gmtime, strftime
import pycparserext.ext_c_parser, pycparser.c_ast, pycparserext.ext_c_generator
import core.module, core.parser, core.utils


class lazyseq(core.module.Translator):
	thisblocknode = None         # AST node for the current block being visited
	stmtcount = -1               # thread statement counter (to build thread labels)
	firstthreadcreated = False   # set once the first thread creation is met
	globalaccess = False         # used to limit context-switch points (when global memory is not accessed, no need to insert them)
	atomicsection = 0            # code being parsed between atomic_start() and atomic_end()
	visitfuncdef = False         # visiting a function definition
	currentfunction = ''         # name of the current thread or function (for functions not inlined)

	visiblestmtcount = {}        # count of visible statements for each thread
	threadname = ['main']        # name of threads, as they are found in pthread_create(s) - the threads all have different names
	threadindex = {}             # index of the thread = value of threadcount when the pthread_create to that thread was discovered
	threadcount = 0              # pthread create()s found so far

	labelline = {}               # statement number where labels are defined [function, label]
	gotoline = {}                # statement number where goto to labels appear [function, label]
	maxcompound = 0              # max label within a compound
	labellen = 55                # for labels to have all the same length, adding padding when needed
	startchar = 't'              # special char to distinguish between labeled and non-labelled lines

	bitwidth = {}                # custom bitwidth for specific int variables, e.g. ['main','var'] = 4
	explicitround = []           # explicit schedules restrictions
	threadendlines  = {}
	staticlocks = ''             # declarations of static mutexes to be moved outside their threads as global variables


	def init(self):
		super().extend()

		self.inputparam('rounds', 'round-robin schedules', 'r', '1', False)
		self.inputparam('contexts', 'execution contexts (replaces --rounds)', 'c', None, optional=True)
		self.inputparam('threads', 'max thread creations (0 = auto)', 't', '0', False)
		self.inputparam('schedule', 'schedule restriction (example: 1,2:+:3)', 's', default='', optional=True)
		self.inputparam('deadlock', 'check for deadlock', '', default=False, optional=True)
		self.inputparam('nondet-condvar-wakeups', 'spurious conditional variables wakeups', '', default=False, optional=True)
		self.inputparam('varnamesmap', 'map for replaced variable names', '', default=None, optional=True)

		self.outputparam('bitwidth')
		self.outputparam('header')
		self.outputparam('threadsizes')    # no. of visible statements for each thread, used to build cex
		self.outputparam('threadendlines')


	def loadfromstring(self,string,env):
		rounds = int(self.getinputparam('rounds'))
		contexts = int(self.getinputparam('contexts')) if self.getinputparam('contexts') is not None else 0
		threads = int(self.getinputparam('threads'))
		schedule = self.getinputparam('schedule')
		deadlock = True if self.getinputparam('deadlock') else False
		pedanticthreads = False if self.getinputparam('nondet-condvar-wakeups') is None else True
		self.varnamesmap = self.getinputparam('varnamesmap')

		# Schedule control.
		# TODO TODO TODO this only works with round-robin scheduler!
		if schedule is not None:
			while schedule.startswith(':'): schedule = schedule[1:]
			while schedule.endswith(':'): schedule = schedule[:-1]
			while schedule.find('::') != -1: schedule = schedule.replace('::',':')
			while schedule.find(',,') != -1: schedule = schedule.replace(',,',',')
			while schedule.startswith(','): schedule = schedule[1:]
			while schedule.endswith(','): schedule = schedule[:-1]

		if schedule is not None and schedule != '':
			for i in schedule.split(':'):
				self.explicitround.append(i)

		for x in self.explicitround:
			for y in x.split(','):
				if y != '+' and not y.isdigit():
					self.warn("invalid scheduling ignored")
					self.explicitround = []
				elif y.isdigit() and int(y) > threads:
					self.warn("invalid scheduling ignored (thread %s does not exist)" % y)
					self.explicitround = []

		if len(self.explicitround) > rounds: # schedules > rounds: adjust rounds
			#self.warn('round bound increased to %s due to longer schedule' % len(schedule.split(':')))
			rounds = len(schedule.split(':'))
		elif len(self.explicitround) < rounds: # schedules < rounds: add more unconstrained entries
			for i in range(len(self.explicitround),rounds):
				self.explicitround.append('+')

		self.explicitround[0] += ',0'   # main thread must always be schedulable in the 1st round

		super(self.__class__, self).loadfromstring(string,env)

		# Add the new main().
		if contexts==0: self.output += self.__scheduler(rounds,threads)
		else:           self.output += self.__schedulercba(contexts,threads)

		# Insert the thread sizes (i.e. number of visible statements).
		lines = ''

		i = maxsize = 0

		for t in self.threadname:
			if i <= threads:
				if i>0: lines += ', '
				lines += str(self.visiblestmtcount[t])
				maxsize = max(int(maxsize), int(self.visiblestmtcount[t]))
			i +=1

		ones = ''  # only used when deadlock check is enabled (see below)
		if i <= threads:
			if i>0: ones += ', '
			ones += '-1'
		i +=1

		# Generate the header.
		#
		# the first part is not parsable (contains macros)
		# so it is passed to next module as a header...
		modulename = ('%s' %__name__)
		modulename = modulename[modulename.rfind('.')+1:]
		modulepath = 'modules/'+env.modulepath[modulename] if env.modulepath[modulename] != '' else 'modules'
		header = core.utils.printFile('%s/lazyseqA.c' % modulepath)
		header = header.replace('<insert-maxthreads-here>',str(threads))
		header = header.replace('<insert-maxrounds-here>',str(contexts) if contexts > 1 else str(rounds))
		self.setoutputparam('header', header)

		# ..this is parsable and is added on top of the output code,
		# as next module is able to parse it.
		if not deadlock and not pedanticthreads:
			header = core.utils.printFile('%s/lazyseqB.c' % modulepath).replace('<insert-threadsizes-here>',lines)
		elif not deadlock and pedanticthreads:
			header = core.utils.printFile('%s/lazyseqB.nondet-condvar-wakeups.c' % modulepath).replace('<insert-threadsizes-here>',lines)
		else:
			header = core.utils.printFile('%s/lazyseqBdeadlock.c' % modulepath).replace('<insert-threadsizes-here>',lines)
			header = header.replace('<insert-all1-here>',  ones)

		self.insertheader(header)

		# Calculate exact bitwidth size for a few integer control variables of the seq. schema,
		# good in case the backend handles bitvectors.
		try:
			k = int(math.floor(math.log(maxsize,2)))+1
			self.bitwidth['','__cs_active_thread'] = 1
			self.bitwidth['','__cs_pc'] = k
			self.bitwidth['','__cs_pc_cs'] = k
			self.bitwidth['','__cs_thread_lines'] = k

			k = int(math.floor(math.log(threads+1,2)))+1
			self.bitwidth['','__cs_thread_index'] = k
			self.bitwidth['','__cs_last_thread'] = k
		except: pass

		# Fix gotos by inserting ASS_GOTO(..) blocks before each goto,
		# excluding gotos which destination is the line below.
		for (a,b) in self.labelline:
			if (a,b) in self.gotoline and (self.labelline[a,b] == self.gotoline[a,b]+1):
				self.output = self.output.replace('<%s,%s>' % (a,b), '')
			else:
				self.output = self.output.replace('<%s,%s>' % (a,b), 'ASS_GOTO(%s)' % self.labelline[a,b])

		self.setoutputparam('bitwidth', self.bitwidth)
		self.setoutputparam('threadsizes',self.visiblestmtcount)
		self.setoutputparam('threadendlines',self.threadendlines)


	def visit_Compound(self,n):
		self.new_block_begin()

		#print ("VISITING BLOCK : %s" % (self.Parser.blocknode[n]))
		s = self._make_indent() + '{\n'
		self.indent_level += 1

		oldblocknode = self.thisblocknode
		self.thisblocknode = n

		# Insert the labels at the beginning of each statement,
		# with a few exclusions to reduce context-switch points...
		#
		if n.block_items:
			for stmt in n.block_items:
				# Case 1: last statement in a thread (must correspond to last label)
				if type(stmt) == pycparser.c_ast.FuncCall and stmt.name.name == 'pthread_exit':
					self.stmtcount += 1
					self.maxcompound = self.stmtcount
					stamp = '__CSEQ_rawline("%s%s_%s: ");\n' % (self.startchar, self.currentfunction, str(self.stmtcount))
					code = self.visit(stmt)
					newStmt =  stamp + code + ';\n'
					s += newStmt
				# Case 2: labeled statements
				elif type(stmt) == pycparser.c_ast.Label:
					# --1-- Simulate a visit to the stmt block to see whether it makes any use of pointers or shared memory.
					#
					globalAccess = self.checkglobalaccess(stmt)
					newStmt = ''

					# --2-- Now rebuilds the stmt block again,
					#       this time using the proper formatting
					#      (now we know if the statement is accessing global memory,
					#       so to insert the stamp at the beginning when needed)
					#
					if self.stmtcount == -1 and self.atomicsection==0:   # first statement in a thread
						self.stmtcount += 1
						self.maxcompound = self.stmtcount
						threadIndex = self.Parser.threadIndex[self.currentfunction] if self.currentfunction in self.Parser.threadIndex else 0
						stamp = '__CSEQ_rawline("IF(%s,%s,%s%s_%s)");\n' % (threadIndex,str(self.stmtcount), self.startchar, self.currentfunction, str(self.stmtcount+1))
						code = self.visit(stmt)
						newStmt = stamp + code + ';\n'
					elif (not self.visitfuncdef and (
						(type(stmt.stmt) == pycparser.c_ast.FuncCall and stmt.stmt.name.name == '__VERIFIER_atomic_begin') or
						(self.atomicsection==0 and
							(globalAccess or
							(type(stmt.stmt) == pycparser.c_ast.FuncCall and stmt.stmt.name.name == 'pthread_create') or
							(type(stmt.stmt) == pycparser.c_ast.FuncCall and stmt.stmt.name.name == 'pthread_join') or
							(type(stmt.stmt) == pycparser.c_ast.FuncCall and stmt.stmt.name.name == 'pthread_mutex_lock') or
							(type(stmt.stmt) == pycparser.c_ast.FuncCall and stmt.stmt.name.name == 'pthread_mutex_unlock') or
							(type(stmt.stmt) == pycparser.c_ast.FuncCall and stmt.stmt.name.name == 'pthread_mutex_destroy') or
							(type(stmt.stmt) == pycparser.c_ast.FuncCall and stmt.stmt.name.name.startswith('__VERIFIER_atomic') and not stmt.name.name == '__VERIFIER_atomic_end') or
							(type(stmt.stmt) == pycparser.c_ast.FuncCall and stmt.stmt.name.name.startswith('__VERIFIER_assume')) or
							(type(stmt.stmt) == pycparser.c_ast.FuncCall and stmt.stmt.name.name == 'pthread_cond_wait_2')
							)
						)
						)):
						self.stmtcount += 1
						self.maxcompound = self.stmtcount
						threadIndex = self.Parser.threadIndex[self.currentfunction] if self.currentfunction in self.Parser.threadIndex else 0
						stamp = '__CSEQ_rawline("%s%s_%s: IF(%s,%s,%s%s_%s)");\n' % (self.startchar, self.currentfunction, str(self.stmtcount),threadIndex,str(self.stmtcount), self.startchar, self.currentfunction, str(self.stmtcount+1))
						code = self.visit(stmt.stmt)
						newStmt = stamp + code + ';\n'
						#####self.log("     (A) STAMP")
					else:
						#####self.log("     (A) no STAMP")
						newStmt = self.visit(stmt.stmt) + ';\n'

					threadIndex = self.Parser.threadIndex[self.currentfunction] if self.currentfunction in self.Parser.threadIndex else 0
					guard = '__VERIFIER_assume( __cs_pc_cs[%s] >= %s );\n' % (threadIndex,self.stmtcount+1) if self.atomicsection==0 else ''
					newStmt = self._make_indent()+ stmt.name + ': ' + guard + newStmt+ '\n'

					s += newStmt
				# Case 3: all the rest....
				#elif (type(stmt) not in (pycparser.c_ast.Compound, pycparser.c_ast.Goto, pycparser.c_ast.Decl)
				elif (type(stmt) not in (pycparser.c_ast.Compound, pycparser.c_ast.Goto)
					and not (self.currentfunction=='main' and self.firstthreadcreated == False) or (self.currentfunction=='main' and self.stmtcount == -1)):
					#####if type(stmt) == pycparser.c_ast.FuncCall: self.log("(B) ----> %s" % stmt.name.name)

					# --1-- Simulate a visit to the stmt block to see whether it makes any use of pointers or shared memory.
					#
					globalAccess = self.checkglobalaccess(stmt)
					newStmt = ''

					self.lines = []   # override core.module marking behaviour, otherwise  module.visit()  won't insert any marker

					# --2-- Now rebuilds the stmt block again,
					#       this time using the proper formatting
					#      (now we know if the statement is accessing global memory,
					#       so to insert the stamp at the beginning when needed)
					#
					if self.stmtcount == -1 and self.atomicsection==0:   # first statement in a thread
						self.stmtcount += 1
						self.maxcompound = self.stmtcount
						threadIndex = self.Parser.threadIndex[self.currentfunction] if self.currentfunction in self.Parser.threadIndex else 0
						stamp = '__CSEQ_rawline("IF(%s,%s,%s%s_%s)");\n' % (threadIndex,str(self.stmtcount), self.startchar, self.currentfunction, str(self.stmtcount+1))
						code = self.visit(stmt)
						newStmt = stamp + code + ';\n'
					elif (not self.visitfuncdef and (
						(type(stmt) == pycparser.c_ast.FuncCall and stmt.name.name == '__VERIFIER_atomic_begin') or
						(self.atomicsection==0 and
							(globalAccess or
							(type(stmt) == pycparser.c_ast.FuncCall and stmt.name.name == 'pthread_create') or
							(type(stmt) == pycparser.c_ast.FuncCall and stmt.name.name == 'pthread_join') or
							(type(stmt) == pycparser.c_ast.FuncCall and stmt.name.name == 'pthread_mutex_lock') or
							(type(stmt) == pycparser.c_ast.FuncCall and stmt.name.name == 'pthread_mutex_unlock') or
							(type(stmt) == pycparser.c_ast.FuncCall and stmt.name.name == 'pthread_mutex_destroy') or
							(type(stmt) == pycparser.c_ast.FuncCall and stmt.name.name.startswith('__VERIFIER_atomic') and not stmt.name.name == '__VERIFIER_atomic_end') or
							(type(stmt) == pycparser.c_ast.FuncCall and stmt.name.name.startswith('__VERIFIER_assume')) or
							(type(stmt) == pycparser.c_ast.FuncCall and stmt.name.name == 'pthread_cond_wait_2')
							)
						)
						)):
						self.stmtcount += 1
						self.maxcompound = self.stmtcount
						threadIndex = self.Parser.threadIndex[self.currentfunction] if self.currentfunction in self.Parser.threadIndex else 0
						stamp = '__CSEQ_rawline("%s%s_%s: IF(%s,%s,%s%s_%s)");\n' % (self.startchar, self.currentfunction, str(self.stmtcount),threadIndex,str(self.stmtcount), self.startchar, self.currentfunction, str(self.stmtcount+1))
						code = self.visit(stmt)
						newStmt =  stamp + code + ';\n'
						#####self.log("     (B) STAMP")
					else:
						#####self.log("     (B) no STAMP")
						newStmt = self.visit(stmt) + ";\n"

					s += newStmt
				else:
					newStmt = self.visit(stmt) + ";\n"
					s += newStmt

		self.indent_level -= 1
		s += self._make_indent() + '}\n'

		self.thisblocknode = oldblocknode

		self.new_block_end()

		return s


	def visit_FuncDef(self,n):
		cntoveralloccurrences = self.Parser.funcIdCnt[n.decl.name]
		cntexplicitcalls = self.Parser.funcCallCnt[n.decl.name]
		cntthreads = self.Parser.threadCallCnt[n.decl.name]
		####print("---> blubluuu: [%s]   callcnlt:%s   idcnt:%s   thrcnt:%s" % (n.decl.name,cntexplicitcalls,cntoveralloccurrences,cntthreads))

		# Remove functions that are never invoked (not even via call to pointer to function)
		if cntoveralloccurrences==cntexplicitcalls==cntthreads==0 and n.decl.name != 'main':
			self.debug("removing unused definition of function %s" % n.decl.name)
			return ''

		# No function sequentialisation
		if (n.decl.name.startswith('__VERIFIER_atomic_') or
			n.decl.name == '__VERIFIER_assert' or
			###n.decl.name in self.Parser.funcReferenced ):
			cntoveralloccurrences > cntthreads): # <--- e.g. functions called through pointers are not inlined yet

			self.currentfunction = n.decl.name
			self.visitfuncdef = True
			self.atomicsection+=1
			decl = self.visit(n.decl)
			body = self.visit(n.body)
			self.atomicsection-=1
			self.visitfuncdef = False
			self.currentfunction = ''  # don't need a stack as FuncDef cannot nest
			return decl + '\n' + body + '\n'

		#print "---> function definition no skip"
		self.currentfunction = n.decl.name
		self.firstthreadcreated = False

		decl = self.visit(n.decl)
		self.indent_level = 0
		body = self.visit(n.body)

		f = ''

		self.visiblestmtcount[self.currentfunction] = self.stmtcount

		#
		if n.param_decls:
			knrdecls = ';\n'.join(self.visit(p) for p in n.param_decls)
			self.stmtcount = -1
			f = decl + '\n' + knrdecls + ';\n'
		else:
			self.stmtcount = -1
			f = decl + '\n'

		# Remove arguments (if any) for main() and transform them into local variables in main_thread.
		# TODO re-implement seriously.
		if self.currentfunction == 'main':
			node = self.Parser.decl('0','main')
			mainargs = self.Parser.functioninput(node)
			mainreturntype = self.Parser.functionoutput(node)

			f = '%s main_thread(void)\n' % mainreturntype # self.Parser.funcBlockOut[self.currentfunction]
			args = ''

			if mainargs.find('void') != -1 or mainargs == '':
				mainargs = ''
			else:
				# Change *argv[] and **argv[] --> **argv
				mainargs = re.sub(r'\*(.*)\[\]', r'** \1', mainargs)
				mainargs = re.sub(r'(.*)\[\]\[\]', r'** \1', mainargs)

				# split arguments
				mainargs = mainargs.split(',')

				if len(mainargs) != 2:
					self.warn('ignoring argument passing (%s) to main function' % mainargs)

				# args = 'static ' + mainargs[0] + '= %s; ' % self.__argc
				# args = 'static ' + mainargs[0] + '; '   # Disable this for SVCOMP
				args = mainargs[0] + '; '
				# argv = self.__argv.split(' ')
				# argv = '{' + ','.join(['\"%s\"' % v for v in argv]) + '}'
				# args += 'static ' + mainargs[1] + '= %s;' % argv
				# args += 'static ' + mainargs[1] + ';'     # Disable this for SVCOMP
				args += mainargs[1] + ';'

			body = '{' + args + body[body.find('{') + 1:]

		f += body + '\n'

		endline = self._mapbacklineno(self.currentinputlineno)[0]
		self.threadendlines[self.currentfunction] = endline

		self.currentfunction = ''

		#
		staticlocksdecl = self.staticlocks
		self.staticlocks = ''

		return staticlocksdecl + f + '\n\n'


	def visit_If(self, n):
		ifStart = self.maxcompound   # label where the if stmt begins

		s = 'if ('

		if n.cond:
			condition = self.visit(n.cond)
			s += condition

		s += ')\n'
		s += self._generate_stmt(n.iftrue, add_indent=True)

		ifEnd = self.maxcompound   # label for the last stmt in the if block:  if () { block; }
		nextLabelID = ifEnd+1

		if n.iffalse:
			elseBlock = self._generate_stmt(n.iffalse, add_indent=True)

			elseEnd = self.maxcompound   # label for the last stmt in the if_false block if () {...} else { block; }

			if ifStart < ifEnd:
				threadIndex = self.Parser.threadIndex[self.currentfunction] if self.currentfunction in self.Parser.threadIndex else 0
				#elseHeader = 'GUARD(%s,%s)' % (threadIndex, str(ifEnd+1))
				if not self.visitfuncdef:
					elseHeader = '__VERIFIER_assume( __cs_pc_cs[%s] >= %s );' % (threadIndex, str(ifEnd+1))
			else:
				elseHeader = ''

			nextLabelID = elseEnd+1
			s += self._make_indent() + 'else\n'

			elseBlock = elseBlock.replace('{', '{ '+elseHeader, 1)
			s += elseBlock

		header = ''

		if ifStart+1 < nextLabelID:
			threadIndex = self.Parser.threadIndex[self.currentfunction] if self.currentfunction in self.Parser.threadIndex else 0
			#footer = 'GUARD(%s,%s)' % (threadIndex, nextLabelID)
			if not self.visitfuncdef:
				footer = '__VERIFIER_assume( __cs_pc_cs[%s] >= %s );' % (threadIndex, nextLabelID)
		else:
			footer = ''

		'''
		if n.iffalse:
			header = 'ASS_ELSE(%s, %s, %s)' % (condition, ifEnd+1, elseEnd+1) + '\n' + self._make_indent()
		else:
			if ifEnd > ifStart:
				header = 'ASS_THEN(%s, %s)' % (condition, ifEnd+1) + '\n' + self._make_indent()
			else: header = ''
		'''

		return header + s + self._make_indent() + footer


	def visit_Return(self, n):
		# ??? Note that the same function may at the same time
		# be passed as an argument to pthread_create() to spawn a thread, and
		# explicitly invoked.  Therefore, just checking whether a function
		# belongs to the set of threads is not sufficient here.
		#
		'''
		if (self.currentfunction != '__CSEQ_assert' and
			self.currentfunction not in self.Parser.funcReferenced and
			not self.atomicsection):
		'''
		if (self.currentfunction in self.Parser.threadName and
			self.currentfunction not in self.Parser.funcName):
			self.error("error: %s: return statement in thread '%s'.\n" % (self.name(), self.currentfunction))

		s = 'return'
		if n.expr: s += ' ' + self.visit(n.expr)
		return s + ';'


	def visit_Label(self, n):
		self.labelline[self.currentfunction, n.name] = self.stmtcount
		return n.name + ':\n' + self._generate_stmt(n.stmt)


	def visit_Goto(self, n):
		self.gotoline[self.currentfunction, n.name] = self.stmtcount
		extra = '<%s,%s>\n' % (self.currentfunction, n.name) + self._make_indent()
		extra = ''
		return extra + 'goto ' + n.name + ';'


	def visit_ID(self, n):
		if self.thisblocknode in self.Parser.blocknode:
			block = self.Parser.blocknode[self.thisblocknode]

			# If this ID corresponds either to a global variable,
			# or to a pointer...
			#
			# why is self.blockid does not work in this module, by the way? TODO
			#if ((self.__isGlobal(self.currentfunction, n.name) or self.Parser.ispointer(block,n.name)) and not
			if ((self.Parser.isglobalvariable(block,n.name) or self.Parser.ispointer(block,n.name)) and not
				n.name.startswith('__cs_thread_local_')):   # <---- review this. TODO
				self.globalaccess = True

		return n.name


	def visit_FuncCall(self, n):
		fref = self._parenthesize_unless_simple(n.name)
		args = self.visit(n.args)

		if fref in ('pthread_mutex_trylock',):
			self.error("%s not supported" % fref,snippet=True,lineno=True)

		if fref == '__VERIFIER_atomic_begin':
			if not self.visitfuncdef: self.atomicsection+=1
			return ''
		elif fref == '__VERIFIER_atomic_end':
			if not self.visitfuncdef: self.atomicsection-=1
			return ''
		elif fref.startswith('__VERIFIER_atomic_'):
			self.globalaccess = True   # TODO why? shouldn't be False instead? needs checking TODO
		elif fref == 'pthread_cond_wait':
			self.error('pthread_cond_wait in input code (use conditional wait converter module first)')

		# When a thread is created, extract its function name
		# based on the 3rd parameter in the pthread_create() call:
		#
		# pthread_create(&id, NULL, f, &arg);
		#                          ^^^
		#
		if fref == 'pthread_create': # TODO re-write AST-based (see other modules)
			fName = args[:args.rfind(',')]
			fName = fName[fName.rfind(',')+2:]
			fName = fName.replace('&', '')

			##print "checking fName = %s\n\n" % fName

			if fName not in self.threadname:
				self.threadname.append(fName)
				self.threadcount = self.threadcount + 1
				self.threadindex[fName] = self.threadcount
				args = args + ', %s' % (self.threadcount)
			else:
				# Reuse the old thread indexes when visiting multiple times
				args = args + ', %s' % (self.threadindex[fName])

			self.firstthreadcreated = True

		# Avoid using pointers to handle mutexes
		# by changing the function calls,
		# there are two cases:
		#
		#    pthread_mutex_lock(&l)   ->  __cs_mutex_lock(l)
		#    pthread_mutex_lock(ptr)  ->  __cs_mutex_lock(*ptr)
		#
		# TODO:
		#    this needs proper implementation,
		#    one should check that the argument is not referenced
		#    elsewhere (otherwise this optimisation will not work)
		#
		'''
		if (fref == 'pthread_mutex_lock') or (fref == 'pthread_mutex_unlock'):
			if args[0] == '&': args = args[1:]
			else: args = '*'+args
		'''

		# Optimization for removing __cs_thread_index variable from global scope
		'''
		if ((fref == 'pthread_mutex_lock') or (fref == 'pthread_mutex_unlock') or
				fref.startswith('pthread_cond_wait_')):
			threadIndex = self.Parser.threadIndex[self.currentfunction] if self.currentfunction in self.Parser.threadIndex else 0
			return fref + '(' + args + ', %s)' % threadIndex
		'''

		return fref + '(' + args + ')'


	def __scheduler(self,ROUNDS,THREADS):
		# the new main() is created according to the following sort of scheduling:
		#
		# main_thread    t1 t2    t1 t2   t1 t2    t1 t2     t1 t2    t1 t2      t1 t2    t1 t2    main_thread
		#
		main = ''
		main += "int main(void) {\n"

		''' Part I:
			Pre-guessed jump lenghts have a size in bits depending on the size of the thread.
		'''
		for r in range(0,ROUNDS):
			for t in range(0,THREADS+1):
				if str(t) in self.explicitround[r].split(',') or '+' in self.explicitround[r]:
					threadsize = self.visiblestmtcount[self.threadname[t]]
					#print("THREADNAME: %s   T:%s" % (self.threadname[t],t))
					#print("THREADSIZE: %s" % threadsize)
					k = int(math.floor(math.log(threadsize,2)))+1
					self.bitwidth['main','__cs_tmp_t%s_r%s' % (t,r)] = k

		k = int(math.floor(math.log(self.visiblestmtcount['main'],2)))+1
		self.bitwidth['main','__cs_tmp_t%s_r%s' % (0,ROUNDS)] = k

		''' Part II:
			Schedule pruning constraints.
		'''
		'''
		main += '\n'

		schedulesPruned = []  # remeember which rounds have been pruned

		for t in range(0,self.__threadbound+1):
			#print "thread %s,  name %s,   maxrepr %s,  threadsize %s" % (t,self.threadname[t],maxrepresentable, threadsize)
			threadsize = self.visiblestmtcount[self.threadname[t]]
			maxrepresentable =  2**int((math.floor(math.log(threadsize,2)))+1) - 1

			sumall = ''

			for r in range(0, ROUNDS):
				sumall += '__cs_tmp_t%s_r%s%s' % (t,r, ' + ' if r<ROUNDS-1 else '')

			if t == 0:
				sumall += ' + __cs_tmp_t0_r%s' % (ROUNDS)

			######if (maxrepresentable > threadsize+1) and int((math.floor(math.log(threadsize,2)))+1)+1 > 4:
			if (maxrepresentable > threadsize+1) and int((math.floor(math.log(threadsize,2)))+1)+1 > 4:
				schedulesPruned.append(True)
				if t == 0:
					wow =   int(math.ceil(math.log((maxrepresentable*(ROUNDS+1)),2)))
				else:
					wow =   int(math.ceil(math.log((maxrepresentable*ROUNDS),2)))
				##wow =   int(math.ceil(math.log((maxrepresentable*ROUNDS),2)))

				#main += "          unsigned __CSEQ_bitvector[%s] top%s = %s;\n" % (wow, t, threadsize)
				main += "          unsigned int __cs_top%s = %s;\n" % (t, threadsize)
				self.bitwidth['main','__cs_top%s' % t] = wow
				#main += "          unsigned __CSEQ_bitvector[%s] sum%s = %s;\n" % (wow, t, sumall)
				#main += "          __CSEQ_assume(sum%s <= top%s);\n" % (t,t)
			else:
				schedulesPruned.append(False)
		'''


		''' Part III:
		'''
		# 1st round (round 0)
		#
		round=0

		i=0
		t='main'

		main +="__CSEQ_rawline(\"/* round  %s */\");\n" % round
		main +="__CSEQ_rawline(\"    /* main */\");\n"
		main +="          __cs_thread_index = %s;\n" % i
		main +="          unsigned int __cs_tmp_t%s_r%s;\n" % (i,round)
		main +="          __cs_pc_cs[%s] = __cs_tmp_t%s_r%s;\n" % (i,i,round)
		main +="          __VERIFIER_assume(__cs_pc_cs[%s] > 0);\n" % i   # do not remove, faster analysis
		main +="          __VERIFIER_assume(__cs_pc_cs[%s] <= %s);\n" % (i,self.visiblestmtcount[t])
		main +="          main_thread();\n"
		main +="          __cs_pc[%s] = __cs_pc_cs[%s];\n" % (i,i)
		main +="\n"

		i = 1
		for t in self.threadname:
			if t == 'main': continue
			if i <= THREADS:
				if str(i) in self.explicitround[0].split(',') or '+' in self.explicitround[0]:
					main +="__CSEQ_rawline(\"    /* %s */\");\n" % t
					main +="          unsigned int __cs_tmp_t%s_r%s;\n" % (i,round)
					main +="          if (__cs_active_thread[%s]) {\n" % i
					main +="             __cs_thread_index = %s;\n" % i
					###main +="             __cs_pc_cs[%s] = __cs_pc[%s] + __cs_tmp_t%s_r%s;\n" % (i,i,i,0)
					main +="             __cs_pc_cs[%s] = __cs_tmp_t%s_r%s;\n" % (i,i,round)
					main +="             __VERIFIER_assume(__cs_pc_cs[%s] <= %s);\n" % (i,self.visiblestmtcount[t])
					main +="             %s(%s);\n" % (t, '__cs_threadargs[%s]') % (i)
					main +="             __cs_pc[%s] = __cs_pc_cs[%s];\n" % (i,i)
					main +="          }\n\n"
				i += 1

		# remaining rounds
		#
		for round in range(1,ROUNDS):
			i=0
			t='main'
			main +="__CSEQ_rawline(\"/* round  %s */\");\n" % round
			main +="__CSEQ_rawline(\"    /* main */\");\n"

			if str(i) in self.explicitround[round].split(',') or '+' in self.explicitround[round]:
				main +="          unsigned int __cs_tmp_t%s_r%s;\n" % (i,round)
				main +="          if (__cs_active_thread[%s]) {\n" % i
				main +="             __cs_thread_index = %s;\n" % i
				###main +="              __cs_pc_cs[%s] = __cs_pc[%s] + __cs_tmp_t%s_r%s;\n" % (i,i,i,round)
				main +="              __cs_pc_cs[%s] = __cs_tmp_t%s_r%s;\n" % (i,i,round)
				main +="              __VERIFIER_assume(__cs_pc_cs[%s] >= __cs_pc[%s]);\n" % (i,i)
				main +="              __VERIFIER_assume(__cs_pc_cs[%s] <= %s);\n" % (i,self.visiblestmtcount[t])
				main +="              main_thread();\n"
				main +="              __cs_pc[%s] = __cs_pc_cs[%s];\n" % (i,i)
				main +="          }\n\n"

			i = 1
			for t in self.threadname:
				if t == 'main': continue
				if i <= THREADS:
					if str(i) in self.explicitround[round].split(',') or '+' in self.explicitround[round]:
						main +="__CSEQ_rawline(\"    /* %s */\");\n" % t
						main +="          unsigned int __cs_tmp_t%s_r%s;\n" % (i,round)
						main +="          if (__cs_active_thread[%s]) {\n" % i
						main +="             __cs_thread_index = %s;\n" % i
						###main +="             __cs_pc_cs[%s] = __cs_pc[%s] + __cs_tmp_t%s_r%s;\n" % (i,i,i,round)
						main +="             __cs_pc_cs[%s] = __cs_tmp_t%s_r%s;\n" % (i,i,round)
						main +="             __VERIFIER_assume(__cs_pc_cs[%s] >= __cs_pc[%s]);\n" % (i,i)
						main +="             __VERIFIER_assume(__cs_pc_cs[%s] <= %s);\n" % (i, self.visiblestmtcount[t])
						main +="             %s(%s);\n" % (t, '__cs_threadargs[%s]') % (i)
						main +="             __cs_pc[%s] = __cs_pc_cs[%s];\n" % (i,i)
						main +="          }\n\n"
					i += 1

		# Last call to main()
		#
		main += "          unsigned int __cs_tmp_t0_r%s;\n" % (ROUNDS)
		main +="          if (__cs_active_thread[0]) {\n"
		main +="             __cs_thread_index = 0;\n"
		###main +="             __cs_pc_cs[0] = __cs_pc[0] + __cs_tmp_t0_r%s;\n" % (ROUNDS)
		main +="             __cs_pc_cs[0] = __cs_tmp_t0_r%s;\n" % (ROUNDS)
		main +="             __VERIFIER_assume(__cs_pc_cs[0] >= __cs_pc[0]);\n"
		main +="             __VERIFIER_assume(__cs_pc_cs[0] <= %s);\n" % (self.visiblestmtcount['main'])
		main +="             main_thread();\n"
		main +="          }\n\n"
		main += "   return 0;\n"
		main += "}\n\n"

		return main


	def __getmaxthreadsize(self,threads):
		i = maxsize = 0

		for t in self.threadname:
			if i <= threads:
				if i>0: lines += ', '
				maxsize = max(int(maxsize), int(self.visiblestmtcount[t]))

		return maxsize


	def __schedulercba(self,CONTEXTS,THREADS):
		round = 0

		main = ''
		main += "int main(void) {\n"
		main += '\n'

		main += '   unsigned int __cs_tid[%s];\n' % (CONTEXTS)
		self.bitwidth['main','__cs_tid'] = int(math.ceil(math.log(float(THREADS+1),2.0)))

		main += '   unsigned int __cs_cs[%s];\n' % (CONTEXTS)
		#self.bitwidth['main','__cs_cs'] = int(math.ceil(math.log(float(CONTEXTS),2.0)))
		self.bitwidth['main','__cs_cs'] =int(math.ceil(math.log(float(self.__getmaxthreadsize(THREADS)+1),2.0)))


		# variant I: tid multiplexer (to be used instead of __cs_tid)
		'''
		main += '   unsigned int prova[%s][%s];\n' % (CONTEXTS,threads+1)
		self.bitwidth['main','prova'] = 1

		boh = ''
		for u in range(0,threads+1):
			truefalse = 1 if u==0 else 0
			boh += 'prova[0][%s] == %s;' % (u, truefalse)
		main +=   '%s;\n' % boh
		'''

		#main += '   int tid;\n'
		main += '   int k;\n'
		main += '   __cs_tid[0] = 0;\n'

		####main += '     unsigned int guess[%s][%s] = {};' %(CONTEXTS,threads+1)
		####self.bitwidth['main','guess'] =int(math.ceil(math.log(float(self.__getmaxthreadsize(THREADS)),2.0)))


		'''
		for k in range (0,CONTEXTS):
			for t in range(0,threads+1):
				name = '__cs_out_%s_%s' % (k,t)
				main += '         unsigned int %s;' % (name)
				self.bitwidth['main', name] =int(math.ceil(math.log(float(self.visiblestmtcount[self.threadname[t]]),2.0)))
				#main += '         guess[%s][%s] = %s;' % (k,t,name)
		'''


		for k in range (0,CONTEXTS):
			main +="__CSEQ_rawline(\"/* context %s */\");\n" % k
			main += '      k = %s;\n' % k

			if k==0:
				t=0
				main += '         __cs_thread_index = %s;\n' % t
				#name = '__cs_out_%s_%s' % (k,t)
				#main += '         __VERIFIER_assume(__cs_out_%s_%s >= __cs_pc_cs[%s]);\n' %(k,t,t)
				#main += '         __VERIFIER_assume(__cs_out_%s_%s <= __cs_thread_lines[%s]);\n' %(k,t,t)
				#main += '         __cs_pc_cs[%s] = __cs_out_%s_%s;\n' %(t,k,t)

				main += '         __VERIFIER_assume(__cs_cs[%s] >= __cs_pc_cs[%s]);\n' %(k,t)
				main += '         __VERIFIER_assume(__cs_cs[%s] <= __cs_thread_lines[%s]);\n' %(k,t)
				main += '         __cs_pc_cs[%s] = __cs_cs[%s];\n' %(t,k)

				main += '         %s(%s);\n' %('main_thread' if t==0 else 't%s_0'%t, '' if t==0 else '0')
				main += '         __cs_pc[%s] = __cs_pc_cs[%s];\n' %(t,t)

			else:
				for t in range(0,THREADS+1):
					# variant I: tid multiplexer (to be used instead of __cs_tid)
					'''
					tidcheck = ''
					for u in range(0,threads+1):
						conjunct = '' if u==0 else '& '
						truefalse = '' if u==t else '!'
						tidcheck += '%s %sprova[k][%s] ' % (conjunct,truefalse,u)
					'''
					tidcheck = '__cs_tid[%s] == %s' %(k,t)

					#name = '__cs_out_%s_%s' % (k,t)

					main += '      if (%s) {\n' %(tidcheck)
					#main += '         tid = %s;\n' %t
					main += '         __cs_thread_index = %s;\n' % t
					main += '         __VERIFIER_assume(__cs_active_thread[%s]);' %(t)

					#main += '         __VERIFIER_assume(__cs_out_%s_%s >= __cs_pc_cs[%s]);\n' %(k,t,t)
					#main += '         __VERIFIER_assume(__cs_out_%s_%s <= __cs_thread_lines[%s]);\n' %(k,t,t)
					#main += '         __cs_pc_cs[%s] = __cs_out_%s_%s;\n' %(t,k,t)

					main += '         __VERIFIER_assume(__cs_cs[%s] >= __cs_pc_cs[%s]);\n' %(k,t)
					main += '         __VERIFIER_assume(__cs_cs[%s] <= __cs_thread_lines[%s]);\n' %(k,t)
					main += '         __cs_pc_cs[%s] = __cs_cs[%s];\n' %(t,k)

					main += '         %s(%s);\n' %('main_thread' if t==0 else self.threadname[t], '' if t==0 else '__cs_threadargs[%s]'%t)
					main += '         __cs_pc[%s] = __cs_pc_cs[%s];\n' %(t,t)
					###main += '      } %s\n' % ('else' if t<threads else 'else assume(0);')
					main += '      } %s\n' % ('' if t<THREADS else '')

		main += "}\n\n"

		return main


	def visit_Decl(self, n, no_type=False):
		# There are two transformations for declaration statements of local variables.
		#
		# 1. split the type declaration from the initialisation, e.g.:
		#       int x = 3; ---> int x; x = 3;
		#
		# 2. force static storage class (unless already static), e.g.:
		#       int y; --> static int y;
		#

		# no_type is used when a Decl is part of a DeclList, where the type is
		# explicitly only for the first delaration in a list.
		#
		#s = n.name if no_type else self._generate_decl(n)
		#
		#if n.bitsize: s += ' : ' + self.visit(n.bitsize)

		'''
		got_through = False

		if n.name and self.thisblocknode:
			block = self.Parser.blocknode[self.thisblocknode]

			if block == self.Parser.blockdefid(block,n.name):
				print ("local variable: %s (block:%s)" % (n.name,self.blockid))
				#print ("block: %s" % self.Parser.blocknode[self.thisblocknode])
				#print ("globl: %s" % self.Parser.isglobalvariable(self.Parser.blocknode[self.thisblocknode],n.name))
				#print (" type: %s" % type(n))
				#print ("defid: %s\n" % self.Parser.blockdefid(self.Parser.blocknode[self.thisblocknode],n.name)
				got_through = True
			#else:
			#	print ("(a) other variable: %s" % n.name)
		#else:
		#	print ("(b) other symbol: %s" % n.name)
		'''

		#if self.currentfunction != '' and n.name in self.Parser.varNames[self.currentfunction]:
		if self.currentfunction != '' and not self.Parser.isglobalvariable(self.blockid,n.name) and n.name != self.currentfunction:
			if 'static' not in n.storage: n.storage.append('static')
			if 'const' in n.quals: n.quals.remove('const')

			decl = ''

			if n.init:
				# Break up declaration and initialisation into two statements.
				oldinit = n.init
				n.init = None # temporarily disable generation of init expression
				declnoinit = super(self.__class__, self).visit_Decl(n,no_type)   # decl without init expr
				declinit = self.visit(oldinit)
				n.init = oldinit
				decl = declnoinit + '; %s = %s' % (n.name,declinit)
			else:
				# TODO: this warning should exclude any temporary variable introduced by any of the previous modules,
				#       such as __cs_tmp_if_cond, __cs_retval_, and so on.
				#

				# shouldn't bother about variables introduced by previous modules not being initialised
				if n.name and not n.name.startswith('__cs_param_') and not n.name.startswith('__cs_retval_') and '__cs_tmp_' not in n.name:
					v = self.varnamesmap[n.name] if n.name in self.varnamesmap else n.name
					self.warn("uninitialised local variable %s" % (self.varnamesmap[n.name]))

				decl = super().visit_Decl(n,no_type)

			return decl

		if n.name and 'pthread_mutex_t' in n.name and n.storage and 'static' in n.storage:
			#self.error("static storage class for locks not supported", snippet=True)
			self.warn("static storage class for locks not supported", snippet=True)
			self.staticlocks += n.name + ';\n'
			return ';'

		return super(self.__class__, self).visit_Decl(n,no_type)


	# Check whether the given AST node:
	# accesses global memory, or
	# uses a pointer or references (*), or
	# uses dereferencing (&).
	#
	# TODO: should provide a mechanism to refine this very rough overapproximation
	#       with some (possibly external) pre-analysis.
	#
	def checkglobalaccess(self,stmt):
		if self.atomicsection>0:
			return False  # if between atomic_begin() and atomic_end() calls no context switchs needed..

		oldStmtCount = self.stmtcount             # backup counters
		oldMaxInCompound = self.maxcompound
		oldGlobalMemoryAccessed = self.globalaccess
		oldatomicsection= self.atomicsection

		globalAccess = False
		self.globalaccess = False

		if type(stmt) not in (pycparser.c_ast.If,): tmp = self._generate_stmt(stmt)
		else: tmp = self._generate_stmt(stmt.cond)

		globalAccess = self.globalaccess

		self.stmtcount = oldStmtCount             # restore counters
		self.maxcompound = oldMaxInCompound
		self.globalaccess = oldGlobalMemoryAccessed
		self.atomicsection = oldatomicsection

		return globalAccess



