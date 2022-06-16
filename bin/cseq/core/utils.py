""" CSeq Program Analysis Framework
    mixed ancillary functions

Author:
    Omar Inverso

Changes:
    2020.12.21  Slight changes to support Python 3
	2020.04.14  commandpid terminates all sub-processes on ctrl-c
	2020.04.07  commandpid accepts timeout 0
    2020.03.24 (CSeq-2.0)
    2020.03.23  commandpid now also returns memory usage
    2019.11.17  if a file does not exist, filehash() returns '0000'
    2019.11.17  bugfix: Command.run default timeout is None (not 0)
    2019.11.15  general cleanup
    2018.11.04  wrapped snippet extraction in try..except block (see snippet())
    2018.11.04  indent function
    2018.10.23  merged alternative strip function from SVCOMP16 fork (2016.11.22 fix)
    2018.04.23  swapped os.killpg(self.process.pid, signal.SIGKILL) and self.process.kill()
    2016.08.12  add option to show memory usage
    2015.07.10  changed KeyboardInterrupt handling (was not killing the backend on Ubuntu)
    2014.10.09  linemarkerinfo method
    2014.10.07  improved timeout management (Class Command: ctrl-C now kills the backend)

"""
from __future__ import print_function

import datetime, getopt, hashlib, sys, os.path, os, re, glob, resource

class colors:
	BLACK = '\033[90m'
	DARKRED = '\033[31m'
	RED = '\033[91m'
	GREEN = '\033[92m'
	YELLOW = '\033[93m'
	BLUE = '\033[94m'

	HIGHLIGHT = '\033[1m'
	FAINT = '\033[2m'
	UNDERLINE = '\033[4m'
	BLINK = '\033[5m'
	REVERSE = '\033[7m'
	NO = '\033[0m'


def warn(string):
	tag = 'warning:'
	taglen = len(tag)+1
	print(colors.YELLOW+tag+colors.NO, end=" ")  # print colors.YELLOW+tag+colors.NO,
	print('\n'+' '*taglen).join([l for l in string.split('\n')])


''' Extract a specific parameter from the command-line
	without using getopt.

	Getopt does not support parsing parameters
	not defined beforehand,
	so this is useful when the whole set of parameters
	depend on one parameter.
'''
def extractparamvalue(args, shortopt, longopt, default):
	value = default

	# case 1: space after '-X' or '--XYZ'
	if shortopt in args:
		index = args.index(shortopt)
		if index+1 < len(args) and not args[index+1].startswith('-'):
			value = args[index+1]

	if longopt in args:
		index = args.index(longopt)
		if index+1 < len(args) and not args[index+1].startswith('-'):
			value = args[index+1]

	# case 2: no space after '-X' (note that longopts require a trailing space)
	for arg in args:
		if arg.startswith(shortopt) and len(arg)>2:
			value = arg[2:]

	return value


def replaceparamvalue(args, shortopt, longopt, old, new):
	# case 1: space after '-X' or '--XYZ'
	if shortopt in args:
		index = args.index(shortopt)
		if index+1 < len(args) and args[index+1] == old:
			args[index + 1] = new

	if longopt in args:
		index = args.index(longopt)
		if index+1 < len(args) and args[index+1] == old:
			args[index + 1] = new

	# case 2: no space after '-X' (note that longopts require a trailing space)
	for i, arg in enumerate(args):
		if arg.startswith(shortopt) and old in arg:
			args[i] = "-l" + new

'''
Source file name and line number information is conveyed by lines of the form
	# linenum filename flags
After the file name comes zero or more flags, which are 1, 2, 3, or 4.
If there are multiple flags, spaces separate them. Here is what the flags mean:

1	 This indicates the start of a new file.
2	 This indicates returning to a file (after having included another file).
3	 This indicates that the following text comes from a system header file,
		so certain warnings should be suppressed.
4	 This indicates that the following text should be treated as being wrapped
		in an implicit extern "C" block.
As an extension, the preprocessor accepts linemarkers in non-assembler input files.
They are treated like the corresponding #line directive, (see Line Control),
except that trailing flags are permitted, and are interpreted with the meanings
described above. If multiple flags are given, they must be in ascending order.
'''
'''
def getCPPLineDirective(line):
	line = line.rstrip()   # remove end line symbol

	# 1st field: line number
	line = line[2:]
	marker_lineno = line[:line.find('"')-1]   # remove space
	if marker_lineno.isdigit(): marker_lineno = int(marker_lineno)
	else: return (-1, '', None)

	# 2nd field: source file
	line = line[line.find('"')+1:]
	marker_filename = line[:line.find('"')]

	# 3rd field: flag (optional)
	if line[-1].isdigit():
		line = line[line.find('"')+1:].strip()
		flags = line.split(" ")
		marker_flags = []
		for number in flags:
			if number.isdigit():
				marker_flags.append(int(number))
	else: marker_flags = None

	#print " LINENO: '%s'" % marker_lineno
	#print " FILE: '%s'" % marker_filename
	#print " FLAG: '%s'" % marker_flag
	#print "\n\n"

	return (marker_lineno, marker_filename, marker_flags)
'''

