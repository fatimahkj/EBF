#!/usr/bin/env python3
FRAMEWORK_VERSION = 'CSeq-3.0-2021.02.02'

""" CSeq Program Analysis Framework
    command-line user interface

Author:
    Omar Inverso

Changes:
    2021.01.26  now storing the path of each module in the cseqenv object
    2020.12.21  slight changes to support Python 3
    2020.05.28  fixed initialisation of mandatory parameters with default values [SV-COMP 2021]
    2020.04.07  exit codes: 0 means termination of without errors, 1 otherwise
    2020.03.24 (CSeq 2.0)
    2019.11.20 (CSeq 1.9) [SV-COMP 2020]
    2019.11.15  support for compiler extensions (e.g. GNUC) thanks to pycparserext+pycparser 2.18
    2019.10.04  verbosity levels: 0 errors, 1 warnings+errors, 2 messages+warning+errors, default 1.
    2019.10.04  slight code tidy-up
    2019.10.01  fpmath configuration [ICCPS 2018] ported with consistent experimental results
    2019.10.01  modules can now be grouped into subdirectories
    2019.10.01  improved printable comments (### comment, and ## comment) in configuration files
    2019.03.11 (CSeq 1.9) towards merging all forks
    2018.11.24 [SV-COMP 2019] last submitted version
    2018.11.24  printable comments (e.g., ## comment) in configuration files
    2018.11.07  showfullmapback() now also prints initial coords that referr to a .i file instead of .c and .h only
    2018.11.07  fixed merger's linemapping for preprocessed files to refer to the original input .i file
    2018.11.04  extended debug information (see debugextended)
    2018.10.27 (CSeq 1.6) [SV-COMP 2019] initial experiments
    2018.10.27  added (optional) workarounds for successfully parsing SVCOMP2019 .i files
    2018.07.19  improved exception handling and on-screen report
    2018.04.22 (CSeq 1.5) experiments with parallel analysis
    2017.02.27 (CSeq 1.4) start porting to python3
    2016.12.15 (CSeq 1.3)
    2016.12.05  new debug option to show linemap
    2016.11.01  improved usage screen
    2016.09.24  improved module error output
    2016.05.05 (CSeq 1.2) student's coursework with transformation examples
    2016.05.03 (CSeq 1.1) debug options
    2015.07.16 (CSeq 1.0) [ASE 2015]
    2015.06.23  major work on modularization (module parameters,front-end output depending on the configuration)
    2015.05.05  output header with translation detail to replicate experiments
    2015.01.18  minor bugfixing in reading module chains
    2015.01.07  fixing default parameters assignments
    2014.12.24 (CSeq 1.0beta)
    2014.12.09  new CSeq framework organisation
    2014.09.27 (CSeq Lazy-0.6, newseq-0.6a, newseq-0.6c), [SV-COMP 2015]
    2014.09.27  moved all code-sanitising to merger stage (merger.py).
    2014.09.22  use strings rather than temporary files before merging (faster)
    2014.09.22  moved thread_local workaround to merging stage (merger.py)
    2014.06.02  introduced specific  module.ModuleError  exception for detailed error handling
    2014.02.28  major code refactory
    2014.02.28  error details from module->module transforms incl. source snippet
    2014.02.28  uniform module importing and handling through one main for loop

To do:
  - check or reimplement function check() after porting to Python 3

  - module handling: add hash signatures within a configuration file
    to make sure one is using the required version of each module (replicability)

  - this is too long and unreadable now, need to arrange the code properly

  - at the end of the analysis, user time should be reported in addition to wall clock time

  - review all error messages and warnings

  - merger's linemapping should also track the input filename

  - handle multiple command-line parameters,
    for example -I firstpath -I secondpath,
    also -i firstsourcefile.c -i secondsourcefile.c

  - maybe rather than being part of the core files the merger should be a normal translation module
   (useful for instance to handle parameter passing across other modules in a uniform way,
    but would mess things up with linemapping)

  - issue a warning message when concurrent versions are running
   (useful, for example, with -D which is obviously not thread-safe as it writes the same files to the same folder)

"""
import os, sys, time, getopt, glob, importlib, inspect, re, shutil, traceback, resource, pycparser
import core.config, core.merger, core.module, core.parser, core.utils
from core.utils import colors as colors

