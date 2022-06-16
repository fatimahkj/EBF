""" CSeq Program Analysis Framework
	symbol table generation module

Generate symbol-table and a few other data structures
(this module is always used at the beginning of a Translator module).

Credits:
    This module is built on top of
    pycparserext by Andreas Klockner, which extends
    pycparser by Eli Bendersky (BSD license), which in turn embeds
    PLY, by David M. Beazley.

Author:
    Omar Inverso

Changes:
    2021.02.04  fixed self.currentStruct
    2021.02.02  added fblock[] to store the blockid of every new function body
    2021.02.01  fix: global arrays now detected and added to new symbol table
    2021.01.31  revised isglobal() macro: function parameters are not global variables
    2020.11.25  new macro decl() to fetch the declaration node of a symbol [SV-COMP 2021]
    2020.05.09  simplified variable scope resolution
    2020.03.28 (CSeq 2.0)
    2020.03.28  block-based lookup macros (isglobal(),ispointer(), etc.), etc.
    2019.11.27 [SV-COMP 2020]
    2019.11.26  initial implementation of the new symbol table (does not replace the old one for now)
    2019.11.24  bugfix: now tracking simple typedefs (e.g., typedef a b;)
    2019.11.15 (CSeq 1.9) pycparserext
    2019.11.15  no longer mapping pthread_xyz function identifiers
    2019.11.13  support for pycparser 2.19 (backwards compatible)
    2019.11.13  no longer overriding pycparser's generate_type
    2019.03.09  line no. extraction for varReferenced, varOccurrence
    2018.11.23 [SV-COMP 2019] fixed counting of explicit function calls
    2018.11.19  tracking (over-approximated) sources of non-determinism (see varrange and nondetfound)
    2018.11.03  fix: threadcallcnt initialised to zero as soon as a new function is parsed (avoids exceptions)
    2018.11.02  counting the overall number of occurrences of each function identifier (see funcIdCnt)
    2018.11.02  comment to clarify threadIndex+threadCount mechanism
    2018.11.02  storing the stack of AST nodes currently being visited
    2018.05.26 (CSeq 1.5-parallel) first submissions for parallel cba
    2018.05.26  no longer storing the entire body of functions (self.funcBody)
    2018.05.26  added new data structs for extra reasoning, exp. useful for inlining (funcExitPointsCnt,lastStmtNode,lastFuncStmtNode)
    2018.01.24  disabled new symbol table bookkeeping (not needed for now)
    2018.01.24  removed funcBlock[] (inefficient and useless)
    2018.01.24  integrated changes (need to check them) from SVCOMP'16 version (see below):
    2016.11.21  add safe check for node.coord before extracting linenumber (merged change)
    2016.08.16  add self.varInAssignment and self.varNoNeedInit to track local variables (merged change)
    2015.06.23  re-implemented 3rd parameter extraction to  pthread_create()  call (fName)
    2015.01.07  bugfix: calculating when variables are referenced and referenced not working with arrays
    2014.10.29 (newseq-0.6c) (CSeq 1.0beta) [SV-COMP 2015]
    2014.10.29  more information on threads (threadindex map)
    2014.10.27 (newseq-0.6a)
    2014.10.27  improved symbol table about variables' details (exact line(s) where they are referenced, dereferenced, and where they occur)
    2014.03.16  amended the mechanism to calculate the list of functions (varNames)
    2014.03.16  introduced self.reset() for resetting all the data structs
    2014.03.09  anonymous structs no longer supported (they are assigned a name in merger.py)
    2014.03.04  symbol table: removed unused variables names in nested parameter declarations (e.g. parameters of a parameter, for example of a function)
    2014.02.25  bugfix: varNames
    2014.02.19  added  self.nodecoords[] to store the nodes' coords

To do:
  - tracking of non-deterministic variables should be reimplemented as an external module
  - major: improve representation of sub-symbols (e.g., structure or union fields) and make it uniform with the rest
  - major: get rid of _generate_decl() for populating the parserdata structures
   (see TODO in visit_FuncDef)
  - major: replace all the old data structures with the new symbol table,
    in particular varTypeUnexpanded (do we really need varType at all?, also
    replace for good varReferenced, varDeReferenced, and varOccurrence, with
    simple counters instead similar to funcIdCnt. Use a uniform naming.
  - when a symbol is declared twice (e.g., a function), check that the definition match.


  - need to clearly differentiate between
    (a) internal data that is only used while parsing and has no meaning externally (insert underscores?)
    (b) data that has an external meaning and can be used by a Translator module etc.
    (c) macros that can be accessed externally too.

  - enumerators are not currently stored (unlike struct fields, for instance)
  - use simple and short method names, all lowercase when clear enough
  - finalise and test block-based symbol table thoroughly
  - handling and propagation of non-deterministic variables is too specific, and
    should be moved to an external module
  - use more direct AST-based information fetching routines, such as
    len(self.Parser.funcASTNode[fref].decl.type.args.params)
    for checking the number of parameters of a function
   (study pycparser/c_ast.py for the fields)

  - avoid cluttering .symbols for function parameters of extern functions, etc. (e.g., extern int (int useless_parameter_to_track); )
   (should improve performance with files with large headers or preprocessed files)

Notes:
  - Keep this module as simple and lightweight as possible:
    when some kind of analysis is too heavy and specific, write a separate module.
  - A symbol may not be precisely visible within the whole block it was declared (as well as within its nested blocks), but
    only from the point it was declared (yes, C89 was simpler).
    This means that the scope of a symbol is not a block, but a block + an offset.
    Currently, the new symbol table does not have that precision.
  - Use data structures for quick access information (e.g., names of a variable in a function).
  - Use macros for information that can be accessed quickly by visiting small parts of the syntax tree.
  - Keep overriding to the minumum and always use super() whenever possible.

Things to handle here:
  - replace everything like this: if 'FuncDecl' in str(n.type)
    with something like this: if type(n) == pycparser.c_ast.FuncDecl, or
    isinstance(n.type,pycparser.c_ast.FuncDecl)
  - replace data such as self.funcIsVoid[] with macros that visit the AST only at need
   (would have to update all the modules accordingly)
  - typedef expansion
  - add extraction of any extra information about the code needed in later modules.

Prerequisites:
  - pycparser >= 2.20
  - input must be preprocessed (i.e., no # directives,
  - no linemarkers, as pycparser will not handle them).

"""