''' Extract information from line directive
	Return:
		includeType: type of include (system or user)
		includeFile: file name of include (compatible with include)
'''
'''
def getIncludeFromLine(line, basename):
	includeType = 0
	includeFile = ''
	(marker_lineno, marker_filename, marker_flags) = getCPPLineDirective(line)
	if marker_lineno != -1:
		if marker_filename == basename:
			return (includeType, basename)

		if marker_lineno == 1 and marker_flags is not None:
			if 3 in marker_flags:
				includeType = 3
				includeFile = marker_filename[marker_filename.rfind("include/")+8:]
				includeFile = includeFile.replace('i386-linux-gnu/', '')		# remove architecture dependence
				includeFile = includeFile.replace('x86_64-linux-gnu/', '')
				fake_include = os.path.dirname(__file__)+'/include/'
				if not os.path.isfile(fake_include+includeFile):  # if this file is not in include
					includeType = 0   # ignore that file
					warn("%s not found" % includeFile)
			else:
				includeType = 2   # user header file
				includeFile = marker_filename

	return (includeType, includeFile)
'''


''' Determine if a line directive is a return directive from
'''
'''
def isReturnDirective(line, basename):
	if not line.startswith('# '):
		return False

	(marker_lineno, marker_filename, marker_flags) = getCPPLineDirective(line)
	if marker_lineno == -1:
		return False
	if (marker_filename == basename and
			marker_flags is not None and
			len(marker_flags) == 1  and
			marker_flags[0] == 2
		):
		return True
	else:
		return False
'''


''' Performs a series of simple transformations so that pycparser can handle the input.
'''
def _sanitiseinput(input):
	text = ''

	''' 1. Fix Empty Structures (an issue if pycparser version <=2.18)
	https://gcc.gnu.org/onlinedocs/gcc/Empty-Structures.html
	'''
	#input = re.sub(r'struct\s*(\S+)\s*{\s*}', r'struct \1 { char dummy; }', input)

	''' 2. Fix typeof (SVCOMP16 workaround)
	https://gcc.gnu.org/onlinedocs/gcc/Typeof.html#Typeof
	'''
	#input = input.replace("typeof( ((struct my_data *)0)->dev )", "struct device ")

	for line in input.splitlines():
		# _thread_local workaround
		line = re.sub(r'__thread _Bool (.*) = 0', r'_Bool __cs_thread_local_\1[THREADS+1] ', line)
		line = re.sub(r'_Thread_local _Bool (.*) = 0', r'_Bool __cs_thread_local_\1[THREADS+1] ', line)
		# fix for void; line
		line = re.sub(r'^void;', '', line)

		text += line+'\n'

	text = text.replace('typeof', '__typeof__')
	text = text.replace('____typeof____', ' __typeof__')
	text = text.replace(' __signed__ ', ' signed ')
	text = text.replace('__builtin_va_list', 'int')
	text = text.replace('__extension__','')
	text = text.replace('__inline','')
	text = text.replace('__restrict','')

	return text