####requirepycparser = '2.18'
####requirepython = '2.7'


class cseqenv:
	cmdline = None         # full command-line
	opts = None            # command-line option-value pairs, e.g. (--input, 'file.c')
	args = None            #
	verbosity = 1          # 0 = errors, 1 = errors and warnings, 2 = errors, warnings, and messages

	params = []            # additional front-end input parameters
	paramIDs = []          # parameters ID only
	paramvalues = {}       # param values indexed by param ID

	debug = False          #
	debugextended = False
	showsymbols = False    #
	showast = False        #
	shownodes = False      #
	showlinemap = False    #

	chainfile = None       # file with the sequence of modules to execute
	chaincomment = ''      # notes within the chainfile (comments with ### at the beginning)

	inputfile = None       # input source file to process
	includepath = None     # #include path (for source merging)
	outputfile = None      # TODO not implemented yet

	modules = []           # modules (each performing a single code trasformation)
	modulecomment = {}     # notes (##) before each module
	modulehash = {}        # hash of the module, if defined in the chainfile
	modulepath = {}        # path to the module, relative to cseq-working-directory/modules

	transforms = 0         # no. of modules executed so far

	maps = []
	lastlinenoinlastmodule = 0
	outputtofiles = []     # map coords from merged sources to the input source file(s)


def moduleparamusage(p):
	abc = "--%s" % (p.id)
	abc += " <%s>" % p.datatype if p.datatype else ''

	opt = 'optional' if p.optional else ''
	opt += ', ' if p.optional and p.default else ''
	opt += 'default:%s%s%s' % (colors.FAINT,p.default,colors.NO) if p.default else ''
	opt = '(%s)' % opt if len(opt) > 0 else opt

	desc = ('\n    '+' '*27).join([l for l in p.description.split('\n')]) # multiline description

	return "%-27s %s %s" % (abc, desc, opt)


def usage(cmd, errormsg, showhelp=True, detail=False):
	# Long help (-H) provides the list of all input and output parameters
	# for each module.
	#
	# Short help (-h) provides only the input parameters
	# that must be provided in the command line.
	#
	# The input parameters for a given module in the chain
	# are those that are not generated by any of the preceeding modules
	# (see class core.module).
	#
	if showhelp:
		config = core.utils.extractparamvalue(cseqenv.cmdline, '-l','--load', core.config.defaultchain)
		currentconfig = core.config.defaultchain if config == core.config.defaultchain else config
		currentconfig = colors.HIGHLIGHT+currentconfig+colors.NO
		defaultorcurrent = 'default' if config == core.config.defaultchain else 'currently'

		searchpath = colors.FAINT+'./'+colors.NO
		debugpath = colors.FAINT+core.config.debugpath+colors.NO

		version = FRAMEWORK_VERSION[FRAMEWORK_VERSION.find('-')+1:]
		version = version[:version.find('-')].split('.')
		vmajor = version[0]
		vminor = version[1]

		print("")
		print("                  C  S e q   ")
		print("                               %s . %s"  % (vmajor,vminor))
		print("")
		print("Usage: ")
		print("")
		print("   %s -h [-l <config>]" % cmd)
		print("   %s -i <input.c> [options]" % cmd)
		print("")
		print(" configuration options: ")
		print("   -l, --load=<file>           configuration to use (%s:%s)" % (defaultorcurrent,currentconfig))
		print("   -L, --list-chains           show available configurations")
		print("")
		print(" input options:")
		print("   -i<file>, --input=<file>    input filename")
		print("   -I<path>, --include=<path>  include search path (use : as a separator) (default:%s)" % (searchpath))
		print("")

		# Module-specific params for the given chain (or for the default one)
		print(" options:")

		outputparamssofar = []   # used to check which module input params are front-end input
		inputparamssofar = []

		for m in cseqenv.modules:
			if detail:
				print("  [%s]" % m.name())
				if len(m.inputparamdefs) == len(m.outputparamdefs) == 0: print('')

			try:
				if detail:
					if len(m.inputparamdefs) > 0: print("     input:")

				for p in m.inputparamdefs:
					if (p.id not in [q.id for q in outputparamssofar] and
					p.id not in [q.id for q in inputparamssofar]):
						inputparamssofar.append(p)
						print('   '+moduleparamusage(p))
					elif detail:
						print('  ('+moduleparamusage(p)+')')

				if detail and len(m.inputparamdefs) > 0: print('')

				if detail:
					if len(m.outputparamdefs) > 0: print("     output:")

				for p in m.outputparamdefs:
					outputparamssofar.append(p)
					if detail:
						abc = "--%s" % (p.id)
						print("   %-26s %s" % (abc, p.description))

				if detail and len(m.outputparamdefs) > 0: print('')

			except Exception as e:
				print("Module error '%s':\n%s.\n" % (m.name(), str(e)))
				traceback.print_exc(file=sys.stdout)
				sys.exit(10)

		print("")
		print(" debugging options: ")
		print("   -D, --debug                 dump (to:%s) temporary files for each module" % (debugpath))
		print("   -X, --debug-stdout          dump (to stdout) temporary files for each module" )
		print("   -S, --show-symbols          show symbol table and exit")
		print("   -A, --show-ast              show abstract syntax tree and exit")
		print("   -M, --show-linemap          show linemap at the end")
		#print "   -N, --shownodes             show ...")
		print("")
		print(" other options: ")
		print("   -h, --help                  show help")
		print("   -H, --detailedhelp          show detailed configuration-specific help")
		print("   -q, --quiet                 show errors only")
		print("   -b, --verbose               show errors, warnings, and messages")
		print("   -v, --version               show version number")
		print("")

	if errormsg:
		print(errormsg + '\n')
		sys.exit(10)

	sys.exit(0)


