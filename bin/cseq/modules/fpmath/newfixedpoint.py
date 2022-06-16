""" CSeq C Sequentialization Framework
    Bit-precise encoding of numerical error under fixed-point arithmetics.

Authors:
    Stella Simic, Omar Inverso

Changes:
	2021.02.02  added explicit casts (e.g., to match bitvector operands in equality check, etc.) via typeof
    2021.02.02  changed verifier-specific __CPROVER_assert into __CSEQ_assertext
    2020.12.21  Slight changes to support Python 3
    2020.12.13  fixedpoint_raw_on() / fixedpoint_raw_off() to prevent transformations
    2020.06.23  bugfix for error propagation and subtraction [IFM 2020]
    2020.06.21  storing multiplications and divisions using one extra bit to avoid signed overflow
    2020.05.09  reimplemented from scratch

To do:
  - switch to bitvector type rather than using self.bitwidth
   (requires changes to pycparser)

Assumptions:
  - no global variables
  - no side effect within array indexes (e.g. a[++i))
  - no binary operations with two constant operands
  - operands in binary operations have the same precision
  - shift only with constants, e.g., x = y >> 3;

Notes:
  - no support for unsigned arithmetics (i.e., no sign)

To do:
  - add __VERIFIER_error-bound-off() / add __VERIFIER_error-bound-on() ....

"""
import core.module
import pycparser


