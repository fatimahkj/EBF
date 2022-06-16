""" Crab encoding for bitvector programs.

Author:
    The Anh Pham, Omar Inverso

Changes:
    2020.05.08  prototype start

To do:
  - so many things

Notes:
  - no global variables in the input program
  - no function definition except for main() (use inliner.py if necessary)
  - no loops (for now) (use unroller.py if necessary)
  - each variable has a unique identifier (hence, no variable shadowing)
  - no control-flow statement except if..then..else (no goto)

"""

import core.module
import pycparserext.ext_c_parser, pycparser.c_ast, pycparser.c_generator, pycparserext.ext_c_generator


class crab(core.module.Translator, pycparser.c_generator.CGenerator):
    if_list = []
    block_declareration = ''
    variable_declareration =''
    if_blocks = []
    last_ifelse_blocks = []
    last_state_block = 'entry'
    exit_parents = 'entry >> exit';
    arrays = []
    enc = ''  # our Crab encoding as a string
    index = 0
    header = '#include "program_options.hpp"\n'
    header += '#include "common.hpp"\n'
    header += '\n'
    header += 'using namespace std;\n'
    header += 'using namespace crab::analyzer;\n'
    header += 'using namespace crab::cfg;\n'
    header += 'using namespace crab::cfg_impl;\n'
    header += 'using namespace crab::domain_impl;\n'
    header += '\n'
    header += 'z_cfg_t* prog1(variable_factory_t& vfac) {\n'

    footer = 'return cfg; \n }\n'
    footer += '\n'
    footer += 'int main(int argc, char** argv) {\n'
    footer += 'bool stats_enabled = false;\n'
    footer += '\n'
    footer += 'variable_factory_t vfac;\n'
    footer += 'z_cfg_t* cfg = prog1(vfac);\n'
    footer += 'crab::outs() << *cfg << "------------------------------------";\n'
    footer += '\n'
    footer += 'run<z_boxes_domain_t>(cfg, cfg->entry(), false, 5, 2, 20, stats_enabled);\n'
    footer += 'run<z_aa_bool_int_t>(cfg, cfg->entry(), false, 1, 2, 20, stats_enabled);\n'
    footer += '\n'
    footer += 'return 0;\n'
    footer += '}\n'

    def loadfromstring (self, string, env):
        super(self.__class__, self).loadfromstring(string, env)
        self.output = self.header + self.block_declareration +'\n'  + self.exit_parents + self.variable_declareration + self.enc + self.footer

    def visit_Compound (self, n):

        if (self.blockid == '0'):
            self.block_declareration += 'z_cfg_t* cfg = new z_cfg_t("entry", "exit", ARR);\n'
            self.block_declareration += 'z_basic_block_t& entry = cfg->insert("entry");\n'
            self.block_declareration += 'z_basic_block_t& exit = cfg->insert("exit");\n'

        x = super(self.__class__, self).visit_Compound(n)

        return x

    def set_bounds (self, variable, bitwidth):
        bounds =''
        self.variable_declareration += '\nentry.assume(%s >=0);\n' % (variable)
        bound = pow(2, bitwidth)
        if (bitwidth <= 62):
            self.variable_declareration += 'entry.assume(%s < %s);\n' % (variable, bound)
        else:
            self.variable_declareration += 'z_var bound_for_%s(vfac["bound_for_%s"], crab::INT_TYPE, 32);\n' % (variable, variable)
            nbloop = bitwidth - 62;
            maxint = pow(2,62)
            self.variable_declareration += 'entry.assign(bound_for_%s,%s);\n'%(variable,maxint)
            self.variable_declareration += 'for (int i =0; i <= %s; i++) entry.mul(bound_for_%s,bound_for_%s,2);\n' % (
                nbloop, variable, variable)
            self.variable_declareration += 'entry.assume(%s < bound_for_%s);\n\n' % (variable, variable)
        return bounds

    def visit_Decl (self, n):

        lookup = self.Parser.blockdefid(self.blockid, n.name)
        if lookup is None and n.name != 'main':  # function
            self.error("functions are not allowed", snippet=True)
        elif lookup is None and n.name == 'main':
            pass
        elif lookup is '0':  # global variable
            self.error("global variables not allowed", snippet=True)
        else:
            # print('block id =', self.blockid)
            # At this point we are dealing with a variable declaration.
            # 1. if the variable is a bitvector array, we must make bounds for it
            if isinstance(n.type, pycparser.c_ast.ArrayDecl):
                self.arrays.append(n.name);

                self.variable_declareration += 'z_var %s(vfac["%s"], crab::ARR_INT_TYPE, 32);\n' % (n.name, n.name)
                self.variable_declareration += 'z_var tmp_%s(vfac["tmp_%s"], crab::INT_TYPE, 32);\n' % (n.name, n.name)
                if 'bitvector' in n.type.type.type.names[0]:
                    self.variable_declareration += 'z_var bound_for_%s(vfac["bound_for_%s"], crab::INT_TYPE, 32);\n' % (
                        n.name, n.name)
                    var = 'bound_for_%s' % n.name
                    self.set_bounds(var, int(n.type.type.type.bit_size))
                    self.variable_declareration += 'entry.array_init(%s,0,%s,%s,1);\n\n' % (n.name, n.type.dim.value, var)
                # print(n.type, n.type.dim.value, n.name, n.type.type.type.names)
            else:  # if it is not a array, create a z_variable
                self.variable_declareration += 'z_var %s(vfac["%s"], crab::INT_TYPE, 32); \n' % (n.name, n.name)
                if 'bitvector' in n.type.type.names[0]:
                    self.set_bounds(n.name, int(n.type.type.bit_size))
        return ''
        # return super(self.__class__, self).visit_Decl(n)

    def encode_basicAssignment (self, x, y, z, op):
        if (op == '+'):
            return 'block_%s_%s_%s.add(%s,%s,%s);\n' % (self.if_nb, self.if_level, self.else_level, x, y, z)
        elif (op == '-'):
            return 'block_%s_%s_%s.sub(%s,%s,%s);\n' % (self.if_nb, self.if_level, self.else_level, x, y, z)
        elif (op == '*'):
            return 'block_%s_%s_%s.mul(%s,%s,%s);\n' % (self.if_nb, self.if_level, self.else_level, x, y, z)
        elif (op == '/'):
            return 'block_%s_%s_%s.div(%s,%s,%s);\n' % (self.if_nb, self.if_level, self.else_level, x, y, z)
        elif (op == '<<'):
            return 'block_%s_%s_%s.shl(%s,%s,%s);\n' % (self.if_nb, self.if_level, self.else_level, x, y, z)
        elif (op == '>>'):
            return 'block_%s_%s_%s.lshr(%s,%s,%s);\n' % (self.if_nb, self.if_level, self.else_level, x, y, z)

    def arrayLoad (self, variable, arr, index):
        statements = 'block_%s_%s_%s.array_load(%s, %s, %s, 1);\n' % (
        self.if_nb, self.if_level, self.else_level, variable, arr, index)
        return statements

    def arrayStore (self, arr1, var, index1, index2, chk):
        statements = ''
        # var is a varible, a[i] = x
        if (not chk):
            statements = 'block_%s_%s_%s.array_store(%s, %s, %s, 1);\n' % (self.if_nb, self.if_level, self.else_level,arr1, index1, var)
        else:  # var is an array: a[i] = b[i] (var)
            statements = 'block_%s_%s_%s.array_load(tmp_%s, %s, %s, 1);\n' % (self.if_nb, self.if_level, self.else_level,var, var, index2)
            statements += 'block_%s_%s_%s.array_store(%s, %s, tmp_%s, 1);\n' % (self.if_nb, self.if_level, self.else_level,arr1, index1, var)
        return statements

    tmpIndex = 0

    def encodeAssignment (self, lval_str, statement_str):
        statements = ''
        binaryOp = ''
        # encode every atomic binaryOp, e.g (x+y), (x*y)
        while statement_str.find(')') > 0:
            p2 = statement_str.find(')')
            p1 = statement_str[:p2].rfind('(')
            binaryOp = statement_str[p1:p2 + 1]
            p3, p4 = binaryOp.find(' '), binaryOp.rfind(' ')
            op, y, z = binaryOp[p3 + 1:p4], binaryOp[1:p3], binaryOp[p4:len(binaryOp) - 1]
            # if y and z are not  array elements
            if ('[' not in (y + z)):
                pass
            else:  # in the case the statement contains arrays
                if ('[' in y):
                    index = y[y.find('[') + 1:y.find(']')]
                    self.tmpIndex = self.tmpIndex + 1
                    tmp = 'tmp%s' % self.tmpIndex
                    self.variable_declareration += 'z_var %s(vfac["%s"], crab::INT_TYPE, 32);\n' % (tmp, tmp)
                    statements += self.arrayLoad(tmp, y[:y.find('[')], index)
                    y = tmp
                if ('[' in z):
                    index = z[z.find('[') + 1: z.find(']')]
                    self.tmpIndex = self.tmpIndex + 1
                    tmp = 'tmp%s' % self.tmpIndex
                    self.variable_declareration += 'z_var %s(vfac["%s"], crab::INT_TYPE, 32);\n' % (tmp, tmp)
                    statements += self.arrayLoad(tmp, z[:z.find('[')], index)
                    z = tmp

            # we now replace a binaryOp by a tmp variable
            self.tmpIndex = self.tmpIndex + 1
            x = 'tmp%s' % self.tmpIndex
            self.variable_declareration += 'z_var %s(vfac["%s"], crab::INT_TYPE, 32);\n' % (x, x)
            statement_str = statement_str[0:p1] + 'tmp%s' % self.tmpIndex + statement_str[p2 + 1:]
            statements += self.encode_basicAssignment(x, y, z, op)
        # encode the last binayOp (i.e x = y + tmp )
        if ('[' in lval_str):
            index = index = lval_str[lval_str.find('[') + 1:lval_str.find(']')]
            statements += 'block_%s_%s_%s.array_store(%s, %s, %s, 1);\n' % (
            self.if_nb, self.if_level, self.else_level, lval_str[:lval_str.find('[')], index, statement_str)
        else:
            statements += 'block_%s_%s_%s.assign(%s,%s);\n' % (
            self.if_nb, self.if_level, self.else_level, lval_str, statement_str)
        return statements

    if_level = 0
    else_level = 0
    if_nb = 0

    def visit_Assignment (self, n):
        rval_str = self._parenthesize_if(n.rvalue, lambda n: isinstance(n, pycparser.c_ast.Assignment))
        lval_str = self.visit(n.lvalue)

        assgmt = '%s %s (%s);' % (self.visit(n.lvalue), n.op, rval_str)
       # print('visiting assignment: %s trong nb_if= %s tai if_level= %s va else_level =%s' % (assgmt, self.if_nb, self.if_level, self.else_level))

        if self.if_level == 0 and self.else_level == 0 :
            # create a new block and compute the parents for such block
            new_block = 'block_%s_%s_%s' % (self.if_nb, self.if_level, self.else_level)
            new_block_decl = 'z_basic_block_t& %s = cfg->insert("%s");\n' % (new_block, new_block)
            # compute the parent for exit block
            self.exit_parents = new_block + ' >> exit;\n'

            if len(self.last_ifelse_blocks) > 0:
                self.block_declareration += new_block_decl
                for block in self.last_ifelse_blocks:
                    self.block_declareration += '%s >> %s;\n' % (block, new_block)
                    self.last_ifelse_blocks = []
                    self.last_state_block = new_block

            elif ( len(self.last_state_block ) > 1 and self.last_state_block != new_block):
                self.block_declareration += new_block_decl
                self.block_declareration += '%s >> %s;\n'%(self.last_state_block,new_block)
                self.last_state_block = new_block

        # We now start to encode the assignment, basic case: e.g, x = y, x = a[i], x = 2, a[i] = x; a[i] = b[i] ...
        if (not isinstance(n.rvalue, pycparser.c_ast.BinaryOp)):

            if (not isinstance(n.rvalue,
                               pycparser.c_ast.ArrayRef)):  # the left side of the assignment is a variable or constant
                rvalue = ''
                if (isinstance(n.rvalue, pycparser.c_ast.Constant)):
                    rvalue = n.rvalue.value
                else:
                    rvalue = n.rvalue.name
                if (not '[' in lval_str):
                    self.enc = self.enc + 'block_%s_%s_%s.assign(%s,%s);\n' % (self.if_nb, self.if_level, self.else_level,n.lvalue.name, rvalue)
                else:  # a[i] = x  arr1,var,index1,index2,chk
                    self.enc = self.enc + self.arrayStore(n.lvalue.name.name, rvalue, n.lvalue.subscript.value, 0, 0)
            else:  # if the right side of the assignment is an array element
                if (not '[' in lval_str):
                    self.enc = self.enc + 'block_%s_%s_%s.array_load(%s, %s, %s, 1);\n' % (self.if_nb, self.if_level, self.else_level,
                    n.lvalue.name, n.rvalue.name.name, n.rvalue.subscript.value)
                else:  # (self, arr1,var,index1,index2,chk):
                    self.enc = self.enc + self.arrayStore(n.lvalue.name.name, n.rvalue.name.name,
                                                          n.lvalue.subscript.value, n.rvalue.subscript.value, 1)

        # the right assignment contains a bynaryop and the left side is a variable, e.g: x = y + a or x = y + z
        elif sum(map(lambda x: 1 if '(' in x else 0,
                     '(' + rval_str + ')')) < 2 and not '[' in rval_str and not '[' in lval_str:
            # compute values for y, z
            y = n.rvalue.left.value if isinstance(n.rvalue.left, pycparser.c_ast.Constant) else n.rvalue.left.name
            z = n.rvalue.right.value if isinstance(n.rvalue.right, pycparser.c_ast.Constant) else n.rvalue.right.name
            self.enc = self.enc + str(self.encode_basicAssignment(n.lvalue.name, y, z, n.rvalue.op))
        else:

            left_val = self.visit(n.lvalue);
            self.enc = self.enc + self.encodeAssignment(left_val, '(' + rval_str + ')');
        # return super(self.__class__, self).visit_Assignment(n)
        return ''

    # to get the negative form of a condition in If
    def get_negative_Form(self,cond):
        negative_form = cond
        if negative_form.find('>=') > 0:  negative_form =negative_form.replace('>=', '<',1)
        elif negative_form.find('<=') > 0: negative_form =negative_form.replace('<=', '>',1)
        elif negative_form.find('==') > 0: negative_form =negative_form.replace('==', '!=',1)
        elif negative_form.find('!=') > 0: negative_form =negative_form.replace('!=', '==',1)
        elif negative_form.find('>'): negative_form = negative_form.replace('>', '<=',1)
        elif negative_form.find('<') > 0: negative_form =negative_form.replace('<', '>=',1)
        return negative_form

    # to nomarlize a condition if it contains array elements
    def nomarlize_Cond(self, cond):
        statements = ''
        new_cond = cond
        for arr in self.arrays:
            p = new_cond.find(arr+'[')
            while p > 0:
                index = new_cond[p+len(arr)+1: p+len(arr)+ new_cond[p:].find(']')-1]
                self.tmpIndex = self.tmpIndex + 1
                tmp = 'tmp%s' % self.tmpIndex
                self.variable_declareration += 'z_var %s(vfac["%s"], crab::INT_TYPE, 32);\n' % (tmp, tmp)
                self.enc += self.arrayLoad(tmp, arr, index)
                new_cond = new_cond.replace(arr+'['+index + ']',tmp)
                p = new_cond.find(arr + '[')
        return  new_cond


    def visit_If1 (self, n):

        nomarlized_cond =''
        nomarlized_cond = self.nomarlize_Cond( self.visit(n.cond))

        self.if_level += 1
        self.if_nb += 1
        s = 'if ('
        if n.cond: s += self.visit(n.cond)
        s += ')\n'

        new_block = 'block_%s_%s_%s' % (self.if_nb, self.if_level, self.else_level)
        new_parents = [new_block]
        self.block_declareration += 'z_basic_block_t& %s = cfg->insert("%s");\n' % (new_block, new_block)

        # add parents for new_block
        parents = self.last_ifelse_blocks + [self.last_state_block]

        for block in parents :
            if(len(block) > 1):
                self.block_declareration += '%s >> %s;\n' % (block, new_block)

        self.enc += '%s.assume(%s); \n' % (new_block, nomarlized_cond)
        s += self._generate_stmt(n.iftrue, add_indent=True)
        #print('ket thuc if thu %s  ' % self.if_nb)
        self.if_level -= 1
        if n.iffalse:
            self.else_level += 1
            new_block = 'block_%s_%s_%s' % (self.if_nb, self.if_level, self.else_level)
            new_parents.append(new_block);

            self.block_declareration += 'z_basic_block_t& %s = cfg->insert("%s");\n' % (new_block, new_block)
            self.enc += '%s.assume(%s); \n' % (new_block, self.get_negative_Form(nomarlized_cond))

            # add parents for new_block
            parents = self.last_ifelse_blocks + [self.last_state_block]

            for block in parents:
                if (len(block) > 1):
                    self.block_declareration += '%s >> %s;\n' % (block, new_block)

            #explore the else statement
            s += self._make_indent() + 'else\n'
            s += self._generate_stmt(n.iffalse, add_indent=True)

            print('')
            self.else_level -= 1
        # the last blocks should the two new_block
        self.last_state_block = ''
        self.last_ifelse_blocks = new_parents

        # compute the parent for exit block
        self.exit_parents =''
        for block in new_parents:
            self.exit_parents += block + ' >> exit;\n'

        return s
        # return super(self.__class__, self).visit_If(n)

    def visit_If (self, n):
        nb_if = self.if_nb
        self.visit_If1(n)
        return ''