def listmodulechains():
	list = ''
	for filename in glob.glob('modules/*.chain'): list += filename[len('modules/'):-len('.chain')] + '\n'
	if list.endswith(', '): list = list[:-2]
	return list


def _showfullmapback():
	# Note: since the same input line may correspond to
	#       multiple lines in the final output,
	#       the tracing has to be done backwards.
	#
	lastmodule = len(cseqenv.maps)
	nextkey = 0
	inputfile = ''

	additionalspace = 4
	symbolspace = '.'

	for lineno in range(1,cseqenv.lastlinenoinlastmodule):
		lastmodule = len(cseqenv.maps)
		nextkey = 0
		inputfile = ''

		#if cseqenv.maps[len(cseqenv.maps)-1].has_key(lineno):
		buff = ''

		if lineno in cseqenv.maps[len(cseqenv.maps)-1]:
			firstkey = nextkey = lastkey = lineno

			printfirstkey = symbolspace*(additionalspace+len(str(max(cseqenv.maps[len(cseqenv.maps)-1]))) - len(str(firstkey)))+str(firstkey)

			buff +="%s" % printfirstkey

			for modno in reversed(range(0,lastmodule)):
				if nextkey in cseqenv.maps[modno] and nextkey != 0:
					lastkey = nextkey
					nextkey = cseqenv.maps[modno][nextkey]

					printnextkey = symbolspace*(additionalspace+len(str(max(cseqenv.maps[modno]))) - len(str(nextkey)))+str(nextkey)

					buff+="%s" % printnextkey
				else:
					nextkey = 0

				if modno == 0 and lastkey in cseqenv.outputtofiles:
					inputfile = cseqenv.outputtofiles[lastkey]
					buff +=" %s" %inputfile

		if not buff.endswith('_fake_typedefs.h'): ## and (buff.endswith('.c') or buff.endswith('.h')):
			print(buff)


def warn(string):
	if cseqenv.verbosity > 1:
		tag = core.utils.colors.FAINT +string+ core.utils.colors.NO
		print(tag)


'''
def check():
	## sanity checks
	## pkg_resources.get_distribution("pycparserext").version 2015.1
	## pkg_resources.get_distribution("pycparser").version    2.14
	needpython = requirepython.split('.')

	print("sdlkfjdskfjdsklfdsj %s " % str(sys.version_info))

	if (int(needpython[0]),int(needpython[1])) > sys.version_info:
		print("Python version mismatch: installed version is %s.%s, version %s or later is required.\n" % (sys.version_info[0],sys.version_info[1],requirepython))
		sys.exit(10)

	havepyc = pycparser.__version__.split('.')
	needpyc = requirepycparser.split('.')

	if (int(needpyc[0]),int(needpyc[1])) > (int(havepyc[0]),int(havepyc[1])):
		print("pycparser version mismatch: installed version is %s, version %s or later is required.\n" % (pycparser.__version__,requirepycparser))
		sys.exit(10)
'''