class newfixedpoint(core.module.Translator):
	precision = {}  # precision (i,f) for a fixed-point variable (blockid,id)
	errorvar = {}   # identifier of the error variable of each fp variable
	sign = {}       # signedness of the error variable of each fp variable (1 means signed)

	#sign = {}      # sign of fixed-point variables (0=signed, 1=unsigned)
	bitwidth = {}   # custom bitwidth for specific int variables, e.g. ['main','var'] = 4

	_tmpvarcnt = 0

	error_propagation_off = False
	error_propagation_off_forever = False

	error_bound_check_off_forever = False  # check disabled from the command line
	error_bound_check_off = False          # between error_bound_check_off() / error_bound_check_on() calls?

	error_overflow_off_forever = False
	error_overflow_off = False

	overflow_off = False
	overflow_off_forever = False  # overflow check disabled from the command line

	# Old things (from [ICCPS2017]?) no longer needed.
	_noerrorcheck = False
	_nooverflowcheck = False
	_nodeltacheck = False

	rawmode = False # True = no transformation


	def init(self):
		self.inputparam('error-i', 'error precision integer part', 'i', default='1', optional=False)
		self.inputparam('error-f', 'error precision fractional part', 'f', default='1', optional=False)
		self.inputparam('error-bound', 'max no. of bits allowed for the propagated error', 'e', default=1, optional=False)

		#self.inputparam('sign', '. . .(internal use only)', '', default=None, optional=True)
		self.inputparam('no-error', 'disable error propagation completely', '', default=False, optional=True)
		self.inputparam('no-error-bound-check', 'disable error bound check', '', default=False, optional=True)
		self.inputparam('no-error-overflow', 'disable overflow check on error variables', '', default=False, optional=True)
		self.inputparam('no-overflow', 'disable overflow check', '', default=False, optional=True)
		#self.inputparam('no-deltacheck', 'disable delta check', '', default=False, optional=True)
		#self.inputparam('eps', 'epsilon for delta assertion checking', 'e', default='0x1', optional=False)

		self.inputparam('precision', '. . .(internal use only)', '', default=None, optional=True)
		self.inputparam('errorvar', '. . .(internal use only)', '', default=None, optional=True)
		self.inputparam('tmpvarcnt', '. . .(internal use only)', 'e', default=1, optional=False)

		self.outputparam('precision')
		self.outputparam('bitwidth')
		self.outputparam('sign')
		self.outputparam('errorvar')
		self.outputparam('tmpvarcnt')
		self.outputparam('error-i')
		self.outputparam('error-f')
		self.outputparam('errorbound')

		self.error_i = self.error_f = self.error_if = self.errorbound = None


	def loadfromstring(self,string,env):
		self.precision = self.getinputparam('precision')
		self.bitwidth = self.getinputparam('bitwidth')
		self.errorvar = self.getinputparam('errorvar')
		self._tmpvarcnt = self.getinputparam('tmpvarcnt')
		self.error_i = int(self.getinputparam('error-i'))
		self.error_f = int(self.getinputparam('error-f'))
		self.errorbound = int(self.getinputparam('error-bound'))

		if self.getinputparam('no-error') is not None: self.error_propagation_off_forever = self.error_propagation_off = True
		if self.getinputparam('no-error-bound-check') is not None: self.error_bound_check_off_forever = self.error_bound_check_off = True
		if self.getinputparam('no-error-overflow') is not None: self.error_overflow_off_forever = self.error_overflow_off = True
		if self.getinputparam('no-overflow') is not None: self.overflow_off_forever = self.overflow_off = True
		#if self.getinputparam('no-deltacheck') is not None: self._nodeltacheck = True
		#self.eps = self.getinputparam('eps')

		#miniheader = "typedef int fixedpoint; typedef int  __cs_fixedpoint; "
		miniheader = ''
		super(self.__class__, self).loadfromstring(miniheader+string, env)

		self.setoutputparam('precision',self.precision)
		self.setoutputparam('bitwidth',self.bitwidth)
		self.setoutputparam('sign',self.sign)
		self.setoutputparam('errorvar',self.errorvar)
		self.setoutputparam('tmpvarcnt',self._tmpvarcnt)
		self.setoutputparam('error-i',self.error_i)
		self.setoutputparam('error-f',self.error_f)
		self.setoutputparam('errorbound',self.errorbound)

		# only add the header when error propagation is enabled
		#if not self._noerrorcheck:
		#	header = core.utils.printFile('modules/fixedpoint.c')
		#	header = header.replace('<i>', str(self.error_i))
		#	header = header.replace('<f>', str(self.error_f))
		#	header = header.replace('<e>', str(self.errorbound))
		#
		#	self.setoutputparam('header',header)


	def visit_Assignment(self, n):
		if self.rawmode: return super(self.__class__, self).visit_Assignment(n)

		ei = self.error_i
		ef = self.error_f
		eb = self.errorbound

		x = self._extractID(n.lvalue)     # identifier-only lvalue (e.g., M)
		xfull = self.visit(n.lvalue)      # full lvalue (e.g., M[3][20948])
		blockdef = self.Parser.blockdefid(self.blockid,x)

		if self._isfixedpoint(self.blockid,x):
			(p,q) = self.precision[blockdef,x]

		# No transformation.
		if not self._isfixedpoint(self.blockid,x):
			return super(self.__class__, self).visit_Assignment(n)

		if type(n.rvalue) == pycparser.c_ast.TernaryOp:    # ternary \assignments
			return super(self.__class__, self).visit_Assignment(n)

		if type(n.rvalue) == pycparser.c_ast.FuncCall:          # function calls
			self.warn("assignment to a function call return value detected, no transformation for this statement")
			return super(self.__class__, self).visit_Assignment(n)

		# Not handled.
		if n.op != '=':  #  <<=, >>=, +=, etc.
			self.error('unsupported operation (%s) on fixed-point variables' % n.op, snippet=True)

		# Assignment to constant (Rule A1).
		if n.op=='=' and type(n.rvalue)==pycparser.c_ast.Constant:
			xbar = xfull.replace(x,self._errorvar(self.blockid,x),1)

			#self.warn("assignment: x:[%s]    xfull:[[%s]]      xbar:[%s]"  % (x,xfull,xbar), lineno=True)
			out  = super(self.__class__, self).visit_Assignment(n)
			out += '; %s = 0' % xbar
			return out

		# Assignment to constant (with a minus sign)
		# (Rule A1).
		if n.op=='=' and type(n.rvalue)==pycparser.c_ast.UnaryOp and n.rvalue.op=='-' and type(n.rvalue.expr)==pycparser.c_ast.Constant:
			xbar = xfull.replace(x,self._errorvar(self.blockid,x),1)
			out  = super(self.__class__, self).visit_Assignment(n)
			out += '; %s = 0' % xbar
			return out

		# Assignment to another variable of the same precision
		# (Rule A4).
		if n.op=='=' and self._extractID(n.rvalue)!=None:
			yfull = self.visit(n.rvalue)
			y = self._extractID(n.rvalue)
			(p1,q1) = self._varprecision(self.blockid,y)

			if (p,q) == (p1,q1):
				#self.log('A4', lineno=True)
				out  = super(self.__class__, self).visit_Assignment(n)
				errx = xfull.replace(x,self._errorvar(self.blockid,x),1)
				erry = yfull.replace(y,self._errorvar(self.blockid,y),1)
				out += '; %s = %s' % (errx,erry)
				return out

		# Assignment to another variable of greater integer precision and the same fractional precision
		# (Rule IPC1).
		if n.op=='=' and self._extractID(n.rvalue)!=None: # type(n.rvalue) == pycparser.c_ast.ID:
			yfull = self.visit(n.rvalue)
			y = self._extractID(n.rvalue)
			(p1,q1) = self._varprecision(self.blockid,y)

			if q==q1 and p>p1:
				#self.log('IPC1', lineno=True)
				errx = xfull.replace(x,self._errorvar(self.blockid,x),1)
				erry = yfull.replace(y,self._errorvar(self.blockid,y),1)
				out  = super(self.__class__, self).visit_Assignment(n)

				if not self.error_propagation_off:
					out += '; %s = %s' % (errx,erry)

				return out

		# Assignment to another variable of smaller integer precision and the same fractional precision
		# (Rule IPC2).
		if n.op=='=' and self._extractID(n.rvalue)!=None: # type(n.rvalue) == pycparser.c_ast.ID:
			yfull = self.visit(n.rvalue)
			y = self._extractID(n.rvalue)
			(p1,q1) = self._varprecision(self.blockid,y)

			if q==q1 and p<p1:
				errx = xfull.replace(x,self._errorvar(self.blockid,x),1)
				erry = yfull.replace(y,self._errorvar(self.blockid,y),1)
				out  = super(self.__class__, self).visit_Assignment(n)

				if not self.overflow_off:
					out += '; __CSEQ_assertext((typeof(%s))%s == %s,"overflow (case 1)") ' % (yfull,xfull,yfull)

				if not self.error_propagation_off:
					out += '; %s = %s' % (errx,erry)

				return out

		# Assignment to another variable with the same integer precision and greater fractional precision
		# (Rule FPC1).
		if n.op=='=' and self._extractID(n.rvalue)!=None: # type(n.rvalue) == pycparser.c_ast.ID:
			yfull = self.visit(n.rvalue)
			y = self._extractID(n.rvalue)
			(p1,q1) = self._varprecision(self.blockid,y)

			if p==p1 and q>q1:
				errx = xfull.replace(x,self._errorvar(self.blockid,x),1)
				erry = yfull.replace(y,self._errorvar(self.blockid,y),1)
				out  = super(self.__class__, self).visit_Assignment(n)

				if not self.error_propagation_off:
					out += ' << %s; %s = %s' % (q-q1,errx,erry)

				return out

		# Assignment to another variable with the same integer precision and smaller fractional precision, case 1
		# (Rule FPC2).
		if n.op=='=' and self._extractID(n.rvalue)!=None: # type(n.rvalue) == pycparser.c_ast.ID:
			yfull = self.visit(n.rvalue)
			y = self._extractID(n.rvalue)
			(p1,q1) = self._varprecision(self.blockid,y)

			# Use the same variable names as in the paper.
			if p==p1 and q<q1 and q1<=ef:
				xbar = xfull.replace(x,self._errorvar(self.blockid,x),1)
				ybar = yfull.replace(y,self._errorvar(self.blockid,y),1)

				out = '%s = %s >> %s' % (xfull,yfull,q1-q)

				if not self.error_propagation_off:
					y1 = self._newtmpvar(self.blockid,'y1',p,q1)
					ybb = self._newtmpvar(self.blockid,'ybb',ei,ef)
					t = self._newtmpvar(self.blockid,'t',p,q1)

					out += ';fixedpoint %s;' % y1
					out += 'fixedpoint %s;' % ybb
					out += 'fixedpoint %s;' % t
					out += '%s = %s << %s;' % (y1,xfull,q1-q)
					out += '%s = %s - %s;' % (t,yfull,y1)
					out += '%s = %s << %s;' % (ybb,t,ef-q1)
					out += '%s = %s(%s,%s)' % (xbar,'e_add',ybar,ybb)

					if not self.error_bound_check_off:
						s = self._newtmpvar(self.blockid,'s',ei,ef)
						out += ';fixedpoint %s;' % s
						out += '%s = %s >= (typeof(%s))0 ? %s : -%s;' % (s,xbar,xbar,xbar,xbar)
						out += '__CSEQ_assertext(%s >> %s == (typeof(%s))0,"error bound violation")' % (s,eb,s)

				return out

		# Assignment to another variable with the same integer precision and smaller fractional precision, case 2
		# (Rule FPC3).
		# Note: if we choose ei.ef properly, we don't need this rule
		'''
		if n.op=='=' and self._extractID(n.rvalue)!=None: # type(n.rvalue) == pycparser.c_ast.ID:
			yfull = self.visit(n.rvalue)
			y = self._extractID(n.rvalue)
			(p1,q1) = self._varprecision(self.blockid,y)

			# Use the same variable names as in the paper.
			if p==p1 and q<q1 and q1>ef:
				y1 = self._newtmpvar(self.blockid,'y1',p,q1)
				ybb = self._newtmpvar(self.blockid,'ybb',ei,ef)
				s = self._newtmpvar(self.blockid,'s',ei,ef)
				t = self._newtmpvar(self.blockid,'t',p,q1)
				t1 = self._newtmpvar(self.blockid,'t1',p,q1)

				xbar = xfull.replace(x,self._errorvar(self.blockid,x),1)
				ybar = yfull.replace(y,self._errorvar(self.blockid,y),1)

				out  = 'fixedpoint %s;' % y1
				out += 'fixedpoint %s;' % ybb
				out += 'fixedpoint %s;' % s
				out += 'fixedpoint %s;' % t
				out += 'fixedpoint %s;' % t1
				out += '%s = %s >> %s;' % (xfull,yfull,q1-q)
				out += '%s = %s << %s;' % (y1,xfull,q1-q)
				out += '%s = %s - %s;' % (t,yfull,y1)
				out += '%s = %s >> %s;' % (ybb,t,q1-ef)
				out += '%s = %s << %s;' % (t1,ybb,q1-ef)
				out += '__CSEQ_assertext(%s == %s,"error overflow (need to increase error precision)");' % (t,t1)
				out += '%s = %s(%s,%s);' % (xbar,'e_add',ybar,ybb)
				out += '%s = %s >= 0 ? %s : -%s;' % (s,xbar,xbar,xbar)
				out += '__CSEQ_assertext(%s >> %s == 0,"error bound violation")' % (s,eb)

				return out
		'''

		# Assignment to binary addition or subtraction
		# (Rule ADD/SUB).
		if n.op=='=' and type(n.rvalue)==pycparser.c_ast.BinaryOp:
			if n.rvalue.op == '+' or n.rvalue.op == '-':
				y = self._extractID(n.rvalue.left)
				yfull = self._parenthesize_if(n.rvalue.left, lambda d: not self._is_simple_node(d))
				(p1,q1) = self._varprecision(self.blockid,y)

				z = self._extractID(n.rvalue.right)
				zfull = self._parenthesize_if(n.rvalue.right, lambda d: not self._is_simple_node(d))
				(p2,q2) = self._varprecision(self.blockid,z)

				xbar = xfull.replace(x,self._errorvar(self.blockid,x),1)

				# Two variables of same precision, or a variable and a constant.
				if (p1,q1)==(p2,q2) or ((p1,q1)!=(None,None) or (p2,q2)!=(None,None)):
					if (p1,q1)==(None,None):  # left operator is a constant
						(p1,q1) = (p2,q2)
						coords = self._mapbacklineno(self.currentinputlineno)
						ybar = 0
						#self.warn('assuming precision (%s.%s) for constant' % (p2,q2), lineno=True)
					else:
						ybar = yfull.replace(y,self._errorvar(self.blockid,y),1)

					if (p2,q2)==(None,None):  # right operator is a constant
						(p2,q2) = (p1,q1)
						coords = self._mapbacklineno(self.currentinputlineno)
						zbar = 0
						#self.warn('assuming precision (%s.%s) for constant' % (p1,q1), lineno=True)
					else:
						zbar = zfull.replace(z,self._errorvar(self.blockid,z),1)

					if (p,q)!=(p1+1,q1):
						self.error('result of fixed-point addition requires a storage precision of (%s.%s)' % (p1+1,q1), lineno=True)

					out  = '%s = %s %s %s;' % (xfull,yfull,n.rvalue.op,zfull)

					if n.rvalue.op == '+':
						out += '%s = e_add(%s,%s)' % (xbar,ybar,zbar)
					else:
						out += '%s = e_sub(%s,%s)' % (xbar,ybar,zbar)

					if not self.error_propagation_off:
						if not self.error_bound_check_off:
							s = self._newtmpvar(self.blockid,'s',ei,ef)
							out += ';fixedpoint %s;' % s
							out += '%s = %s >= (typeof(%s))0 ? %s : -%s;' % (s,xbar,xbar,xbar,xbar)
							out += '__CSEQ_assertext(%s >> %s == (typeof(%s))0,"error bound violation")' % (s,eb,s)

					# TODO Error propagation (simplified if one operand is a constant).
					#if ybar!=0 and zbar!=0:
					#	if n.rvalue.op=='+': out += '%s = e_add(%s,%s);' % (xhat,ybar,zbar)
					#	else:                out += '%s = e_sub(%s,%s);' % (xbar,ybar,zbar)
					#	out += '%s = e_c(%s)' % (xbar,xhat)
					#elif ybar!=0: out += '%s = %s' % (xbar,ybar)
					#elif zbar!=0: out += '%s = %s' % (xbar,zbar)
					#else: self.error('cannot be that bad', snippet=True)

					return out

		# Assignment to binary multiplication
		# (Rule MUL).
		if n.op=='=' and type(n.rvalue)==pycparser.c_ast.BinaryOp:
			if n.rvalue.op == '*':
				y = self._extractID(n.rvalue.left)
				yfull = self._parenthesize_if(n.rvalue.left, lambda d: not self._is_simple_node(d))
				(p1,q1) = self._varprecision(self.blockid,y)

				z = self._extractID(n.rvalue.right)
				zfull = self._parenthesize_if(n.rvalue.right, lambda d: not self._is_simple_node(d))
				(p2,q2) = self._varprecision(self.blockid,z)

				xbar = xfull.replace(x,self._errorvar(self.blockid,x),1)

				# Two variables of same precision, or a variable and a constant.
				if (p1,q1)==(p2,q2) or ((p1,q1)!=(None,None) or (p2,q2)!=(None,None)):
					if (p1,q1)==(None,None):  # left operator is a constant
						(p1,q1) = (p2,q2)
						coords = self._mapbacklineno(self.currentinputlineno)
						ybar = 0
						self.warn('assuming precision (%s.%s) for constant' % (p2,q2), lineno=True)
					else:
						ybar = yfull.replace(y,self._errorvar(self.blockid,y),1)

					if (p2,q2)==(None,None):  # right operator is a constant
						(p2,q2) = (p1,q1)
						coords = self._mapbacklineno(self.currentinputlineno)
						zbar = 0
						self.warn('assuming precision (%s.%s) for constant' % (p1,q1), lineno=True)
					else:
						zbar = zfull.replace(z,self._errorvar(self.blockid,z),1)

					if (p,q)!=(p1+p2+1,q1+q2):
						self.error('result of fixed-point multiplication requires a storage precision of (%s.%s)' % (p1+p2,q1+q2), snippet=True)

					e1 = self._newtmpvar(self.blockid,'e1',ei,ef)
					e2 = self._newtmpvar(self.blockid,'e2',ei,ef)
					e3 = self._newtmpvar(self.blockid,'e3',ei,ef)
					e4 = self._newtmpvar(self.blockid,'e4',ei,ef)

					out  = '%s = %s %s %s' % (xfull,yfull,n.rvalue.op,zfull)

					if not self.error_propagation_off:
						out += ';fixedpoint %s;' % (e1)
						out += 'fixedpoint %s;' % (e2)
						out += 'fixedpoint %s;' % (e3)
						out += 'fixedpoint %s;' % (e4)

						# Error propagation (TODO simplify error propagation if one operand is a constant)
						out += '%s = e_mul(%s,%s);' % (e1,ybar,zbar)
						out += '%s = e_mul(%s,%s);' % (e2,yfull,zbar)
						out += '%s = e_mul(%s,%s);' % (e3,zfull,ybar)
						out += '%s = e_add(%s,%s);' % (e4,e1,e2)
						out += '%s = e_add(%s,%s)' % (xbar,e3,e4)

						if not self.error_bound_check_off:
							s = self._newtmpvar(self.blockid,'s',ei,ef)
							out += ';fixedpoint %s;' % s
							out += '%s = %s >= (typeof(%s))0 ? %s : -%s;' % (s,xbar,xbar,xbar,xbar)
							out += '__CSEQ_assertext(%s >> %s == (typeof(%s))0,"error bound violation")' % (s,eb,s)

					return out

		# Assignment to binary division
		# (Rule DIV).
		if n.op=='=' and type(n.rvalue)==pycparser.c_ast.BinaryOp:
			if n.rvalue.op == '/':
				y = self._extractID(n.rvalue.left)
				yfull = self._parenthesize_if(n.rvalue.left, lambda d: not self._is_simple_node(d))
				(p1,q1) = self._varprecision(self.blockid,y)

				z = self._extractID(n.rvalue.right)
				zfull = self._parenthesize_if(n.rvalue.right, lambda d: not self._is_simple_node(d))
				(p2,q2) = self._varprecision(self.blockid,z)

				xbar = xfull.replace(x,self._errorvar(self.blockid,x),1)

				# Two variables of same precision, or a variable and a constant.
				if (p1,q1)==(p2,q2) or ((p1,q1)!=(None,None) or (p2,q2)!=(None,None)):
					if (p1,q1)==(None,None):  # left operator is a constant
						(p1,q1) = (p2,q2)
						coords = self._mapbacklineno(self.currentinputlineno)
						ybar = 0
						self.warn('assuming precision (%s.%s) for constant' % (p2,q2), lineno=True)
					else:
						ybar = yfull.replace(y,self._errorvar(self.blockid,y),1)

					if (p2,q2)==(None,None):  # right operator is a constant
						(p2,q2) = (p1,q1)
						coords = self._mapbacklineno(self.currentinputlineno)
						zbar = 0
						self.warn('assuming precision (%s.%s) for constant' % (p1,q1), lineno=True)
					else:
						zbar = zfull.replace(z,self._errorvar(self.blockid,z),1)

					if (p,q)!=(p1+q2+1,p2+q1):
						self.error('result of fixed-point division requires a storage precision of (%s.%s)' % (p1+q2,p2+q1), snippet=True)

					t = self._newtmpvar(self.blockid,'t',p1,q1+p2+q2)
					t1 = self._newtmpvar(self.blockid,'t1',p2+p+1,q2+q)
					v = self._newtmpvar(self.blockid,'v',q,0)
					xtilde = self._newtmpvar(self.blockid,'xtilde',0,q)
					u = self._newtmpvar(self.blockid,'u',ei,ef)

					out  = '__CSEQ_assertext(%s!=(typeof(%s))0,"division by zero");' % (zfull,zfull)
					out += 'fixedpoint %s;' % (t)
					out += 'fixedpoint %s;' % (t1)
					out += 'fixedpoint %s;' % (v)
					out += 'fixedpoint %s;' % (xtilde)
					out += 'fixedpoint %s;' % (u)

					out += '%s = %s << %s;' % (t,yfull,p2+q2)
					out += '%s = %s %s %s' % (xfull,t,n.rvalue.op,zfull)

					if not self.error_propagation_off:
						out += ';%s = %s * %s;' % (t1,zfull,xfull)
						out += '%s = 1 - (%s == %s);' % (v,t,t1)
						out += '%s = %s;' % (xtilde,v)

						out += '%s = e_c(%s);' % (u,xtilde) #out += '%s = e_c1(%s);' % (u,xtilde)

						e1 = self._newtmpvar(self.blockid,'e1',ei,ef)
						e2 = self._newtmpvar(self.blockid,'e2',ei,ef)
						e3 = self._newtmpvar(self.blockid,'e3',ei,ef)
						e4 = self._newtmpvar(self.blockid,'e4',ei,ef)
						e5 = self._newtmpvar(self.blockid,'e5',ei,ef)
						e6 = self._newtmpvar(self.blockid,'e6',ei,ef)

						out += 'fixedpoint %s;' % (e1)
						out += 'fixedpoint %s;' % (e2)
						out += 'fixedpoint %s;' % (e3)
						out += 'fixedpoint %s;' % (e4)
						out += 'fixedpoint %s;' % (e5)
						out += 'fixedpoint %s;' % (e6)

						out += '%s = e_mul(%s,%s);' % (e1,ybar,zfull)
						out += '%s = e_mul(%s,%s);' % (e2,t,zbar)
						out += '%s = e_add(%s,%s);' % (e3,zfull,zbar)
						out += '%s = e_sub(%s,%s);' % (e4,e1,e2)
						out += '%s = e_mul(%s,%s);' % (e5,zfull,e3)
						out += '%s = e_div(%s,%s);' % (e6,e4,e5)
						out += '%s = e_add(%s,%s)' % (xbar,e6,u)

						if not self.error_bound_check_off:
							s = self._newtmpvar(self.blockid,'s',ei,ef)
							out += ';fixedpoint %s;' % s
							out += '%s = %s >= (typeof(%s))0 ? %s : -%s;' % (s,xbar,xbar,xbar,xbar)
							out += '__CSEQ_assertext(%s >> %s == (typeof(%s))0,"error bound violation")' % (s,eb,s)

						#(TODO simplify error propagation if one operand is a constant)

					return out

		# Assignment to left shift
		# (Rule .....).
		if n.op=='=' and type(n.rvalue)==pycparser.c_ast.BinaryOp:
			if n.rvalue.op == '<<':
				y = self._extractID(n.rvalue.left)
				yfull = self._parenthesize_if(n.rvalue.left, lambda d: not self._is_simple_node(d))
				(p1,q1) = self._varprecision(self.blockid,y)

				k = int(n.rvalue.right.value)  # this module assumes this to be a constant

				if p==p1+k and q==q1:
					xbar = xfull.replace(x,self._errorvar(self.blockid,x),1)
					ybar = yfull.replace(y,self._errorvar(self.blockid,y),1)

					y1 = self._newtmpvar(self.blockid,'y1',p1,q1+k)

					out  = 'fixedpoint %s;' % (y1)
					out += '%s = %s << %s;' % (y1,yfull,k)
					out += '%s = %s' % (xfull,y1)

					if not self.error_propagation_off:
						xhat = self._newtmpvar(self.blockid,'xhat',ei+k,ef-k)

						out += ';fixedpoint %s;' % (xhat)
						out += '%s = %s;' % (xhat,ybar)
						out += '%s = e_c(%s)' % (xbar,xhat) #out += '%s = e_c1(%s)' % (xbar,xhat)

					return out

		# Assignment to right shift (case 1)
		# (Rule .....).
		if n.op=='=' and type(n.rvalue)==pycparser.c_ast.BinaryOp:
			if n.rvalue.op == '>>':
				y = self._extractID(n.rvalue.left)
				yfull = self._parenthesize_if(n.rvalue.left, lambda d: not self._is_simple_node(d))
				(p1,q1) = self._varprecision(self.blockid,y)

				k = int(n.rvalue.right.value)  # this module assumes this to be a constant

				if p==p1-k and q==q1:
					if k<=p1 and k<=q1:
						xbar = xfull.replace(x,self._errorvar(self.blockid,x),1)
						ybar = yfull.replace(y,self._errorvar(self.blockid,y),1)

						y1 = self._newtmpvar(self.blockid,'y1',p1,q1-k)

						out  = 'fixedpoint %s;' % (y1)
						out += '%s = %s >> %s;' % (y1,yfull,k)
						out += '%s = %s' % (xfull,y1)

						if not self.error_propagation_off:
							out += ';%s = e_d(%s,%s,%s)' % (xbar,yfull,y1,k)

							if not self.error_bound_check_off:
								s = self._newtmpvar(self.blockid,'s',ei,ef)
								out += ';fixedpoint %s;' % s
								out += '%s = %s >= (typeof(%s))0 ? %s : -%s;' % (s,xbar,xbar,xbar,xbar)
								out += '__CSEQ_assertext(%s >> %s == (typeof(%s))0,"error bound violation")' % (s,eb,s)

						return out

		# Assignment to right shift (case 2)
		# (Rule .....).
		if n.op=='=' and type(n.rvalue)==pycparser.c_ast.BinaryOp:
			if n.rvalue.op == '>>':
				y = self._extractID(n.rvalue.left)
				yfull = self._parenthesize_if(n.rvalue.left, lambda d: not self._is_simple_node(d))
				(p1,q1) = self._varprecision(self.blockid,y)

				k = int(n.rvalue.right.value)  # this module assumes this to be a constant

				if p==0 and q==q1:
					if k>p1 and k<=q1:
						xbar = xfull.replace(x,self._errorvar(self.blockid,x),1)
						ybar = yfull.replace(y,self._errorvar(self.blockid,y),1)

						y1 = self._newtmpvar(self.blockid,'y1',p1,q1-k)
						x1 = self._newtmpvar(self.blockid,'x1',p1,q1)
						y2 = self._newtmpvar(self.blockid,'y2',p1+k,q1-k)

						out  = 'fixedpoint %s;' % (y1)
						out += 'fixedpoint %s;' % (x1)
						out += 'fixedpoint %s;' % (y2)
						out += '%s = %s >> %s;' % (y1,yfull,k)
						out += '%s = %s;' % (y2,y1)
						out += '%s = %s;' % (x1,y2)
						out += '%s = %s' % (xfull,x1)

						if not self.error_propagation_off:
							out += ';%s = e_d(%s,%s,%s)' % (xbar,yfull,y1,k)

							if not self.error_bound_check_off:
								s = self._newtmpvar(self.blockid,'s',ei,ef)
								out += ';fixedpoint %s;' % s
								out += '%s = %s >= (typeof(%s))0 ? %s : -%s;' % (s,xbar,xbar,xbar,xbar)
								out += '__CSEQ_assertext(%s >> %s == (typeof(%s))0,"error bound violation")' % (s,eb,s)

						return out

		# Assignment to right shift (case 3)
		# (Rule .....).
		if n.op=='=' and type(n.rvalue)==pycparser.c_ast.BinaryOp:
			if n.rvalue.op == '>>':
				y = self._extractID(n.rvalue.left)
				yfull = self._parenthesize_if(n.rvalue.left, lambda d: not self._is_simple_node(d))
				(p1,q1) = self._varprecision(self.blockid,y)

				k = int(n.rvalue.right.value)  # this module assumes this to be a constant

				if p==p1-k and q==q1:
					if k>q1:
						xbar = xfull.replace(x,self._errorvar(self.blockid,x),1)
						ybar = yfull.replace(y,self._errorvar(self.blockid,y),1)

						y1 = self._newtmpvar(self.blockid,'y1',p1+q1-k,0)

						out  = 'fixedpoint %s;' % (y1)
						out += '%s = %s >> %s;' % (y1,yfull,k)
						out += '%s = %s' % (xfull,y1)

						if not self.error_propagation_off:
							out += ';%s = e_d(%s,%s,%s)' % (xbar,yfull,y1,k)

							if not self.error_bound_check_off:
								s = self._newtmpvar(self.blockid,'s',ei,ef)
								out += ';fixedpoint %s;' % s
								out += '%s = %s >= (typeof(%s))0 ? %s : -%s;' % (s,xbar,xbar,xbar,xbar)
								out += '__CSEQ_assertext(%s >> %s == (typeof(%s))0,"error bound violation")' % (s,eb,s)

						return out


		# Safety check for shift
		if n.op=='=' and type(n.rvalue)==pycparser.c_ast.BinaryOp:
			if n.rvalue.op == '<<' or n.rvalue.op == '>>':
				self.error("unhandled shift operation", snippet=True)

		self.error("unsupported operation on fixed-point variables", snippet=True)
		#return super(self.__class__, self).visit_Assignment(n)

	''' NEW
	def visit_Decl(self,n,no_type=False):
		s = n.name if no_type else self._generate_decl(n)

		# Safety check for precisions.
		if s.startswith("fixedpoint ") or s.startswith("__cs_fixedpoint "):
			if (self.blockid,n.name) not in self.precision:
				self.error('unable to extract precision of fixed-point variable (%s)' % n.name, snippet=True)

		return super(self.__class__, self).visit_Decl(n,no_type)
	'''
	def visit_Decl(self,n,no_type=False):
		s = n.name if no_type else self._generate_decl(n)

		# Safety check for precisions.
		if s.startswith("fixedpoint ") or s.startswith("__cs_fixedpoint "):
			if (self.blockid,n.name) not in self.precision:
				self.error('unable to extract precision of fixed-point variable (%s)' % n.name, snippet=True)

		if s.startswith("fixedpoint ") or s.startswith("__cs_fixedpoint ") or s.startswith("ufixedpoint "):
			# Set the bitwidth of the variable as the sum of
			# the widths of the integer part and the fractional part, so
			# during the instrumentation they can be re-declared as
			#  s of appropriate size.
			(i,f) = self.precision[self.blockid,n.name]
			self.bitwidth[self.blockid,n.name] = int(i)+int(f);
			#if self.sign[self.blockid,n.name]: self.bitwidth[self.blockid,n.name] = self.bitwidth[self.blockid,n.name]+1

			# Add the error variable for the variable being declared (Rule DECL).
			if not self._noerrorcheck:
				##xbar = xfull.replace(x,self._errorvar(self.blockid,x),1)
				s2full = s.replace('ufixedpoint ','',1)
				s2full = s2full.replace('fixedpoint ','',1)

				#errorvarname = self._newtmpvar(self.blockid,s2,self.error_i,self.error_f,'err_')  #'E'+n.name
				errorvarfullname = 'err_'+s2full
				errorvarname = 'err_'+n.name
				#print("adding error variable (%s) (%s)" % (errorvarfullname,errorvarname))

				#errorvarname = core.utils.rreplace(errorvarname,'__%s_%s__' % (self.error_i,self.error_f), '',1)
				extra = '; fixedpoint %s = {0}' % errorvarfullname

				#print("---> [[%s]]" % (extra))

				self.bitwidth[self.blockid,errorvarname] = int(self.error_i)+int(self.error_f); ##TODO need +1 or not??
				self.precision[self.blockid,errorvarname] = (self.error_i,self.error_f)
				self.errorvar[self.blockid,n.name] = errorvarname
				#self.sign[self.blockid,errorname] = 1

				if not self.rawmode:
					return super(self.__class__, self).visit_Decl(n,no_type) +extra

		return super(self.__class__, self).visit_Decl(n,no_type)


	def visit_FuncCall(self,n):
		fref = self._parenthesize_unless_simple(n.name)

		if fref=='fixedpoint_raw_on':
			self.debug("fixedpoint raw mode enabled")
			self.rawmode = True

		if fref=='fixedpoint_raw_off':
			self.debug("fixedpoint raw mode disabled")
			self.rawmode = False

		# Keep track of code sections where error propagation is disabled.
		if fref=='error_propagation_off' and not self.error_propagation_off_forever:
			self.error_propagation_off = True
			self.log('error propagation disabled', lineno=True)
		elif fref=='error_propagation_off' and self.error_propagation_off_forever:
			self.warn('error propagation disabling marker ignored', lineno=True)

		if fref=='error_propagation_on' and not self.error_propagation_off_forever:
			self.error_propagation_off = True
			self.log('error propagation enabled', lineno=True)
		elif fref=='error_propagation_on' and self.error_propagation_off_forever:
			self.warn('error propagation enabling marker ignored', lineno=True)

		# Keep track of code sections where error bound check is disabled.
		if fref=='error_bound_check_off' and not self.error_bound_check_off_forever and not self.error_propagation_off_forever:
			self.error_bound_check_off = True
			self.log('error bound check free section starts here', lineno=True)
		elif fref=='error_bound_check_off' and (self.error_bound_check_off_forever or self.error_propagation_off_forever):
			self.warn('error bound check disabling marker ignored', lineno=True)

		if fref=='error_bound_check_on' and not self.error_bound_check_off_forever and not self.error_propagation_off_forever:
			self.error_bound_check_off = False
			self.log('error bound check free section stops here', lineno=True)
		elif fref=='error_bound_check_on' and (self.error_bound_check_off_forever or self.error_propagation_off_forever):
			self.warn('error bound check enabling marker ignored', lineno=True)

		# Keep track of code sections where overflow check is disabled.
		if fref=='overflow_check_off' and not self.overflow_off_forever:
			self.overflow_off = True
			self.log('overflow check disabled', lineno=True)
		elif fref=='overflow_check_off' and self.overflow_off_forever:
			self.warn('overflow check disabling marker ignored', lineno=True)

		if fref=='overflow_check_on' and not self.overflow_off_forever:
			self.overflow_on = True
			self.log('overflow check enabled', lineno=True)
		elif fref=='overflow_check_on' and self.overflow_off_forever:
			self.warn('overflow check enabling marker ignored', lineno=True)

		return super(self.__class__, self).visit_FuncCall(n)


	''' Check whether a given (scope,variablename) correspond to a fixed-point variable.
	'''
	def _isfixedpoint(self,scope,name):
		scope = self.Parser.blockdefid(scope,name)
		return (scope,name) in self.precision


	''' Extract the variable identifier from the sub-AST rooted at n.

		Returns  None  if the node corresponds to a constant expression,
		the variable identifier if the node contains a simple variable occurrence,
		the array identifier (e.g. arr) in case the node
		is an array reference (e.g. arr[x][y]).

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

		return None
		# shouldn't really get to this point
		#self.error('unable to extract variable ID from AST-subtree: unknown node type (%s).' % type(n), True)

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

		#self.error("unable to extract precision for variable %s, please double check declaration" % var, snippet=True)
		return (None,None) # might be a constant


	def _newtmpvar(self,block,id,i,f,suffix='T'):
		cnt = self._tmpvarcnt
		self._tmpvarcnt+=1

		name = '%s%s_%s__%s_%s__' % (suffix,id,self._tmpvarcnt,i,f)
		self.precision[block,name] = (i,f)
		self.bitwidth[block,name] = (i+f)
		self.sign[block,name] = 1

		return name















