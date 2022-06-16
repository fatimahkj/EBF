""" CSeq Program Analysis Framework
    ...

Authors:
    Stella Simic, Omar Inverso

Changes:
    2020.12.13  fixedpoint_raw_on() / fixedpoint_raw_off() to prevent transformations
    2020.12.09  first version

To do:
  - handle array elements (e.g., a[3])
  - handle nested branches

"""
import pycparserext.ext_c_parser, pycparser.c_ast, pycparserext.ext_c_generator
import core.module, core.parser, core.utils


class branch2(core.module.Translator):
	precision = {}  # precision (i,f) for a fixed-point variable (blockid,id)
	errorvar = {}   # identifier of the error variable of each fp variable
	sign = {}       # signedness of the error variable of each fp variable (1 means signed)

	bitwidth = {}   # custom bitwidth for specific int variables, e.g. ['main','var'] = 4
	errorvar = {}   # identifier of the error variable of each fp variable

	_tmpvarcnt = 0

	# Propagated from previous module
	W_s = {}
	W_s1 = {}
	W_s2 = {}
	T = {}
	E = {}
	I = {}
	C = {}

	replacements = {}  # replacement[from_ID] = to_ID


	def init(self):
		self.inputparam('error-i', 'error precision integer part', 'i', default='1', optional=False)
		self.inputparam('error-f', 'error precision fractional part', 'f', default='1', optional=False)
		self.inputparam('error-bound', 'max no. of bits allowed for the propagated error', 'e', default=1, optional=False)

		self.inputparam('precision', '. . .(internal use only)', '', default=None, optional=True)

		self.outputparam('bitwidth')
		self.outputparam('sign')
		self.outputparam('errorvar')
		self.outputparam('tmpvarcnt')
		self.outputparam('error-i')
		self.outputparam('error-f')
		self.outputparam('errorbound')

		self.inputparam('W_s', 'internal use only', '', default='', optional=False)
		self.inputparam('W_s1', 'internal use only', '', default='', optional=False)
		self.inputparam('W_s2', 'internal use only', '', default='', optional=False)
		self.inputparam('T', 'internal use only', '', default='', optional=False)
		self.inputparam('E', 'internal use only', '', default='', optional=False)
		self.inputparam('I', 'internal use only', '', default='', optional=False)
		self.inputparam('C', 'internal use only', '', default='', optional=False)

		self.inputparam('error-control-flow', 'propagate errors across control-flow branches', '', default=False, optional=True)

	def loadfromstring(self, string, env):
		self.controlflowerror = True if self.getinputparam('error-control-flow') is not None else False

		self.error_i = int(self.getinputparam('error-i'))
		self.error_f = int(self.getinputparam('error-f'))
		self.errorbound = int(self.getinputparam('error-bound'))
		self.precision = self.getinputparam('precision')

		self.W_s = self.getinputparam('W_s')
		self.W_s1 = self.getinputparam('W_s1')
		self.W_s2 = self.getinputparam('W_s2')
		self.T = self.getinputparam('T')
		self.E = self.getinputparam('E')
		self.I = self.getinputparam('I')
		self.C = self.getinputparam('C')

		super(self.__class__, self).loadfromstring(string, env)

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

		if n in self.replacements:
			return self.replacements[n]

		return n


	def visit_If(self, n):
		if not self.controlflowerror:
			return super(self.__class__, self).visit_If(n)

		lineno = self._mapbacklineno(self.currentinputlineno)[0]

		# No error propagation across branching
		if lineno not in self.W_s:
			return super(self.__class__, self).visit_If(n)

		# There is an if with fixed-point variabled involved,
		# need to propagate the error accordingly.
		self.log("if-then-else at line %s" % (lineno))

		self.log("     W(s): %s" % (','.join(self.W_s[lineno])))
		self.log("     W(s'): %s" % (','.join(self.W_s1[lineno])))
		self.log("     W(s\"): %s" % (','.join(self.W_s2[lineno])))
		self.log("     T(s): %s" % (','.join(self.T[lineno])))
		self.log("     E(s): %s" % (','.join(self.E[lineno])))
		self.log("     I(s): %s" % (','.join(self.I[lineno])))
		self.log("     C(s): %s" % (','.join(self.C[lineno])))

		if len(self.C[lineno]) != 1:
			self.error("only one fixed-point variable is allowed in the branching condition", snippet=True)

		X = self.C[lineno][0]   # our fixed-point branching variable (i.e., that in the if condition!)
		(xi,xf) = self._varprecision(self.blockid,X)
		(ei,ef) = (self.error_i,self.error_f)

		# Build the different chunks (condition, if block, then block)
		s1 = self._generate_stmt(n.iftrue, add_indent=True)    # then block
		s2 = self._generate_stmt(n.iffalse, add_indent=True)   # else block
		c  = self.visit(n.cond)

		# Rewrite rule, block 1
		xtilde = self._newtmpvar(self.blockid,'',ei,ef,'XT')
		x1 = self._newtmpvar(self.blockid,'',ei,ef,'B')

		s =  'fixedpoint_raw_on(); '
		s += 'fixedpoint %s; ' % (xtilde)
		s += 'fixedpoint %s; ' % (x1)
		s += '%s = %s << %s; ' % (x1,X,ef-xf)  # TODO add cast here
		s += '%s = e_add(%s,err_%s);' % (xtilde,x1,X)
		s += 'fixedpoint_raw_off(); '

		# Rewrite rule, block 2
		s += 'if (%s <= 0 && %s <= 0) ' % (X,xtilde)
		s += '%s' % (s1)
		s += 'if (%s > 0 && %s > 0) ' %(X,xtilde)
		s += '%s' % (s2)

		# Rewrite rule, block 3
		s += 'if (%s <= 0 && %s > 0) {' % (X,xtilde)

		self.new_block_begin()
		s += 'fixedpoint_raw_on();'

		vthenmap = {}       # maps to keep track of the newly introduced variables
		vthen1map = {}
		velsemap = {}
		velse1map = {}
		velsetildemap = {}
		v1map = {}
		vtildemap = {}

		for v in self.W_s1[lineno]:
			(vi,vf) = self._varprecision(self.blockid,v)

			vthen = self.replacements[v] = self._newtmpvar(self.blockid,'',vi,vf,'_vthen')
			vthenmap[v] = vthen
			vthen1 = self._newtmpvar(self.blockid,'',ei,ef,'_vthen1')
			vthen1map[v] = vthen1

			s += 'fixedpoint %s;' % vthen
			s += 'fixedpoint %s;' % vthen1

		for v in self.W_s1[lineno]:
			(vi,vf) = self._varprecision(self.blockid,v)

			s += '%s = %s;' % (vthenmap[v],v)
			s += '%s' % ('replace_this_right_after_the_loop')
			s += '%s = %s << %s;' % (vthen1map[v],vthenmap[v],ef-vf)

		stmt1 = self._generate_stmt(n.iftrue, add_indent=True)  # then block w/ alterations
		s = s.replace('replace_this_right_after_the_loop', stmt1)
		self.replacements = {}

		s += 'fixedpoint_raw_off();'

		#
		for v in self.W_s2[lineno]:
			(vi,vf) = self._varprecision(self.blockid,v)

			velse = self.replacements[v] = self._newtmpvar(self.blockid,'',vi,vf,'_velse')
			velsemap[v] = velse

			s += 'fixedpoint %s;' % velse
			s += '%s = %s;' % (velse,v)

		for v in self.W_s2[lineno]:
			(vi,vf) = self._varprecision(self.blockid,v)

			s += '%s' % ('replace_this_right_after_the_loop')

		stmt2 = self._generate_stmt(n.iffalse, add_indent=True)  # else block w/ alterations
		s = s.replace('replace_this_right_after_the_loop', stmt2)
		self.replacements = {}

		#
		s += 'fixedpoint_raw_on();'

		for v in self.W_s2[lineno]:
			(vi,vf) = self._varprecision(self.blockid,v)

			velse1 = self._newtmpvar(self.blockid,'',ei,ef,'_velse1')
			velse1map[v] = velse1
			velsetilde = self._newtmpvar(self.blockid,'',ei,ef,'_velsetilde')
			velsetildemap[v] = velsetilde

			s += 'fixedpoint %s;' % velse1
			s += 'fixedpoint %s;' % velsetilde
			s += '%s = %s << %s;' % (velse1,velsemap[v],ef-vf)
			s += '%s = e_add(%s,err_%s);' % (velsetilde,velse1,velsemap[v])

		#
		for v in self.W_s[lineno]:
			if v == X: continue

			v1 = self._newtmpvar(self.blockid,'',ei,ef,'_v1')
			v1map[v] = v1

			s += 'fixedpoint %s;' % v1
			s += '%s = %s << %s;' % (v1,v,ef-vf)

		v1map[X] = x1

		#
		for v in self.T[lineno]:
			if v == X: continue

			vtilde = self._newtmpvar(self.blockid,'',ei,ef,'_vtilde')
			vtildemap[v] = vtilde

			s += 'fixedpoint %s;' % vtilde
			s += '%s = e_add(%s,err_%s);' % (vtilde,v1map[v],v)

		vtildemap[X] = xtilde

		#
		for v in self.T[lineno]:
			s += 'err_%s = e_sub(%s,%s);' % (v,vtildemap[v],vthen1map[v])

		for v in self.I[lineno]:
			s += 'err_%s = e_sub(%s,%s);' % (v,velsetildemap[v],vthen1map[v])

		for v in self.E[lineno]:
			s += 'err_%s = e_sub(%s,%s);' % (v,velsetildemap[v],v1map[v])

		for v in self.W_s1[lineno]:
			s += '%s = %s;' % (v,vthenmap[v])

		for v in self.W_s[lineno]:
			sss = self._newtmpvar(self.blockid,'',ei,ef,'_s')

			s += 'fixedpoint %s;' % sss
			s += '%s = err_%s>=0 ? err_%s: -err_%s;' % (sss,v,v,v)
			s += 'assert((%s >> %s) == 0);' %(sss,self.errorbound)

		s += 'fixedpoint_raw_off();'
		s += '}'
		self.new_block_end()

		# Rewrite rule, block 4
		s += 'if (%s > 0 && %s <= 0) {' % (X,xtilde)

		self.new_block_begin()
		s += 'fixedpoint_raw_on();'

		vthenmap = {}       # maps to keep track of the newly introduced variables
		vthen1map = {}
		velsemap = {}
		velse1map = {}
		vthentildemap = {}
		v1map = {}
		vtildemap = {}

		for v in self.W_s2[lineno]:
			(vi,vf) = self._varprecision(self.blockid,v)

			velse = self.replacements[v] = self._newtmpvar(self.blockid,'',vi,vf,'_velse')
			velsemap[v] = velse
			velse1 = self._newtmpvar(self.blockid,'',ei,ef,'_velse1')
			velse1map[v] = velse1

			s += 'fixedpoint %s;' % velse
			s += 'fixedpoint %s;' % velse1

		for v in self.W_s2[lineno]:
			(vi,vf) = self._varprecision(self.blockid,v)

			s += '%s = %s;' % (velsemap[v],v)
			s += '%s' % ('replace_this_right_after_the_loop')
			s += '%s = %s << %s;' % (velse1map[v],velsemap[v],ef-vf)

		stmt2 = self._generate_stmt(n.iffalse, add_indent=True)  # then block w/ alterations
		s = s.replace('replace_this_right_after_the_loop', stmt2)
		self.replacements = {}

		s += 'fixedpoint_raw_off();'

		#
		for v in self.W_s1[lineno]:
			(vi,vf) = self._varprecision(self.blockid,v)

			vthen = self.replacements[v] = self._newtmpvar(self.blockid,'',vi,vf,'_vthen')
			vthenmap[v] = vthen

			s += 'fixedpoint %s;' % vthen
			s += '%s = %s;' % (vthen,v)

		for v in self.W_s1[lineno]:
			(vi,vf) = self._varprecision(self.blockid,v)

			s += '%s' % ('replace_this_right_after_the_loop')

		stmt1 = self._generate_stmt(n.iftrue, add_indent=True)  # else block w/ alterations
		s = s.replace('replace_this_right_after_the_loop', stmt1)
		self.replacements = {}

		#
		s += 'fixedpoint_raw_on();'

		for v in self.W_s1[lineno]:
			(vi,vf) = self._varprecision(self.blockid,v)

			vthen1 = self._newtmpvar(self.blockid,'',ei,ef,'_vthen1')
			vthen1map[v] = vthen1
			vthentilde = self._newtmpvar(self.blockid,'',ei,ef,'_vthentilde')
			vthentildemap[v] = vthentilde

			s += 'fixedpoint %s;' % vthen1
			s += 'fixedpoint %s;' % vthentilde
			s += '%s = %s << %s;' % (vthen1,vthenmap[v],ef-vf)
			s += '%s = e_add(%s,err_%s);' % (vthentilde,vthen1,vthenmap[v])

		#
		for v in self.W_s[lineno]:
			if v == X: continue

			v1 = self._newtmpvar(self.blockid,'',ei,ef,'_v1')
			v1map[v] = v1

			s += 'fixedpoint %s;' % v1
			s += '%s = %s << %s;' % (v1,v,ef-vf)

		v1map[X] = x1

		#
		for v in self.E[lineno]:
			if v == X: continue

			vtilde = self._newtmpvar(self.blockid,'',ei,ef,'_vtilde')
			vtildemap[v] = vtilde

			s += 'fixedpoint %s;' % vtilde
			s += '%s = e_add(%s,err_%s);' % (vtilde,v1map[v],v)

		vtildemap[X] = xtilde

		#
		for v in self.E[lineno]:
			s += 'err_%s = e_sub(%s,%s);' % (v,vtildemap[v],velse1map[v])

		for v in self.I[lineno]:
			s += 'err_%s = e_sub(%s,%s);' % (v,vthentildemap[v],velse1map[v])

		for v in self.T[lineno]:
			s += 'err_%s = e_sub(%s,%s);' % (v,vthentildemap[v],v1map[v])

		for v in self.W_s2[lineno]:
			s += '%s = %s;' % (v,velsemap[v])

		for v in self.W_s[lineno]:
			sss = self._newtmpvar(self.blockid,'',ei,ef,'_s')

			s += 'fixedpoint %s;' % sss
			s += '%s = err_%s>=0 ? err_%s: -err_%s;' % (sss,v,v,v)
			s += 'assert((%s >> %s) == 0);' %(sss,self.errorbound)

		s += 'fixedpoint_raw_off();'
		s += '}'
		self.new_block_end()

		return s



	''' Check whether a given (scope,variablename) correspond to a fixed-point variable.
	'''
	def _isfixedpoint(self,scope,name):
		scope = self.Parser.blockdefid(scope,name)
		return (scope,name) in self.precision


	''' Extract the variable identifier from the sub-AST rooted at n.

		Returns  None  if the node corresponds to a constant expression,
		the variable identifier if the node contains a simple variable occurrence,
		the array identifier in case the node is an array reference (e.g. arr[x][y]).

	    The identifier so obtained can then be used to look up the symbol table.
	'''
	def _extractID(self,n):
		if type(n) == pycparser.c_ast.Constant: return n.value
		if type(n) == pycparser.c_ast.ID: return self.visit(n)
		if type(n) == pycparser.c_ast.UnaryOp: return self._extractID(n.expr)

		if type(n) == pycparser.c_ast.ArrayRef:
			next = n

			while type(next.name) != pycparser.c_ast.ID:
				next = next.name

			return self.visit(next.name)

		# shouldn't really get to this point
		self.error('unable to extract variable ID from AST-subtree: unknown node type (%s).' % type(n), True)

	def _isarray(self,block,var):
		scope = self.Parser.blockdefid(block,var)

		if scope is not None:
			if type(self.Parser.var[scope,var].type) == pycparser.c_ast.ArrayDecl: return True

		return False


	# Return the identifier of the error variable for the given variable.
	def _errorvar(self,block,var):
		block = self.Parser.blockdefid(block,var)

		if block is not None:
			if (block,var) in self.errorvar: return self.errorvar[block,var]

		return None


	def _varprecision(self,block,var):
		if (self.Parser.blockdefid(block,var),var) in self.precision:
			return self.precision[self.Parser.blockdefid(block,var),var]

		#self.warn("unable to extract precision for variable %s, please double check declaration" % var)
		return (None,None) # might be a constant


	def _newtmpvar(self,block,id,i,f,suffix='T'):
		cnt = self._tmpvarcnt
		self._tmpvarcnt+=1

		name = '%s%s_%s__%s_%s__' % (suffix,id,self._tmpvarcnt,i,f)
		self.precision[block,name] = (i,f)
		self.bitwidth[block,name] = (i+f)
		self.sign[block,name] = 1

		return name