def init():
	'''
	# List all pycparser's AST visit_xyz methods
	# (any of them can be overridden in a module)
	#
	k = core.parser.Parser()
	methods = inspect.getmembers(k, predicate=inspect.ismethod)

	for m in methods:
		if m[0].startswith('visit_'): print m[0]

	sys.exit(0)
	'''

	'''                   '''
	''' I. Initialisation '''
	'''                   '''
	cseqenv.cmdline = sys.argv
	cseqenv.starttime = time.time()    # save wall time

	# Extract the configuration from the command-line or set it to the default.
	cseqenv.chainname = core.utils.extractparamvalue(cseqenv.cmdline, '-l','--load', core.config.defaultchain)
	cseqenv.chainfile = 'modules/%s.chain' % core.utils.extractparamvalue(cseqenv.cmdline, '-l','--load', core.config.defaultchain)

	if not core.utils.fileExists(cseqenv.chainfile):
		usage(cseqenv.cmdline[0], 'error: unable to open configuration file (%s)' % cseqenv.chainfile, showhelp=False)

	# Import all modules in the current configuration.

	# Module comments.
	#
	# Notes related to the whole configuration can be positioned
	# at the beginning of the file (e.g., '### This configuration implements CAV2014 paper') and
	# will be shown by the user interface as the configuration is loaded.
	#
	# Intermediate comments (e.g., '## Program flattening') can occur anywhere and are shown
	# during the execution of the modules.
	#
	# Regular comments (e.g., '# text') are just ignored.
	#
	for line in core.utils.printFile(cseqenv.chainfile).splitlines():
		if line.startswith('### ') or line == '###':    # configuration notes
			if cseqenv.chaincomment == '':
				#print("%s%s%s" % (core.utils.colors.FAINT,line[4:],core.utils.colors.NO))
				cseqenv.chaincomment = line[4:]
			else:
				#print("%s%s%s" % (core.utils.colors.FAINT,line[4:],core.utils.colors.NO))
				cseqenv.chaincomment += '\n' +line[4:]

		elif line.startswith('## ') or line == '##':    # comments related to next module
			if len(cseqenv.modules) not in cseqenv.modulecomment:
				cseqenv.modulecomment[len(cseqenv.modules)] = line[3:]
			else:
				cseqenv.modulecomment[len(cseqenv.modules)] += '\n' +line[3:]
		elif not line.startswith('#') and len(line) >= 1:   # comments taking an entire line
			line = line.strip()

			if '#' in line: line = line[:line.find('#')].strip()   # comments at the end of a line

			split = line.split(' ')
			modulename = split[0]
			modulehash = split[1] if len(split) == 2 else ''

			cseqenv.modulehash[modulename] = modulehash

			if cseqenv.modulehash[modulename] != '':
				modhash = core.utils.shortfilehash('modules/%s.py' % modulename)
				warn("module [%s]  hash check ok" % modulename)

				if modulehash != modhash:
					print("error: hash mismatch for module [%s], stored hash [%s] actual hash [%s]" % (modulename,modulehash,modhash))
					exit(10)

			try:
				mod = importlib.import_module('modules.'+modulename.replace('/','.'))  # use dots to import
				modulepath = modulename[:modulename.rfind('/')] if '/' in modulename else ''
				modulename = modulename[modulename.rfind('/')+1:]   # modules.something.module
				cseqenv.modules.append(getattr(mod, modulename)())
				#cseqenv.modulepath[getattr(mod, modulename)()] = modulepath
				cseqenv.modulepath[modulename] = modulepath
				#print("NAME:%s PATH:%s" %(modulename,modulepath))
			except ImportError as e:
				print("Unable to import module '%s',\nplease check installation.\n" % modulename)
				traceback.print_exc(file=sys.stdout)
				sys.exit(10)
			except AttributeError as e:
				print("Unable to load module '%s',\nplease check that the module filename,\nthe entry in the chain-file, and\nthe top-level classname in the module correctly match.\n" % modulename)
				traceback.print_exc(file=sys.stdout)
				sys.exit(10)
			except Exception as e:
				print("%serror%s: unable to initialise (module %s):\n%s.\n" % (colors.HIGHLIGHT,colors.NO,modulename,str(e)))
				traceback.print_exc(file=sys.stdout)
				sys.exit(10)

	# Init modules.
	for m in cseqenv.modules:
		try:
			if 'init' in dir(m):
				m.init()
		except Exception as e:
			print("Unable to initialise module '%s':\n%s.\n" % (m.name(), str(e)))
			traceback.print_exc(file=sys.stdout)
			sys.exit(10)

	# Init module parameters.
	#
	# Modules can have input and output parameters.
	# Any module input that is not the output of a previous module
	# is a front-end parameter
	# (it is displayed in the usage() screen, and
	#  it can be provided to the front-end in the command-line)
	inParams = []      # module-specific input parameters seen so far
	inParamIDs = []
	inparamvalues = {}

	outParams = []     # module-specific output parameters seen so far
	outParamIDs = []
	outparamvalues = {}

	for moduleid,m in enumerate(cseqenv.modules):
		try:
			for p in m.inputparamdefs:  # global input params seen so far
				if p.id not in inParamIDs:
					inParamIDs.append(p.id)
					inParams.append(p)

				# if the input param  p  is new and
				# no previous module generates it
				# (i.e., it is not an output param for any previous module)
				# then it needs to be a global (front-end) input
				if p.id not in outParamIDs:
					cseqenv.paramIDs.append(p.id)
					cseqenv.params.append(p)

			for p in m.outputparamdefs:  # output params seen so far
				if p.id not in outParamIDs:
					outParamIDs.append(p.id)
					outParams.append(p)
		except Exception as e: 
			print("Unable to initialise module '%s':\n%s.\n" % (m.name(), str(e)))
			traceback.print_exc(file=sys.stdout)
			sys.exit(10)

	'''                '''
	''' II. Parameters '''
	'''                '''
	# Parse command-line.
	try:
		shortargs = "hHdi:o:I:e:DXSANMvl:Cqb"
		longargs = [ "help", "detailed-help", "detail", "input=", "output=", "include=",
		             "error-label=",
		             "debug", "debug-stdout", "show-symbols", "show-ast",
		             "show-nodes", "show-linemap", "version", "load=",
		             "list-configs", "quiet", "verbose" ]    # <-- append module params here

		# add one command-line parameter for each module-specific parameter
		for p in cseqenv.params:
			longargs.append('%s%s' % (p.id, '' if p.isflag() else '='))

		cseqenv.opts, cseqenv.args = getopt.getopt(sys.argv[1:], shortargs, longargs)
	except getopt.GetoptError as err:
		usage(cseqenv.cmdline[0], 'error: ' +str(err))

	for o, a in cseqenv.opts:
		if o in ("-v", "--version"): print(FRAMEWORK_VERSION); sys.exit(0)
		elif o in ("-h", "--help"): usage(cseqenv.cmdline[0],'')
		elif o in ("-H", "--detailed-help"): usage(cseqenv.cmdline[0],'',detail=True)
		elif o in ("-l", "--load"): pass # handled beforehand, see above
		elif o in ("-C", "--list-configs"): print(listmodulechains()); sys.exit(0)
		elif o in ("-D", "--debug"):
			cseqenv.debug = True
			cseqenv.verbosity = 2
		elif o in ("-X", "--debug-stdout"): cseqenv.debugextended = True
		elif o in ("-S", "--show-symbols"): cseqenv.showsymbols = True
		elif o in ("-A", "--show-ast"): cseqenv.showast = True
		elif o in ("-N", "--show-nodes"): cseqenv.shownodes = True
		elif o in ("-M", "--show-linemap"): cseqenv.showlinemap = True
		elif o in ("-d", "--detail"): detail = True
		elif o in ("-i", "--input"): cseqenv.inputfile = a
		elif o in ("-o", "--output"): cseqenv.outputfile = a
		elif o in ("-I", "--include"): cseqenv.includepath = a
		elif o in ("-q", "--quiet"): cseqenv.verbosity = 0
		elif o in ("-b", "--verbose"): cseqenv.verbosity = 2
		else: # module-specific parameters
			cseqenv.paramvalues[o[2:]] = a

	if cseqenv.debug and cseqenv.debugextended:
		usage(cseqenv.cmdline[0], 'only one debug mode can be activated.')

	# Basic parameter check.
	if not cseqenv.inputfile: usage(cseqenv.cmdline[0], 'error: input file name not specified.')
	if not core.utils.fileExists(cseqenv.inputfile): usage(cseqenv.cmdline[0], 'error: unable to open input file (%s)' % cseqenv.inputfile, showhelp=False)
	if not core.utils.fileExists(cseqenv.chainfile): usage(cseqenv.cmdline[0], 'error: unable to open module-chain file (%s)' % cseqenv.chainfile, showhelp=False)

	# All global parameters (calculated above) should be in the command-line.
	for p in cseqenv.params:
		#if not p.optional and not p.default:
		if p.optional==False and p.default is None:
			usage(cseqenv.cmdline[0], 'error: %s (option --%s) not specified.' % (p.description, p.id))

	# Debug setup.
	cseqenv.debugpath = core.config.debugpath
	if not os.path.exists(core.config.debugpath): os.makedirs(core.config.debugpath)
	elif cseqenv.debug:
		shutil.rmtree(core.config.debugpath)
		os.makedirs(core.config.debugpath)


