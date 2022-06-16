""" CSeq Program Analysis Framework
    workarounds module

This module performs all workarounds to known backend bugs/issues, or
useful transformations to simplify the code and meet the assumptions of
the modules to be invoked later
(later modules can thus avoid to handle the full C syntax)

Transformations inherited from old merger (some code normalisation to avoid corner-cases):
	- add enclosing brackets to single-statement loop bodies

	- split declaration of variables of the same kind:
		int x,y; --> int x; int y;

	- split declaration of local variables + init value to two separate statements:
		int x = value; --> int x; x = value;

	- remove  if(!1) { .. }  and  if(0) { .. }

	- assign a name to anonymous structures:
		struct { int f1; char f2; ... }    -->   struct __anon_0 { int f1; char f2; ... }

	- remove (void *) 0 --> 0

Transformation 4:
	structure->field            -->     (*structure).field
	structure->field->field     -->   (*(*structure).field).field    TODO: test/check this one properly

Transformation 5:
	__cs_thread_local_variablename --> variablename[pthread_self()]

Transformation 8:
	fix PTHREAD_MUTEX_INITIALIZER     initialization
		PTHREAD_COND_INITIALIZER
		PTHREAD_RWLOCK_INITIALIZER

Transformation 9:
	make sure __VERIFIER_atomic_begin/__VERIFIER_atomic_end are well-nested,
	or transform the latter into a dummy function call.

Author:
    Omar Inverso

Changes:
    2021.02.12  workarounds no. 3, 6, 7 removed
    2021.02.12  special treatment for empty structures no longer required
    2021.02.12  different handling of structure declarations in the case of struct S {...} a, b;
    2020.11.11  handling struct S { ... } a, b; [SV-COMP 2021]
    2020.03.24 (CSeq 2.0)
    2019.11.27 [SV-COMP 2020]
    2019.11.17 (CSeq 1.5-parallel pycparserext) [PPoPP 2020]
    2019.11.17  removing empty do..while statements
    2019.11.17  removing one-step do..while statements
    2019.11.13  support for pycparser 2.19 (backward compatibility preserved)
    2018.11.22 [SV-COMP 2019]
    2018.11.22  no longer splitting declaration from initialisation of new variables (see commented snippet in visit_Decl)
    2018.10.29  transforming decllist (only size 1 for now) in the init statement of for loops
    2018.10.28  fixed indentation, at last
    2018.10.20  merged with [SV-COMP 2016] version
    2018.10.20  Make any call __VERIFIER_atomic_end ineffective when not well-nested
               (i.e., no __VERIFIER_atomic_begin occurs before in the same block).
    2016.11.18  bugfixes for [SV-COMP 2017], add workarounds 7 and 8
    2015.01.13  bugfixes
    2014.12.24 (CSeq 1.0beta)
    2014.12.09  further code refactory to match the new organisation of the CSeq framework
    2014.10.26 (CSeq Lazy-0.6,newseq-0.6a,newseq-0.6c) [SV-COMP 2015]
    2014.10.26  structure dereference workaround (transformation 4)
    2014.10.09  moved in this module all the transformations from merger.py
    2014.06.05 (CSeq Lazy-0.4)
    2014.03.13 (CSeq Lazy-0.3)
    2014.02.25  switched to module.Module base class for modules (CSeq Lazy-0.2)

To do:
  - urgent: some transformations are no longer required (e.g., workarounds no.4 maybe. check TODO)
  - urgent: some transformations should be moved to the relevant module
  - double-check __VERIFIER_atomic_begin/__VERIFIER_atomic_end fix

"""
import inspect, os, sys, getopt, time
import pycparserext.ext_c_parser, pycparser.c_ast, pycparserext.ext_c_generator
import core.module, core.parser, core.utils


