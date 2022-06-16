""" CSeq Program Analysis Framework
    switch transformed module

Convert switch stmt to if ... else with goto label:

  switch (x) {
      case a:                  cond_x = x;
          block1;              if (x == a)
          break;               {
          block0;                  block1;
      case b:                      goto exit_switch;
          block2;                  block0;
          break;               }
      case c:                  if (x == b)
          block3;              {
      case d:                      label_b:;
          block4;                  block2;
      default:                     goto exit_switch;
          block5;                  goto label_c;
  }                            }
                               if(x == c)
                               {
                                   label_c:;
                                   block 3;
                                   goto label_d;
                               }
                               if (x == d)
                               {
                                   label_d:;
                                   block4;
                                   goto label_default;
                               }
                               if (! (x == a || x == b || x == c || x == d))
                               {
                                   label_default:;
                                   block5;
                               }
                               exit_switch:;

Author:
    Truc Nguyen Lam, University of Southampton.

Changes:
    2020.03.24 (CSeq 2.0)
    2016.08.17  change into LazyCSeq
    2016.06.14  fix nested switches label name (when one switch is in function that will be inlined in another switch)
    2015.01.15  fix condition variable for switch(cond)
    2015.01.09  immigrate code from UL-Cseq

To do:
  - urgent: combine switchtransformer, dowhileconverter, and conditionextractor
  - code review

"""
import re
import pycparserext.ext_c_parser, pycparser.c_ast, pycparserext.ext_c_generator
import core.module, core.parser, core.utils


class switchtransformer(core.module.Translator):
    __currentSwitchCount = 0
    __currentSwitchVar = []
    __currentSwitchExprALL = []
    __caseCount = {}

    __currentFunction = ''

    def visit_FuncDef(self, n):
        decl = self.visit(n.decl)
        self.indent_level = 0
        self.__currentFunction = n.decl.name
        body = self.visit(n.body)
        self.__currentFunction = ''
        if n.param_decls:
            knrdecls = ';\n'.join(self.visit(p) for p in n.param_decls)
            return decl + '\n' + knrdecls + ';\n' + body + '\n'
        else:
            return decl + '\n' + body + '\n'

    def visit_Switch(self, n):
        # Increase ID of switch
        cond = self.visit(n.cond)
        self.__currentSwitchCount += 1
        switchCondVar = '__cs_switch_cond_%s_%s' % (self.__currentFunction, self.__currentSwitchCount)
        self.__currentSwitchVar.append(switchCondVar)
        self.__caseCount[self.__currentSwitchCount] = 0
        self.__currentSwitchExprALL.append([])
        header = self._make_indent() + '; static int %s;%s = %s;\n' % (switchCondVar, switchCondVar, cond)
        s = self._generate_stmt(n.stmt, add_indent=True)
        s = s[s.find('{') + 1:s.rfind('}')]
        endCaseNumber = self.__caseCount[self.__currentSwitchCount] + 1
        switchEndLabel = '__cs_switch_%s_%s_case_%s' % (self.__currentFunction, self.__currentSwitchCount, endCaseNumber)
        switchEndLabelFinal = '__cs_switch_%s_%s_exit' % (self.__currentFunction, self.__currentSwitchCount)
        s += self._make_indent() + switchEndLabel + ':;'
        breakLabel = '<case-break-of-switch-%s_%s>' % (self.__currentFunction, self.__currentSwitchCount)
        self.__currentSwitchExprALL.pop()
        self.__currentSwitchVar.pop()
        self.__currentSwitchCount -= 1
        s = s.replace(breakLabel, 'goto %s;' % switchEndLabel)
        s = s.replace(switchEndLabel, switchEndLabelFinal)
        return header + s

    def visit_Case(self, n):
        expr = self.visit(n.expr)
        self.__currentSwitchExprALL[-1].append(expr)
        ifcond = self.__currentSwitchVar[-1] + " == " + expr
        self.__caseCount[self.__currentSwitchCount] += 1
        caseNumber = self.__caseCount[self.__currentSwitchCount]
        s = 'if (%s)\n' % ifcond
        s += self._make_indent() + '{\n'
        self.indent_level += 1
        # Make a label for this case here
        if self.__caseCount[self.__currentSwitchCount] > 1:
            s += self._make_indent() + '__cs_switch_%s_%s_case_%s:;\n' % (
                self.__currentFunction, self.__currentSwitchCount, caseNumber)
        hasBreak = False
        for i in range(0, len(n.stmts)):
            if type(n.stmts[i]) == pycparser.c_ast.Break:
                hasBreak = True
                s += self.visit(n.stmts[i])
            else:
                s += self._generate_stmt(n.stmts[i], add_indent=False)
        if not hasBreak:
            s += self._make_indent(delta=0) + 'goto __cs_switch_%s_%s_case_%s;\n' % (
                self.__currentFunction, self.__currentSwitchCount, caseNumber + 1)
        self.indent_level -= 1
        s += self._make_indent() + '}\n'
        return s

    def visit_Default(self, n):
        self.__caseCount[self.__currentSwitchCount] += 1
        caseNumber = self.__caseCount[self.__currentSwitchCount]
        cond = '!('
        for i, e in enumerate(self.__currentSwitchExprALL[-1]):
            if i != 0:
                cond += ' || '
            cond += self.__currentSwitchVar[-1] + ' == ' + e
        cond += ')'

        s = 'if (%s) \n' % cond
        s += self._make_indent() + '{\n'
        self.indent_level += 1
        s += self._make_indent() + '__cs_switch_%s_%s_case_%s:;\n' % (
            self.__currentFunction, self.__currentSwitchCount, caseNumber)
        hasBreak = False
        for i in range(0, len(n.stmts)):
            if type(n.stmts[i]) == pycparser.c_ast.Break:
                hasBreak = True
                s += self.visit(n.stmts[i])
            else:
                s += self._generate_stmt(n.stmts[i], add_indent=False)
        if not hasBreak:
            s += self._make_indent(delta=0) + 'goto __cs_switch_%s_%s_case_%s;\n' % (
                self.__currentFunction, self.__currentSwitchCount, caseNumber + 1)
        self.indent_level -= 1
        s += self._make_indent() + '}\n'
        return s

    def visit_Break(self, n):
        innermostSwitch = -1
        # Find the innermost stmt that has this break stmt
        for i in reversed(range(0, len(self.stack))):
            if self.stack[i] == 'Case':
                innermostSwitch = 1
                break
            if self.stack[i] == 'Default':
                innermostSwitch = 1
                break
            if self.stack[i] == 'For':
                innermostSwitch = 0
                break
            if self.stack[i] == 'While':
                innermostSwitch = 0
                break
            if self.stack[i] == 'DoWhile':
                innermostSwitch = 0
                break

        if innermostSwitch == -1:
            self.error("break statement outside switch, for, while or do..while blocks.\n")

        if innermostSwitch == 1:
            return self._make_indent() + '<case-break-of-switch-%s_%s>\n' % (
                self.__currentFunction, self.__currentSwitchCount)
        else:
            return 'break;'
