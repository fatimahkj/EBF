""" CSeq Program Analysis Framework
    function ignore assertions
    
The purpose of this module is to remove assert functions when running the data race check,
in order to avoid wrong results from files that also have the unreach-call property 

"""
import core.module
import core.parser
import core.utils


class ignoreassertions(core.module.Translator):

    def init(self):
        self.inputparam('data-race-check', 'Runs the data race module',
                        '', default=False, optional=True)

        self.dataracecheck = False

    def loadfromstring(self, string, env):
        self.dataracecheck = True if self.getinputparam(
            'data-race-check') is not None else False

        if self.dataracecheck:
            header = core.utils.printFile('modules/ignore_assertions_header.c')
            self.insertheader(header)

        super(self.__class__, self).loadfromstring(string, env)

    def visit_FuncCall(self, n):
        """
        # name: Id
        # args: ExprList
        #
        FuncCall: [name*, args*]
        """
        ret = super(self.__class__, self).visit_FuncCall(n)

        if not self.dataracecheck:
            return ret

        assertions = ["assert", "ASSERT", "reach_error", "abort"]

        if hasattr(n.name, 'name') and n.name.name in assertions:
            return "__dummy__()"

        return ret

    def visit_Label(self, n):
        """
        Label: [name, stmt*]
        """
        ret = super(self.__class__, self).visit_Label(n)

        if not self.dataracecheck:
            return ret
        
        if 'ERROR' in n.name:
            return self._generate_stmt(n.stmt)
        
        return ret