class workarounds(core.module.Translator):
	_visitingtypedef = False
	_threadLocals = []
	_parsingFunction = ''
	_hasAtomicBegin = []

	_currentAnonStructsCount = 0   # no. of anonymous structures
	structs = {}  # structs, indexed by blockid where they occur

	def init(self):
		super().extend()
		self.inputparam('sv-comp', 'SV-COMP2021 mode', '', default=False, optional=True)


	def loadfromstring(self,string,env):
		self.svcomp = True if self.getinputparam('sv-comp') is not None else False
		super().loadfromstring(string,env)


	def visit_Compound(self, n):
		s = self._make_indent() + '{\n'
		self.indent_level += 1

		if n.block_items:
			self._hasAtomicBegin.append(False)

			for stmt in n.block_items:
				k = self._generate_stmt(stmt)

				if '__VERIFIER_atomic_begin()' in k:
					self._hasAtomicBegin[-1] = True

				if not self._hasAtomicBegin[-1] and '__VERIFIER_atomic_end()' in k:
					self.warn("atomic sections not well-nested, disabling last atomic section end marker")
					k = k.replace('__VERIFIER_atomic_end()', '__CSEQ_noop()', 1)

				s += k

			self._hasAtomicBegin.pop()

		self.indent_level -= 1
		s += self._make_indent() + '}\n'

		return s


	def visit_ID(self, n):
		if n.name in self._threadLocals: return '__cs_thread_local_'+n.name+'[__cs_thread_index]'
		else: return n.name


	def visit_FuncDef(self,n):
		out = ''

		###print("==== Parser.funcIdCnt start ============")
		###print(self.Parser.funcIdCnt)
		###print("=====Parser.funcIdCnt stop ===========")

		cntoveralloccurrences = self.Parser.funcIdCnt[n.decl.name]
		cntexplicitcalls = self.Parser.funcCallCnt[n.decl.name]
		cntthreads = self.Parser.threadCallCnt[n.decl.name]

		#print "---> blubluuu: %s   callcnlt:%s   idcnt:%s   thrcnt:%s" % (n.decl.name,cntexplicitcalls,cntoveralloccurrences,cntthreads)

		# Remove functions that are never invoked (not even via call to pointer to function)
		needsubparsing = False
		if cntoveralloccurrences==cntexplicitcalls==cntthreads==0 and n.decl.name != 'main':
			self.debug("removing unused definition of function %s" % n.decl.name)
			needsubparsing = True
			out = ''

		self._parsingFunction = n.decl.name

		decl = self.visit(n.decl)
		body = self.visit(n.body)

		# In SVCOMP2021 reach_error() replaces __VERIFIER_assert(0)
		if self.svcomp and n.decl.name == 'reach_error': body = '{ ; }'

		if n.param_decls:
			knrdecls = ';\n'.join(self.visit(p) for p in n.param_decls)
			self._parsingFunction = ''
			out = decl + '\n' + knrdecls + ';\n' + body + '\n'
		else:
			self._parsingFunction = ''
			out = decl + '\n' + body + '\n'

		oldout = out

		'''
		if needsubparsing:
			# would need to parse everything from the beginning, and then
			# not just this function!
			print("SUBPARSING:\n%s\n" % (out))
			import core.parser
			subparser = core.parser.Parser()
			subparser.loadfromstring(out)
		'''

		return out


	def visit_FuncCall(self, n):
		fref = self._parenthesize_unless_simple(n.name)

		#if self.svcomp and fref == 'reach_error': return 'assert(0)'
		#if self.svcomp and fref == 'assume_abort_if_not': return '__VERIFIER_assume(%s)' % super().visit(n.args)
		if fref == 'reach_error': return 'assert(0)'
		if fref == 'assume_abort_if_not': return '__VERIFIER_assume(%s)' % super().visit(n.args)

		return super().visit_FuncCall(n)


	def visit_Decl(self, n, no_type=False):
		# no_type is used when a Decl is part of a DeclList, where the type is
		# explicitly only for the first delaration in a list.
		#
		s = n.name if no_type else self._generate_decl(n)

		if n.bitsize: s += ' : ' + self.visit(n.bitsize)

		# when an init expression is used,
		# remove it from the declaration statement and insert a separate
		# statement for the assignment.
		#
		assignmentStmt = ''

		if n.init:
			if isinstance(n.init, pycparser.c_ast.InitList):
				assignmentStmt = ' = {' + self.visit(n.init) + '}'

			elif isinstance(n.init, pycparser.c_ast.ExprList):
				assignmentStmt = ' = (' + self.visit(n.init) + ')'
			else:
				assignmentStmt = ' = ' + self.visit(n.init)

		# Split the declaration statement from initialization statement.
		#
		# Remember thread-local variables
		if (n.name is not None) and (n.name.startswith('__cs_thread_local_')):
			self._threadLocals.append(n.name.replace('__cs_thread_local_', ''))

		return s + assignmentStmt


	def visit_If(self, n):
		cond = ''

		s = 'if ('
		cond = self.visit(n.cond)
		if n.cond: s += cond
		s += ')\n'

		# Eliminate dead code
		if cond == '0' or cond == '!1':
			return ''

		# always add brackets when missing
		if type(n.iftrue) != pycparser.c_ast.Compound:
			self.indent_level+=1
			t = self._generate_stmt(n.iftrue, add_indent=True)
			self.indent_level-=1
			t = self._make_indent() + '{\n' + t + self._make_indent() + '}\n'
		else:
			t = self._generate_stmt(n.iftrue, add_indent=True)

		s += t

		if n.iffalse:
			s += self._make_indent() + 'else\n'

			# always add brackets when missing
			if type(n.iffalse) != pycparser.c_ast.Compound:
				self.indent_level+=1
				e = self._generate_stmt(n.iffalse, add_indent=True)
				self.indent_level-=1
				e = self._make_indent() + '{\n' + e + self._make_indent() + '}\n'
			else:
				e = self._generate_stmt(n.iffalse, add_indent=True)

			s += e

		return s


	def visit_For(self, n):
		endbracket = ''   # no end bracket unless n.init is a decllist

		s = 'for ('

		# Transforms
		#    for(int k=0, k<=....) body
		#
		# into:
		#    {int k; for(k=0, k<=....) body }
		#
		# notice newly added enclosing brackets to limit the scope of variable k.
		#
		if n.init:
			if type(n.init) == pycparser.c_ast.DeclList:
				caz = self._generate_decl(n.init.decls[0])
				s = '{ ' + caz + '; ' + s
				s += n.init.decls[0].name +' = '+ self.visit(n.init.decls[0].init)
				endbracket = '}'  # remember we need to close that extra bracket

				if len(n.init.decls) > 1:
					self.error("multiple declarations not supported here",snippet=True)   # TODO generalise to multiple decl in decllist
			else:
				s += self.visit(n.init)

		s += ';'

		if n.cond: s += ' ' + self.visit(n.cond)

		s += ';'

		if n.next: s += ' ' + self.visit(n.next)

		s += ')\n'

		# always add brackets when missing
		if type(n.stmt) != pycparser.c_ast.Compound:
			self.indent_level+=1
			t = self._generate_stmt(n.stmt, add_indent=True)
			self.indent_level-=1
			t = self._make_indent() + '{\n' + t + self._make_indent() + '}\n'
		else:
			t = self._generate_stmt(n.stmt, add_indent=True)

		return s+t+ self._make_indent()+endbracket


	def visit_Struct(self,n):
		# Assign a name to anonymous structs
		if n.name is None:
			n.name = 'anonstruct_' + str(self._currentAnonStructsCount)
			self._currentAnonStructsCount += 1

		out = super().visit_Struct(n)

		# Avoid wrongly separating delarations,
		# such as in struct S { .... } A, B
		if self.blockid not in self.structs:
			self.structs[self.blockid] = []

		# Structure declared for the first time.
		if n.name not in self.structs[self.blockid] and not self._visitingtypedef:
			self.structs[self.blockid].append(n.name)

		# Structure cannot be redeclated (e.g., struct S { .... } A; struct S { .... } B;
		elif n.name in self.structs[self.blockid]:
			out = 'struct %s ' % n.name

		return out


	def visit_Union(self, n):
		if n.name is None:
			n.name = 'anonstruct_' + str(self._currentAnonStructsCount)
			self._currentAnonStructsCount += 1

		return super().visit_Struct(n)


	def visit_StructRef(self,n):
		sref = self._parenthesize_unless_simple(n.name)
		ret = ''

		# workaround no. 4
		if n.type == '->': ret = ('(*' + sref + ').' + self.visit(n.field))
		else: ret = sref + n.type + self.visit(n.field)

		return ret


	def visit_While(self, n):
		s = 'while ('

		if n.cond: s += self.visit(n.cond)

		s += ')\n'

		if type(n.stmt) != pycparser.c_ast.Compound:
			self.indent_level+=1
			t = self._generate_stmt(n.stmt, add_indent=True)
			self.indent_level-=1
			t = self._make_indent() + '{\n' + t + self._make_indent() + '}\n'
		else:
			t = self._generate_stmt(n.stmt, add_indent=True)

		return s + t


	def visit_DoWhile(self, n):
		cond = ''
		body = ''

		if type(n.stmt) != pycparser.c_ast.Compound:
			self.indent_level+=1
			body = self._generate_stmt(n.stmt, add_indent=True)
			self.indent_level-=1
			body = self._make_indent() + '{\n' + body + self._make_indent() + '}\n'
		else:
			body = self._generate_stmt(n.stmt, add_indent=True)

		if n.cond:
			cond = self.visit(n.cond)

		if self.visit(n.cond)=='0' and type(n.stmt) == pycparser.c_ast.Compound and n.stmt.block_items is None:
			self.debug("empty do..while")
			return ''

		elif self.visit(n.cond)=='0' and type(n.stmt) == pycparser.c_ast.Compound and n.stmt.block_items is not None:
			self.debug("one-step do..while")
			return body

		return 'do\n' + body + self._make_indent() + 'while (' + cond + ');'


	def visit_Typedef(self,n):
		self._visitingtypedef = True
		r = super().visit_Typedef(n)
		self._visitingtypedef = False
		return r