''' Extract a snippet of code from  string,
	lines from  linenumber-width  to  linenumber+width (when possible).

	Lines are trimmed down to the terminal column size
	when  trim  is set.

	Note: following compiler and editor conventions,
		  line numbers start from 1, not zero!
'''
def snippet(string, linenumber, colnumber, width, trim=False):
	#TODO: the 'while not finished' loop below may not terminate?
	snippet = ''

	try:
		columnwidth = getTerminalSize()[1]
		splitinput = string.splitlines()
		snippet = ''
		shiftedcolumns = 0
		finished = False

		# first and last line numbers of the snippet
		a = max(0, linenumber-width-1)
		b = min(len(splitinput), linenumber+width)

		# Convert tab to spaces
		for i in range(a,b):
			splitinput[i] = splitinput[i].replace('\t', ' ')  # each tab counts as a column for the parser

		# Get rid of all the empty spaces in common at the beginning to each line,
		# so to shift all the printed code to the left..
		while not finished:
			count = 0
			### print "count: %s   -   finished: %s,   %s %s   shifted:%s" % (count, finished, a, b, shiftedcolumns)

			for i in range(a,b):
				if splitinput[i].startswith(' ') or splitinput[i] == '': count = count+1
				else: finished = True

			if count == len(range(a,b)):
				if count == 0: finished = True
				else:
					for i in range(a,b):
						splitinput[i] = splitinput[i][1:]

					shiftedcolumns+=1

		# Concatenate the actual (possibly shortened) lines from parameter string,
		# to make the snippet
		extraline = ''

		for i in range(a,linenumber):  #for i in range(a,b):
			shiftedcolumns2 = 0

			if i+1 == linenumber:
				# shorten internally the line when it does not fit the terminal
				if colnumber-shiftedcolumns > int(columnwidth*0.9):
					splitinput[i] = splitinput[i][:int(columnwidth*0.1)] + ' ... ' + splitinput[i][colnumber-shiftedcolumns-int(columnwidth*0.6):]
					shiftedcolumns2 = colnumber - int(columnwidth*0.1) - int(columnwidth*0.6) - 5

				nextline = " > %s" % (splitinput[i])
				pointer = '~~~^' if (colnumber-shiftedcolumns-shiftedcolumns2) > 4 else '^~~~'
				extraline = "   " + ' '*(colnumber-shiftedcolumns-shiftedcolumns2) + pointer
			else:
				nextline = "    %s" % (splitinput[i])

			if trim and len(nextline) > columnwidth:
				nextline = nextline[:int(columnwidth*0.9)] + '...'

			snippet += nextline + '\n'

			if extraline != '':
				snippet += extraline + '\n'
				extraline = ''
	except:
		snippet = 'unable to extract code snippet'

	return snippet


''' Extract linemarker information.

	Examples:
		linemarkerinfo('# 1 "<built-in>" 1')         -->  (1, '<built-in>', 1)
		linemarkerinfo('# 1 "<stdin>"')              -->  (1, '<stdin>', -1)
		linemarkerinfo('# 1 "include/pthread.h" 2')  -->  (1, 'include/pthread.h', 2)

   (for a description of linemarkers see:
	https://gcc.gnu.org/onlinedocs/gcc-4.3.6/cpp/Preprocessor-Output.html)

'''
def linemarkerinfo(marker):
	# linemarker format:  # LINENO FILE FLAG
	# (note  FLAG  is not mandatory)
	#
	#print "MARKER: '%s'" % marker

	line = marker

	# 1st field: line number
	line = line[2:]
	marker_lineno = line[:line.find('"')-1]

	if marker_lineno.isdigit(): marker_lineno = int(marker_lineno)
	else: return ('-1', '-1', '-1')

	# 2nd field: source file
	line = line[line.find('"')+1:]
	marker_filename = line[:line.find('"')]

	# 3rd field: flag (optional)
	line = line[line.rfind(' ')+1:]
	if line.isdigit() and int(line) <=4 and int(line) >= 1:	marker_flag = int(line)
	else: marker_flag = -1

	#print " LINENO: '%s'" % marker_lineno
	#print " FILE: '%s'" % marker_filename
	#print " FLAG: '%s'" % marker_flag
	#print "\n\n"

	return (marker_lineno, marker_filename, marker_flag)


''' Timeout management

 See:
   http://stackoverflow.com/questions/1191374/subprocess-with-timeout
   http://stackoverflow.com/questions/4789837/how-to-terminate-a-python-subprocess-launched-with-shell-true

'''
import shlex, signal, subprocess, threading, resource