def run():
	if cseqenv.debug or cseqenv.verbosity == 2:
		print ("cseq resource ata: soft:%s hard:%s"  % resource.getrlimit(resource.RLIMIT_DATA)  )
		print ("cseq resource stack: soft:%s hard:%s"  % resource.getrlimit(resource.RLIMIT_STACK)  )
		print ("cseq resource resident size: soft:%s hard:%s"  % resource.getrlimit(resource.RLIMIT_RSS)  )
		print ("cseq resource memlock: soft:%s hard:%s"  % resource.getrlimit(resource.RLIMIT_MEMLOCK)  )
		print ("cseq resource as: soft:%s hard:%s"  % resource.getrlimit(resource.RLIMIT_AS)  )

	if cseqenv.verbosity == 2:
		print ("Configuration [%s%s%s] loaded" % (colors.FAINT,cseqenv.chainfile,colors.NO))
		print("%s%s%s" % (core.utils.colors.FAINT,cseqenv.chaincomment,core.utils.colors.NO))

	'''              '''
	''' III. Merging '''
	'''              '''
	# Load the input file.
	input = core.utils.printFileRows(cseqenv.inputfile)

	# Might need to sanitise preprocessed (.i) files due to non-standard syntax.
	if cseqenv.inputfile.endswith(".i"):
		input = core.utils._sanitiseinput(input)

	# Merge all the source files into a single string.
	try:
		timeBefore = time.time()
		fileno = str(cseqenv.transforms).zfill(2)

		if cseqenv.debug or cseqenv.debugextended:
			print("[%s] %s" % (fileno, 'merger'))

		cseqenv.moduleID = 'merger'

		Merger = core.merger.Merger()
		Merger.loadfromstring(input,cseqenv)
		output = Merger.output
		cseqenv.transforms += 1

		if cseqenv.debug:
			core.utils.saveFile('%s/_00_input___merger.c' % core.config.debugpath, input, binary=False)
			core.utils.saveFile('%s/_00_marked__merger.c' % cseqenv.debugpath,Merger.markedoutput,binary=False)
			core.utils.saveFile('%s/_00_output__merger.c' % core.config.debugpath,output,binary=False)
			core.utils.saveFile('%s/_00_linemap__merger.c' % core.config.debugpath,Merger.getlinenumbertable(),binary=False)

		if cseqenv.debugextended:
			dump = input
			print('[%s] %s _00_input___merger.c begin' % (fileno,30*' -'))
			print('%s' % (core.utils.indent(dump,char='[%s] '%fileno,space='')), end='')
			print('[%s] %s _00_input___merger.c end' % (fileno,30*' -'))
			dump = output
			print('[%s] %s _00_output___merger.c begin' % (fileno,30*' -'))
			print('%s' % (core.utils.indent(dump,char='[%s] '%fileno,space='')), end='')
			print('[%s] %s _00_output___merger.c end' % (fileno,30*' -'))
			#dump = Merger.markedoutput
			#print('[%s] %s _00_marked___merger.c begin' % (fileno,30*' -'))
			#print('%s' % (core.utils.indent(dump,char='[%s] '%fileno,space='')), end='')
			#print('[%s] %s _00_marked___merger.c end' % (fileno,30*' -'))
			#dump = Merger.getlinenumbertable()
			#print('[%s] %s _00_linemap___merger.c begin' % (fileno,30*' -'))
			#print('%s' % (core.utils.indent(dump,char='[%s] '%fileno,space='')), end='')
			#print('[%s] %s _00_linemap___merger.c end' % (fileno,30*' -'))

		if cseqenv.debug or cseqenv.debugextended:
			print("[%s] %s %0.2fs " % (fileno,'merger',time.time()-timeBefore))

	except pycparser.plyparser.ParseError as e:
		print("Parse error (%s):\n" % str(e))
		print("%s%s%s" % (colors.HIGHLIGHT, core.utils.snippet(output,Merger.getLineNo(e),Merger.getColumnNo(e),5,True), colors.NO))
		sys.exit(10)
	except SystemExit as e: # the module invoked sys.exit()
		sys.exit(10)
	except:
		traceback.print_exc(file=sys.stdout)
		sys.exit(10)


	'''                    '''
	''' IV. Transformation '''
	'''                    '''
	cseqenv.maps.append(Merger.outputtoinput)
	cseqenv.outputtofiles = Merger.outputtofiles

	# Run all modules in a sequence
	for cseqenv.transforms, m in enumerate(cseqenv.modules):
		try:
			if cseqenv.showsymbols:
				Parser = core.parser.Parser()
				Parser.loadfromstring(output)
				Parser.printsymbols()
				sys.exit(0)

			if cseqenv.showast:
				Parser = core.parser.Parser()
				Parser.loadfromstring(output)
				Parser.ast.show(attrnames=True,nodenames=True,showcoord=True)
				sys.exit(0)

			if cseqenv.shownodes:
				Parser = core.parser.Parser()
				Parser.loadfromstring(output)
				Parser.shownodes()
				sys.exit(0)

			if cseqenv.transforms in cseqenv.modulecomment:
				print ("%s" % cseqenv.modulecomment[cseqenv.transforms])

			timeBefore = time.time()
			fileno = str(cseqenv.transforms+1).zfill(2)

			if cseqenv.debug or cseqenv.debugextended:
				print("[%s] %s" % (fileno, m.name()))

			m.initparams(cseqenv)
			m.loadfromstring(output,cseqenv)
			output = m.output

			if 'inputtooutput' in dir(m):   # linemapping only works on Translator (C-to-C) modules
				cseqenv.maps.append(m.outputtoinput)
				cseqenv.lastlinenoinlastmodule = m.output.count('\n')

			if cseqenv.debugextended:
				#dump = input
				#print('[%s] %s _00_input___merger.c begin' % (fileno,30*' -'))
				#print('%s' % (core.utils.indent(dump,char='[%s] '%fileno,space='')), end='')
				#print('[%s] %s _00_input___merger.c end' % (fileno,30*' -'))
				dump = output
				print('[%s] %s _00_output___%s.c begin' % (fileno,30*' -',m.name()))
				print('%s' % (core.utils.indent(dump,char='[%s] '%fileno,space='')), end='')
				print('[%s] %s _00_output___%s.c end' % (fileno,30*' -',m.name()))

			if cseqenv.debugextended and 'markedoutput' in dir(m):   # only if the current module is a Translator
				pass
				#dump = Merger.markedoutput
				#print('[%s] %s _00_marked___merger.c begin' % (fileno,30*' -'))
				#print('%s' % (core.utils.indent(dump,char='[%s] '%fileno,space='')), end='')
				#print('[%s] %s _00_marked___merger.c end' % (fileno,30*' -'))
				#dump = Merger.getlinenumbertable()
				#print('[%s] %s _00_linemap___merger.c begin' % (fileno,30*' -'))
				#print('%s' % (core.utils.indent(dump,char='[%s] '%fileno,space='')), end='')
				#print('[%s] %s _00_linemap___merger.c end' % (fileno,30*' -'))

			if cseqenv.debug:
				core.utils.saveFile('%s/_%s_input___%s.c' % (cseqenv.debugpath,fileno,m.name()),m.input,binary=False)
				core.utils.saveFile('%s/_%s_output__%s.c' % (cseqenv.debugpath,fileno,m.name()),m.output,binary=False)
				#core.utils.saveFile('_%s_%s.ast.c' % (cseqenv.transforms,moduleName),str(m.Parser.ast.show())) TODO
				#core.utils.saveFile('_%s_%s.symbols.c' % (cseqenv.transforms,moduleName),str(m.Parser.printsymbols())) TODO
				print("[%s] %s %0.2fs " % (fileno,m.name(),time.time()-timeBefore))

			if cseqenv.debug and 'markedoutput' in dir(m):   # only if the current module is a Translator
				core.utils.saveFile('%s/_%s_marked__%s.c' % (cseqenv.debugpath,fileno,m.name()),m.markedoutput,binary=False)
				core.utils.saveFile('%s/_%s_linemap__%s.c' % (cseqenv.debugpath,fileno,m.name()),m.getlinenumbertable(),binary=False)

		except pycparser.plyparser.ParseError as e:
			if cseqenv.transforms == 0:
				print("%ssyntax error%s (%s):\n" % (colors.HIGHLIGHT,colors.NO,str(e)))
				#print("COORDS: %s %s" % (Merger.outputtoinput[m.getLineNo(e)],m.getColumnNo(e)))
				snip = core.utils.snippet(input,m.getLineNo(e),m.getColumnNo(e),5,True)
				print("%s%s%s" % (colors.FAINT,snip,colors.NO))
			else:   # code broken in the last tranformation step
				print("%serror%s (%s) while performing %s->%s:\n" % (colors.HIGHLIGHT,colors.NO,str(e),cseqenv.modules[cseqenv.transforms-1].name() if cseqenv.transforms>0 else '', cseqenv.modules[cseqenv.transforms].name()))
				print("%s%s%s" % (colors.FAINT,core.utils.snippet(output,m.getLineNo(e),m.getColumnNo(e),5,True),colors.NO))
			sys.exit(10)
		except core.module.ModuleParamError as e:
			print("%serror%s: module %s:\n" % (colors.HIGHLIGHT,colors.NO,str(e)))
			sys.exit(10)
		except core.module.ModuleError as e:
			tag = '%serror%s: module %s: ' % (colors.HIGHLIGHT,colors.NO,cseqenv.modules[cseqenv.transforms].name())
			#print(tag) #print colors.RED +tag+ colors.NO,
			#taglen = len(tag)
			print(tag, end='') #print colors.RED +tag+ colors.NO,
			####print('\n'+' '*taglen).join([l for l in str(e)[1:-1].split('\n')])
			print(str(e))
			sys.exit(10)
		except core.module.ModuleSyntaxError as e:
			tag = '%serror%s: module %s: ' % (colors.HIGHLIGHT,colors.NO,cseqenv.modules[cseqenv.transforms].name())
			print(tag, end=' ') #print colors.RED +tag+ colors.NO,
			coords = m.getLastCoords()
			print(coords+str(e))
			snip = core.utils.snippet(cseqenv.modules[cseqenv.transforms].input,cseqenv.modules[cseqenv.transforms].currentinputlineno,0,5,True),
			#snip = snip.splitlines()
			snip = '\n'.join(snip)
			print("\n%s%s%s" % (colors.FAINT,snip,colors.NO))
			sys.exit(10)
		except KeyboardInterrupt as e:
			sys.exit(10)
		except ImportError as e:
			print("Import error (%s),\nplease re-install the tool.\n" % str(e))
			traceback.print_exc(file=sys.stdout)
			sys.exit(10)
		except Exception as e:
			print("%serror%s (%s) while performing %s->%s:\n" % (colors.HIGHLIGHT,colors.NO,str(e),cseqenv.modules[cseqenv.transforms-1].name() if cseqenv.transforms>0 else '', cseqenv.modules[cseqenv.transforms].name()))
			####print("%s%s%s" % (colors.FAINT,core.utils.snippet(output,m.getLineNo(e),m.getColumnNo(e),5,True),colors.NO))
			print(colors.FAINT,end='')
			traceback.print_exc(file=sys.stdout)
			print(colors.NO,end='')
			sys.exit(10)

	print(output)

	if cseqenv.showlinemap:
		_showfullmapback()

	sys.exit(0)
	return


def main():
	# Basic environment check.
	####check() TODO re-check after migration to Python3 (reimplement if necessary)

	# Initialise modules and parse command-line parameters.
	init()

	# Merge and preprocess source file(s).
	# Go through the given module chain.
	run()


if __name__ == "__main__":
	main()







