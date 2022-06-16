#!/usr/bin/env python


def main():
    src = """ int a = f(); """

    from pycparserext.ext_c_parser import GnuCParser
    p = GnuCParser()
    ast = p.parse(src)
    ##ast.show()

    from pycparserext.ext_c_generator import GnuCGenerator
    print(GnuCGenerator().visit(ast))

if __name__ == "__main__":
	main()