class Command(object):
	status = None
	output = stderr = ''

	def __init__(self, cmdline):
		self.cmd = cmdline
		self.process = None

	def run(self, timeout=None):
		def target():
			# Thread started
			self.process = subprocess.Popen(self.cmd, shell=True, preexec_fn=os.setsid, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
			self.output, self.stderr = self.process.communicate()
			# Thread finished

		thread = threading.Thread(target=target)

		try:
			thread.start()
			thread.join(timeout)

			if thread.is_alive():
				# Terminating process
				###
				os.killpg(self.process.pid,signal.SIGTERM)
				os.killpg(self.process.pid,signal.SIGKILL)
				self.process.kill()
				self.process.terminate()
				thread.join()
		except KeyboardInterrupt:
			os.killpg(self.process.pid,signal.SIGTERM)
			os.killpg(self.process.pid,signal.SIGKILL)
			self.process.kill()
			self.process.terminate()

		memsize = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss

		#return self.output.decode(), self.stderr.decode(), self.process.returncode, memsize
		return self.output, self.stderr, self.process.returncode, memsize





class CommandPid(object):
	pid = None
	status = None
	output = ''
	stderr = ''

	def __init__(self,cmdline,memlimit=0):   ## TODO: implement memory limit
		self.cmd = cmdline
		self.process = None

	def kill(self):
		self.process.kill()

	def spawn(self):
		try:
			self.process = subprocess.Popen(self.cmd,shell=True,preexec_fn=os.setsid,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
			#self.process = subprocess.Popen(self.cmd,shell=True,preexec_fn=limit_virtual_memory,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
			self.pid = self.process.pid
			return int(self.process.pid)
		except e:
			traceback.print_exc()

	def wait(self,timeout=0):
		if timeout != 0: timer = threading.Timer(timeout, self.kill)

		try:
			if timeout != 0: timer.start()
			self.output,self.stderr = self.process.communicate()
			#self.output = str(self.output)
			#self.stderr = str(self.stderr)
		except KeyboardInterrupt:
			#self.process.kill()
			os.killpg(os.getpgid(self.pid),signal.SIGTERM)  # Send the signal to all the process groups
		finally:
			if timeout != 0: timer.cancel()

		memsize = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss

		#return self.output.decode(), self.stderr.decode(), self.process.returncode,tr memsize
		return self.output,self.stderr,self.process.returncode,memsize


''' Short hash for quick file version comparison
'''
def shortfilehash(file):
	if fileExists(file):
		return hashlib.md5(open(file, 'rb').read()).hexdigest()[0:4].upper()
	else:
		return '0000'

'''
'''
def shorthashstring(file):
	return hashlib.md5(string).hexdigest()[0:4].upper()


''' Append a prefix to a filepath. '''
def filepathprefix(path,prefix):
	if '/' not in path: return prefix+path
	else: return rreplace(path, '/', '/'+prefix, 1)


''' Reverse replace
'''
def rreplace(s, old, new, occurrence):
	li = s.rsplit(old, occurrence)
	return new.join(li)


''' Checks whether or not the given file exists
'''
def fileExists(filename):
	return True if os.path.isfile(filename) else False


''' Loads into an array of rows the content of a file, then returns it.
'''
def printFileRows(filename):
	rows = ''

	myfile = open(filename)
	lines = list(myfile)

	for line in lines:
		rows += line

	return rows


''' Loads in a string the content of a file, then returns it.
'''
def printFile(filename):
	if not os.path.isfile(filename):
		#print("ERROR: printfile(%s): file does not exist.\n" % filename)
		return

	in_file = open(filename,"r")
	text = in_file.read()
	in_file.close()

	return text


''' Write to a file the contents of a string.
'''
def saveFile(filename,string_or_bytes,binary):
	if binary:
		outfile = open(filename,"wb")
		outfile.write(string_or_bytes)

	if not binary:
		outfile = open(filename,"w")
		outfile.write(string_or_bytes)

	outfile.close()


'''
'''
def linesContain(string_lines, string):
	for line in string_lines:
		if string in line: return True

	return False


''' Return the number of lines (or of '\n's +1) in the given file.
'''
def fileLength(filename):
	with open(filename) as f:
		for i, l in enumerate(f): pass

	return i + 1


''' Check whether a file starts with 'string'
'''
def fileStartsWith(filename, string):
	if os.path.isfile(filename):
		myfile = open(filename)
		lines = list(myfile)

		if lines[0].startswith(string): return True
		else: return False

	else: return False

	return False


''' Check whether a file contains at least one occurrence of 'string' in any of its lines
'''
def fileContains(filename, string):
	if os.path.isfile(filename):
		myfile = open(filename)
		lines = list(myfile)

		for line in lines:
			if string in line: return True
	else: return False

	return False


def getTerminalSize():
	rows, columns = os.popen('stty size', 'r').read().split()
	return (int(rows), int(columns))


''' Convert string to number '''
def string_to_number(s):
	try:
		return int(s)
	except ValueError:
		try:
			return float(s)
		except ValueError:
			raise ValueError('argument is not a string of number')


def indent(s,char='|',space='  '):
	t = ''
	for l in s.splitlines(): t += '%s%s%s'%(space,char,l)+'\n'
	return t


def listfiles(path='./',filter='*'):
	return [y for x in os.walk(path) for y in glob.glob(os.path.join(x[0], filter))]


def validatedate(date,pattern='%Y-%m-%d'):
	try:
		datetime.datetime.strptime(date,pattern)
		return date
	except ValueError: return '          '


def indent(s,char='|'):
	t = ''
	for l in s.splitlines(): t += '   %s%s'%(char,l)+'\n'
	return t