import pycparserext.ext_c_parser, pycparser.c_ast, pycparserext.ext_c_generator
import core.utils


class Parser(pycparserext.ext_c_generator.GnuCGenerator): #class Parser(pycparser.c_ast.NodeVisitor):
	_finished = False    # Parsing mode on: populating symbol table.
	_debug = False       # Print out the details while building the symbol table
	_extended = False    # Enable symbol table extensions


	def __init__(self,reduce_parentheses=False):
		self.reset()
		self.reduce_parentheses = reduce_parentheses   # pycparser >= 2.20


	def reset(self):
		# Blocks
		self.block = [0]            # Identifier of the block being parsed, as a list of integers.
		self.blockid = '0'          # Identifier of the block being parsed, as a string '0.y.z'.
		                            #
		                            # The identifier of the global scope is 0,
		                            # that of first nested block within block 0 is 0.0, and so on.
		                            # Clearly there is no block 1 (because all blocks are nested blocks of 0).
		                            #
		                            # Each pair of braces "{...}" delimits a block,
		                            # except for the braces enclosing the fields within a declaration of structs,
		                            # (as in "struct s { this is not a new block }"), and similar cases.

		self.blockd = 0             # current block depth (used internally to assign blockids)
		self.blockcount = 0         # block no. at the current depth (used internally to assign blockids)

		# Symbols
		self.symbols = {}           # Node where a symbol is defined,
                                    # indexed by [blockid,identifier].
                                    #
                                    # blockid indicates the block where the symbol occurs,
                                    # which is necessary for scope resolution.
                                    #
                                    # Symbol here means: identifiers of variables and functions, and TODO enumerators;
                                    # basically anything which has a meaning in the program when
                                    # considered in isolation and in the correct scope.
                                    #
                                    # The name of a structure is not a symbol.
                                    # The name of a field of a structure is not a symbol either, etc.

		#self.symbolscount = {}      # No. of occurrences for [blockid,identifier]'s.
		#                            # This should really go away as it makes everything more heavy. TODO

		self.vars = {}              # Node for variable declarations [blockid,id],
		                            # incl. function parameters and constants.

		self.funcs = {}             # Node for function declarations [0,identifier]
		self.fbody = {}             # Node of function definitions [0,identifier]
		self.params = {}            # Node for function parameters definition [blockid,id] - to differentiate between local variables and parameters
		self.typedefs = {}          # Node for typedefs [blockid,id]

		self.structs = {}           # Node for stucture definitions [blockid,id]
		self.unions = {}            # Node for unions [blockid,id]
		self.enums = {}             # Node for enums [blockid,id]

		self.blocknode = {}         # blockid for a given compound block node in the syntax tree

		self.blockidf = None        # blockid of the function body currently being visited
		self.fblock = {}            # blockid of a function identifier

		self.visitingfdecl = False  # currently visiting a function prototype (not the body)
		self.___up = None




		#  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
		#              extended symbol table: functions and threads
		#  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
		self.threadName = []           # all threads names (i.e. functions used as argument to pthread_create())
		self.threadCount = 0           # pthread create()s found so far (not counting duplicates, i.e. when the same function is used to create multiple threads)
		self.threadIndex = {}          # index of the thread = value of threadcount when the pthread_create to that thread was discovered
		self.threadCallCnt = {}        # number of times a function is explicitly used to generate a thread (by calling pthread_create())

		self.funcDecl = {}             # function declarations, only for functions declared and defined in different statements, or not defined at all.
		self.funcIdCnt = {}            # number of occurrences of each function identifier (including calls and excluding declarations)
		self.funcCallCnt = {}          # number of calls to a function identifier

		self.funcName = ['']           # all functions names (consider '' to be a special function to model global scope)
		self.funcASTNode = {}          # AST node for the function definitions, indexed by function name

		self.funcExitPointsCnt = {}    # Number of return statements in the function

		self.lastStmtNode = ''         # last statement generated (as an AST node)
		self.lastFuncStmtNode = {}     # last statement for each function (as an AST node)

		self._visitedIDnodes = []



		#  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
		#                      old things that work fine
		#  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
		self._currentfunct = ''        # name of the function being parsed ('' = none)

		self.indent_level = 0
		self.INDENT_SPACING = '   '


		#  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
		#                          old stuff to review
		#  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
		self.structsName = []
		self.currentStruct = ''
		#self.visitingField = False     # needed to differentiate between variables and fields identifiers


		# tracking of non-deterministic variables (disabled now due to new symbol table, should be implemented as a separate module anyway)
		self.varrange = {}           # a constant value if constant, or * if nondet
		self._nondetfound = False    # a nondeterministic expression has been visited since last re-set
		                             #(i.e. a variable previously known to be non-deterministic or call to nondet init)

		# list of line no. where an occurrence, referencing, or dereferencing  happened
		#self.varOccurrence = {}      # any occurrence (does not include the very first time a variable occurs, i.e. on the left hand side of its own declaration)
		#self.varReferenced = {}      # &var
		#self.varDeReferenced = {}    # *var

		# Handling of typedefs.
		# We put in the first variable below the last part of a typedef statement,
		# and in the second variable its correspondent expansion.
		#
		# Anonymous typedefs are no exception, as they are assigned an internal name to be used as described.

		# = True while parsing the subtree for a struct (or union) declaration
		self.parsingstructunionenum = False

		# set to True while parsing typedef blocks
		#self.parsingTypedef = False

		self.stacknodes = []  # AST nodes

	def loadfromstring(self,string,extended=False):
		self._finished = False
		self._extended = extended
		#self.ast = pycparser.c_parser.CParser().parse(string)    # pycparser
		self.ast = pycparserext.ext_c_parser.GnuCParser().parse(string)   # pycparserext
		self.visit(self.ast)
		self._finished = True


	def printsymbols(self):
		return
		print("\n\nSymbols:")

		for f in self.symbols:
			print("  %s" % str(f))
			print("      declared in block %s" % (self.blockdefid(f[0],f[1])))
			print("      function? %s" % (self.isfunction(f[0],f[1])))
			print("      variable? %s" % (self.isvariable(f[0],f[1])))
			print("      global variable? %s" % (self.isglobalvariable(f[0],f[1])))
			print("      local variable? %s" % (self.islocalvariable(f[0],f[1])))
			print("      pointer? %s" % (self.ispointer(f[0],f[1])))
			print("      array? %s" % (self.isarray(f[0],f[1])))
			print("")
			print("")

		#print("\nVariables: %s" % self.vars)


	def shownodes(self):
		from optparse import OptionParser
		import inspect
		print([entry for entry in dir(pycparser.c_generator.CGenerator) if not entry[0].startswith('_')])


	def _make_indent(self, delta=0): return (self.indent_level+delta) * self.INDENT_SPACING


	def highlight(self,text): return core.utils.colors.HIGHLIGHT+text+core.utils.colors.NO


	def visit(self,node):
		method = 'visit_' + node.__class__.__name__
		self.stacknodes.append(type(node))

		#s = ''
		#for i in self.stacknodes:
		#	p = "%s" % str(i)
		#	s += '/'+p[p.rfind('.')+1:-2]
		#
		#print("--> %s" % s)

		ret = getattr(self,method,self.generic_visit)(node)
		self.stacknodes.pop()
		return ret

	#def visit_Cazzo(self,n,no_type=False):
	def visit_Decl(self,n,no_type=False):
		#print("\n- - - - - - - -")
		#n.show(attrnames=True,nodenames=True,showcoord=True)
		#print("\n-.-.-.-.-.-.-.-")

		# No changes to the symbol table once finished building it.
		if self._finished: return super().visit_Decl(n)

		# In the general case,
		# we store exactly the identifier of the block
		# where a symbol first occurs (i.e., self.blockid).
		#
		# For function parameters, however,
		# we store the identifier of the function body block (i.e., self.blockidf):
		# a function parameter is considered a local variable
		# which is visible in the body of the function.
		#
		# Can n.name be none? Yes.  For example:
		#
		#     	struct S1 { int field_a; };
		#
		# In the above statement no variable is declared, so n.name is None.
		#
		if n.name:
			c = n.coord
			b = self.blockid
			bf = self.blockidf

			sym = n.name    # symbol
			typ = n.type    # type

			psym = self.___up.name if hasattr(self.___up,'name') else None   # parent symbol
			ptyp = self.___up   # parent type

			if self._debug:
				tshort = str(type(typ))
				tshort = tshort[tshort.rfind('.')+1:-2]
				psshort = psym if psym else ''
				ptshort = str(type(ptyp))
				ptshort = ptshort[ptshort.rfind('.')+1:-2] if 'NoneType' not in ptshort else ''
				print("%s/%s sym:[%s] typ:[%s] psym:[%s] ptyp:[%s]: " % (c,b,self.highlight(sym),tshort,psshort,ptshort), end='')

			# Function identifiers.
			#if isinstance(n.type,pycparser.c_parser.FuncDecl):
			if isinstance(n.type,pycparserext.ext_c_parser.FuncDeclExt):
				if self._debug: print(self.highlight("function"))
				self.symbols[self.blockid,sym] = n
				self.funcs[self.blockid,sym] = n
			elif (isinstance(n.type,pycparser.c_ast.TypeDecl) or isinstance(n.type,pycparser.c_ast.PtrDecl) or isinstance(n.type,pycparser.c_ast.ArrayDecl)):
				# Structure fields (case 1).
				if not psym and isinstance(ptyp,pycparser.c_ast.Struct):
					if self._debug: print(self.highlight("anonymous structure field (discarded)"))
				# Global variables.
				#
				# There is no difference between the syntax trees
				# for declaring a global variable or a local one, but
				# the scopes are different.
				elif not psym and not ptyp and self.blockid=='0':
					if self._debug: print(self.highlight("global variable"))
					self.symbols[self.blockid,sym] = n
					self.vars[self.blockid,sym] = n
				# Local variables.
				elif not psym and not ptyp and self.blockid!='0':
					if self._debug: print(self.highlight("local variable"))
					self.symbols[self.blockid,sym] = n
					self.vars[self.blockid,sym] = n

				# Structure fields (case 2).
				elif psym and isinstance(ptyp,pycparser.c_ast.Struct):
					if self._debug: print(self.highlight("structure field (discarded)"))

				# Function parameters.
				elif psym and ('0',psym) in self.funcs:
					if self._debug: print(self.highlight("function parameter"))
					self.symbols[self.blockidf,sym] = n   # <--- note blockidf in place of blockid
					self.vars[self.blockidf,sym] = n      # <--- note blockidf in place of blockid

				elif psym and ('0',psym) not in self.funcs:
					pass
					#####if self._debug: print(self.highlight("AAA ----undefined---- (case 1)"))
					#####print("AAA error 1: symbol table: %s/%s unable to handle symbol '%s' syntax tree node type %s" % (n.coord,self.blockid,n.name,type(n.type)))
			# Unhandled case.
			else:
				if self._debug: print("AAA  >>>   ----undefined---- (case 2)")
				print("AAA error 2: symbol table: %s/%s unable to handle symbol '%s' syntax tree node type %s" % (n.coord,self.blockid,n.name,type(n.type)))
				exit(1)
				'''
				# Local variables.
				if  isinstance(pt,pycparser.c_ast.FuncDef) and self.blockid!='0':
					if self._debug: print("  >>>  local variable [%s]" % s)
					self.symbols[self.blockid,s] = n

				# Function parameters (from within a function definition).
				elif isinstance(pt,pycparser.c_ast.FuncDef) and self.blockid=='0':
					if self._debug: print("  >>>  function parameter [%s]" % s)
					self.symbols[self.blockidf,s] = n    # <--- note blockidf in place of blockid

				# Function parameters (from within a function prototype) e.g., void f(int this_one);
				elif pt is None and self.blockid=='0':
					if self._debug: print("  >>>  function parameter [%s] (discarded)" % s)

				# Structure fields.
				elif isinstance(pt,pycparser.c_ast.Struct):
					if self._debug: print("  >>>  field [%s] for structure [%s] (discarded)" % (s,ps))

				# Union field.
				elif isinstance(pt,pycparser.c_ast.Union):
					if self._debug: print("  >>>  field [%s] for union [%s] (discarded)" % (s,ps))

				# Unhandled case.
				'''

			# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

			'''
			if not self.visitingfdecl:
				self.symbols[self.blockid,s] = n
			elif self.visitingfdecl and isinstance(n.type,pycparserext.ext_c_parser.FuncDeclExt):
				self.symbols[self.blockid,s] = n
			elif self.visitingfdecl and not isinstance(n.type,pycparserext.ext_c_parser.FuncDeclExt):
				self.symbols[self.blockidf,s] = n
			'''

			# Structures, unions, or enumerative types
			#elif isinstance(n.type,pycparser.c_ast.Struct):
			#	if self._debug: print("  -->  (2a) structure '%s' declared" % n.type.name)
			#	self.structs[self.blockid,n.type.name] = n.type
			#elif isinstance(n.type,pycparser.c_ast.Union):
			#	if self._debug: print("  -->  (2b) union '%s' declared" % n.name)
			#	self.unions[self.blockid,n.type.name] = n.type
			#elif isinstance(n.type,pycparser.c_ast.Enum):
			#	if self._debug: print("  -->  (2c) enum '%s' declared" % n.name)
			#	self.enums[self.blockid,n.type.name] = n.type

			# Function parameters (note that here we use self.blockidf and not self.blockid for indexing).
			'''
			if self.visitingfdecl:
				if isinstance(n.type,pycparser.c_ast.TypeDecl) or isinstance(n.type,pycparser.c_ast.PtrDecl) or isinstance(n.type,pycparser.c_ast.ArrayDecl):
					if self._debug: print("  -->  (2) parameter '%s' for function '%s'" % (n.name,self._currentfunct))
					self.vars[self.blockidf,n.name] = n
				else:
					print("error: symbol table: %s/%s '%s' unable to handle function parameter of type %s" % (self.blockid,n.coord,n.name,type(n.type)))
					exit(1)
			'''

			# Structure or enum fields.
			'''
			elif self.parsingstructunionenum:
				if isinstance(n.type,pycparser.c_ast.TypeDecl) or isinstance(n.type,pycparser.c_ast.PtrDecl) or isinstance(n.type,pycparser.c_ast.ArrayDecl):
					if self._debug: print("  -->  (3) field '%s' for structure '%s'" % (n.name,self.currentStruct))
					#pass
			'''

			# variables of any type (incl. arrays, pointers, and any combinations thereof)
			'''
			elif isinstance(n.type,pycparser.c_ast.TypeDecl) or isinstance(n.type,pycparser.c_ast.PtrDecl) or isinstance(n.type,pycparser.c_ast.ArrayDecl):
				if self._debug: print("  -->  (4)  variable '%s'" % (n.name))
				self.vars[self.blockid,n.name] = n
			'''
			'''
				#print("   type: %s" % (type(n.type.type)))

				# e.g., struct S { ... } var;
				# e.g., struct { ... } var;   <--- anonymous structure, n.type.type.name will be None

				if isinstance(n.type.type,pycparser.c_ast.Struct):
					if n.type.type.decls:
						if self._debug: print("  -->  (4aa) new structure '%s' declared" % (n.type.type.name))
						self.structs[self.blockid,n.type.type.name] = n.type.type

				if isinstance(n.type.type,pycparser.c_ast.Union):
					if n.type.type.decls:
						if self._debug: print("  -->  (4aa) new union '%s' declared" % (n.type.type.name))
						self.unions[self.blockid,n.type.type.name] = n.type.type

				#if isinstance(n.type.type,pycparser.c_ast.Enum):
				#	if n.type.type.decls:
				#		if self._debug: print("  -->  (4aa) new enum '%s' declared" % (n.type.type.name))
				#		self.unions[self.blockid,n.type.type.name] = n.type.type
			'''
			'''
				if isinstance(n.type.type,pycparser.c_ast.Struct):
					if n.type.type.decls:
						if self._debug: print("  -->  (4ba) new structure '%s' declared" % (n.type.type.name))
						self.structs[self.blockid,n.type.type.name] = n.type.type

				if isinstance(n.type.type,pycparser.c_ast.Union):
					if n.type.type.decls:
						if self._debug: print("  -->  (4bb) new structure '%s' declared" % (n.type.type.name))
						self.unions[self.blockid,n.type.type.name] = n.type.type
			'''

		oldlast = self.___up
		self.___up = n
		s = super().visit_Decl(n)
		self.___up = oldlast

		if self._extended:
			# Store function declarations.
			if ((isinstance(n.type,pycparser.c_ast.FuncDecl) or
				isinstance(n.type,pycparserext.ext_c_parser.FuncDeclExt)) and
				self._currentfunct == ''):
				self.funcDecl[n.name] = s

			# Initialise counters for function identifiers.
			if isinstance(n.type,pycparserext.ext_c_parser.FuncDeclExt): # isinstance(n.type,pycparser.c_parser.FuncDecl)
				if n.name not in self.funcCallCnt: self.funcCallCnt[n.name] = 0
				if n.name not in self.funcIdCnt: self.funcIdCnt[n.name] = 0
				if n.name not in self.threadCallCnt: self.threadCallCnt[n.name] = 0

		return s


	def visit_Enum(self,n):
		oldParsingStruct = self.parsingstructunionenum
		self.parsingstructunionenum = True
		s = super().visit_Enum(n)
		self.parsingstructunionenum = oldParsingStruct

		return s


	def visit_FuncCall(self, n):
		fref = self._parenthesize_unless_simple(n.name)
		args = self.visit(n.args)

		# Tracks sources of non-determinism (needs refinement TODO)
		#if fref.startswith('__VERIFIER_nondet') or fref.startswith('__CSEQ_nondet'):
		#	self._nondetfound = True

		if self._extended:
			# Counts function calls etc.
			if fref not in self.funcCallCnt: self.funcCallCnt[fref] = 1
			else: self.funcCallCnt[fref] += 1

			# When a thread is created, extract its function name
			# based on the 3rd parameter in the pthread_create() call:
			#
			# pthread_create(&id, NULL, f, &arg);
			#                          ^^^
			#
			if fref == 'pthread_create':
				fName = self._extractfname(n.args.exprs[2])

				if fName not in self.threadCallCnt: self.threadCallCnt[fName] = 0

				if self.threadCallCnt[fName] == 0:
					self.threadName.append(fName)
					self.threadCallCnt[fName] = 1;
					self.threadCount = self.threadCount + 1
					self.threadIndex[fName] = self.threadCount
				else:
					self.threadCallCnt[fName] += 1

				# Adjust the overall occurrence count for fName
				# as now this node has been visited twice.
				if fName in self.funcIdCnt: self.funcIdCnt[fName] -=1

		return fref + '(' + args + ')'


	# Note: function definition = declaration + body.
	# This method is not called when parsing simple declarations of function (i.e., function prototypes).
	#
	def visit_FuncDef(self,n):
		#oldlast = self.___up
		#self.___up = n

		self._currentfunct = n.decl.name

		# Index of the compound block
		# where the body is going to be defined
		# later in this function.
		self.blockidf = self.blockid + '.%s' % self.blockcount
		self.fblock[self._currentfunct] = self.blockidf
		#print("fdefblockid = %s" % (self.blockidf))

		# Note: the function definition is in two parts:
		#       one is 'decl' and the other is 'body'

		self.visitingfdecl = True
		decl = self.visit(n.decl)
		self.visitingfdecl = False

		self.fbody['0',n.decl.name] = n.body

		body = self.visit(n.body)
		funcBlock = decl + '\n' + body + '\n'

		if self._extended:
			if n.decl.name not in self.funcName: self.funcName.append(n.decl.name)
			if n.decl.name not in self.funcExitPointsCnt: self.funcExitPointsCnt[n.decl.name] = 0

			self.funcASTNode[n.decl.name] = n
			self.lastFuncStmtNode[self._currentfunct] = self.lastStmtNode

		self.blockidf = None
		self._currentfunct = ''

		#self.___up = oldlast

		return funcBlock


	def visit_Compound(self,n):
		# Update block counters before visiting n
		self.blockd += 1
		oldblockcount = None

		if self.blockd >= len(self.block):             # visiting a nested block
			oldblockcount = self.blockcount
			self.block.append(self.blockcount)
			self.blockid = '.'.join(str(self.block[i]) for i in range(0,len(self.block)))
			self.blockcount = 0
		else:                               # visiting a block at the same depth
			self.block.pop()
			self.block.append(self.blockcount+1)
			self.blockid = '.'.join(str(self.block[i]) for i in range(0,len(self.block)))
			self.blockcount +=1

		# Actual visit.
		self.blocknode[n] = self.blockid   # stores blockid for AST node n

		s = self._make_indent() + '{\n'
		self.indent_level += 1

		if n.block_items:
			for stmt in n.block_items:
				newStmt = self._generate_stmt(stmt)
				s += newStmt
				self.lastStmtNode = stmt

		self.indent_level -= 1
		s += self._make_indent() + '}\n'

		# Update block counters after visiting n
		if oldblockcount is not None:                  # visiting a nested block
			self.blockcount = oldblockcount+1
			self.block.pop()
			self.blockid = '.'.join(str(self.block[i]) for i in range(0,len(self.block)))
		else:                               # visiting a block at the same depth
			pass

		self.blockd -= 1

		return s


	'''
	def visit_ID(self,n):
		if not self.visitingField:
			bid = self.blockdefid(self.blockid,n.name)

			if (bid,n.name) in self.symbols:
				self.symbolscount[bid,n.name] += 1

		# Tracking of non-deterministic variables.
		#if (self._currentfunct,n.name) in self.varrange and self.varrange[self._currentfunct,n.name] == '*':
		#	#print "A propagating non-determinism due to variable (%s,%s)" % (self._currentfunct,n.name)
		#	self._nondetfound = True
		#elif ('',n.name) in self.varrange and self.varrange['',n.name] == '*':
		#	#print "B propagating non-determinism due to variable (%s,%s)" % (self._currentfunct,n.name)
		#	self._nondetfound = True

		return super().visit_ID(n)
	'''
	def visit_ID(self,n):
		if self._extended:
			if n.name in self.funcName and n not in self._visitedIDnodes:
				self.funcIdCnt[n.name] += 1
				self._visitedIDnodes.append(n)

		# Tracking of non-deterministic variables.
		if (self._currentfunct,n.name) in self.varrange and self.varrange[self._currentfunct,n.name] == '*':
			#print "A propagating non-determinism due to variable (%s,%s)" % (self._currentfunct,n.name)
			self._nondetfound = True
		elif ('',n.name) in self.varrange and self.varrange['',n.name] == '*':
			#print "B propagating non-determinism due to variable (%s,%s)" % (self._currentfunct,n.name)
			self._nondetfound = True

		return super().visit_ID(n)


	def visit_Return(self,n):
		if self._extended:
			# Count the function's exit points (i.e., return statements).
			if self._currentfunct not in self.funcExitPointsCnt:
				self.funcExitPointsCnt[self._currentfunct] = 1;
			else:
				self.funcExitPointsCnt[self._currentfunct] += 1

		return super().visit_Return(n)


	def visit_Struct(self,n):
		oldcurrentStruct = None

		# This method may be called more than once on the same struct, but
		# the following is done only on the first time.
		#
		if n.name not in self.structsName:
			oldcurrentStruct = self.currentStruct
			self.currentStruct = n.name
			self.structsName.append(n.name)

		oldlast = self.___up
		self.___up = n
		oldParsingStruct = self.parsingstructunionenum
		self.parsingstructunionenum = True
		s = super(self.__class__, self).visit_Struct(n)
		self.parsingstructunionenum = oldParsingStruct
		self.___up = oldlast

		if oldcurrentStruct is not None:
			self.currentStruct = oldcurrentStruct

		return s


	'''
	def visit_StructRef(self, n):
		sref = self._parenthesize_unless_simple(n.name)

		oldVisitingField = self.visitingField
		self.visitingField = True
		field = self.visit(n.field)
		self.visitingField = oldVisitingField

		return sref + n.type + field
	'''


	'''
	def visit_UnaryOp(self,n):
		operand = self._parenthesize_unless_simple(n.expr)
		oper = operand[:operand.find('[')] if '[' in operand else operand # could be an array: remove indexes

		if n.op == 'p++': return '%s++' % operand
		elif n.op == 'p--': return '%s--' % operand
		elif n.op == 'sizeof': return 'sizeof(%s)' % self.visit(n.expr)
		elif n.op == '*':
			#print "DEREFERENCING %s (line:%s)" % (operand, self.nodecoords[n]);
			if oper in self.varNames[self._currentfunct]:
				self.varDeReferenced[self._currentfunct,oper].append(0)
			elif oper in self.varNames['']:
				self.varDeReferenced['',oper].append(0)

			return '%s%s' % (n.op, operand)
		elif n.op == '&':
			#print "REFERENCING %s / %s (line:%s)" % (operand, oper, self.nodecoords[n]);
			if oper in self.varNames[self._currentfunct]:  # local variable
				self.varReferenced[self._currentfunct,oper].append(0)
			elif oper in self.varNames['']:               # global variable
				self.varReferenced['',oper].append(0)

			return '%s%s' % (n.op, operand)
		else: return '%s%s' % (n.op, operand)
	'''

	# TODO revise the whole function.
	def visit_Typedef(self,n):
		s = ''
		if n.storage: s += ' '.join(n.storage) + ' '

		self.parsingTypedef = True
		typestring = self._generate_type(n.type)  # TODO: shouldn't call super here?
		self.parsingTypedef = False

		#print ("-=-=-=->   typedef <%s> <%s>" % (n.name,typestring))
		#self.typedefsdefs.append(n.name)
		#self.typedefsdefExpansion[n.name] = typestring

		name = '?'
		if n.storage: name = ' '.join(n.storage)
		#print ("= - > new typedef             [%s,%s,%s] " % (self.blockid,n.name,name))
		self.typedefs[self.blockid,n.name] = n

		if isinstance(n.type.type,pycparser.c_ast.Struct):
			if n.type.type.decls:
				#print ("= - > new structure declared             [%s,%s,%s] " % (self.blockid,n.type.type.name,n.type.type.decls))
				#print ("= - >                                    [%s] " % (self.visit(n.type.type)))
				self.structs[self.blockid,n.type.type.name] = n.type.type
		elif isinstance(n.type.type,pycparser.c_ast.Union):
			if n.type.type.decls:
				#print ("= - > new union declared             [%s,%s,%s] " % (self.blockid,n.type.type.name,n.type.type.decls))
				#print ("= - >                                    [%s] " % (self.visit(n.type.type)))
				self.unions[self.blockid,n.type.type.name] = n.type.type

		s += typestring
		return s


	def visit_Union(self,n):
		#oldlast = self.___up
		#self.___up = n

		oldParsingStruct = self.parsingstructunionenum
		self.parsingstructunionenum = True
		s = super().visit_Union(n)
		self.parsingstructunionenum = oldParsingStruct

		#self.___up = oldlast


		return s


	def visit_Assignment(self, n):
		lval_str = self.visit(n.lvalue)

		# Tracks non-nondeterminism, only for scalar variables at the moment TODO
		oldnondetfound = self._nondetfound   # probably useless?!
		self._nondetfound = False

		rval_str = self._parenthesize_if(n.rvalue, lambda n: isinstance(n, pycparser.c_ast.Assignment))

		if self._nondetfound and type(n.lvalue) == pycparser.c_ast.ID:
			# Resolve variable scope
			variablecontext = ''

			#if self._currentfunct != '':
			if lval_str in self.varNames[self._currentfunct]:
				#print "variable %s is local to function %s" % (lval_str,self._currentfunct)
				variablecontext = self._currentfunct
			#else: print "variable %s is global" % (lval_str)

			self.varrange[variablecontext,lval_str] = '*'

		self._nondetfound = oldnondetfound

		return '%s %s %s' % (lval_str, n.op, rval_str)


    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
	# # # # # # # # # # # # #     External macros     # # # # # # # # # # # # #
    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

	''' Scope resolution.
	    Returns the identifier of the block where a symbol is defined.
	'''
	def blockdefid(self,block,symbol):
		# If the symbol is not defined in the same block where it occurs,
		# search the parent block.
		i = 0
		nextblock = block

		while (nextblock,symbol) not in self.symbols and nextblock != '0':
			nextblock = nextblock[:nextblock.rfind('.')]
			i += 1

		if (nextblock,symbol) in self.symbols: return nextblock
		elif self._debug: print("symbol table: '%s,%s' undefined" % (block,symbol))

		return None


	''' Checks whether a given symbol visible in a given block is defined globally.
	'''
	def isglobalsymbol(self,block,symbol):
		block = self.blockdefid(block,symbol)
		return (block == '0')


	''' Return the declaration node for a given symbol visible in the given block,
	    or None if no such declaration exists.
	'''
	def decl(self,blockid,name):
		resolve = self.blockdefid(blockid,name)
		return self.symbols[resolve,name] if resolve is not None else None


	''' Checks whether a given symbol, visible in a given block, is a function.
	'''
	def isfunction(self,block,symbol):
		block = self.blockdefid(block,symbol)
		return (block=='0' and ('0',symbol) in self.funcs)


	''' Checks whether a given symbol, visible in a given block, is a variable.
	'''
	def isvariable(self,block,symbol):
		block = self.blockdefid(block,symbol)
		return (block,symbol) in self.vars


	''' Checks whether a given symbol visible in a given block is a global variable.
	'''
	def isglobalvariable(self,block,symbol):
		block = self.blockdefid(block,symbol)
		return (block=='0' and (block,symbol) in self.vars)


	''' Checks whether a given symbol visible in a given block is a local variable.
	'''
	def islocalvariable(self,block,symbol):
		block = self.blockdefid(block,symbol)
		return (block!='0' and (block,symbol) in self.vars)


	''' Checks whether the given symbol visible from the given block is a pointer.

	    This includes arrays of pointers, etc.
	    As soon as a memory address is involved, this should return true.
	'''
	def ispointer(self,block,symbol):
		c = self.blockdefid(block,symbol)

		if c:
			n = self.symbols[c,symbol]

			while hasattr(n,'type'):
				if isinstance(n.type,pycparser.c_ast.PtrDecl): return True
				n = n.type

		return False  # not found anyway


	''' Checks whether the given symbol visible from the given block is an array.
	'''
	def isarray(self,block,symbol):
		c = self.blockdefid(block,symbol)

		if c:
			n = self.symbols[c,symbol]

			while hasattr(n,'type'):
				if isinstance(n.type,pycparser.c_ast.ArrayDecl): return True
				n = n.type

		return False  # not found anyway


	''' Checks if there is variable v visible from block b, and
	    returns its type if so.
	'''
	def buildtype(self,b,v):
		b = self.blockdefid(b,v)
		return self._generate_type(self.vars[b,v].type) if b else None


	''' Return the type of a variable v that is visible from block b.

	    Note: this does not work for functions.
	'''
	def gettype(self,b,v):
		b = self.blockdefid(b,v)
		return super().visit(self.symbols[b,v].type) if b else None


	#def countoccurrences(self,block,symbol):
	#	b = self.blockdefid(block,symbol) # find the block where the symbol is declared
	#	return self.symbolscount[b,symbol] if b else 0


	''' Return the input parameter(s) of a function (as a string).

	    Note: f(void) will return 'void' here, but f() will return ''.
	'''
	def functioninput(self,declnode): return super().visit(declnode.type.args)


	''' Return the return type of a function (as a string).

	    Note: modifiers are ignored, e.g.,
	         '__inline static unsigned int f(...)' will return  'unsigned int'.

	    Note: a function without a return type is considered to return 'int', e.g.,
	       'f(...)' will return 'int' here.
	'''
	def functionoutput(self,declnode): return super().visit(declnode.type.type)


	def functionisvoid(self,declnode): return (self.functionoutput(declnode)=='void')


	''' Extract the function identifier from a function call node.
	'''
	def _extractfname(self,n):
		# scan through parent nodes such as casts, unary operators, etc.
		# until an identifier is found.
		if type(n) == pycparser.c_ast.Cast: return self._extractfname(n.expr)
		if type(n) == pycparser.c_ast.UnaryOp: return self._extractfname(n.expr)
		if type(n) == pycparser.c_ast.ArrayRef: return self._extractfname(n.name)
		if type(n) == pycparser.c_ast.ID:
			return self.visit(n)

		print("error: unable to extract function identifier from expression '%s' (node type: '%s')" % (self.visit(n),type(n)))
		exit(1)
		return self.visit(n)












