#!/usr/bin/env python3

# 2021.02.14  ported to python3
# 2019.11.27  calculate the score after a run of test-parallel.py
import sys


def isfloat(s):
	try:
		float(s)
		return True
	except ValueError:
		return False

def isint(s):
	try:
		int(s)
		return True
	except ValueError:
		return False


def wellformed(string):
	# 1058> stop, 1058, FAIL, 24.88,126.31, 7.51,117.72, 0.00,0.00, 0.00,0.00, 0.00,0.00,  FALSE, concurrency_2020/pthread/queue_longest.i.xml, 32.8,126.3, witness-ko-unknown
	splits = string.split(',')

	#return (isint(splits[1].strip()) and
	return (True and
		isfloat(splits[3].strip()) and
		isfloat(splits[4].strip()) and
		#isfloat(splits[5].strip()) and
		#isfloat(splits[6].strip()) and
		#isfloat(splits[7].strip()) and
		#isfloat(splits[8].strip()) and
		#isfloat(splits[9].strip()) and
		#isfloat(splits[10].strip()) and
		#isfloat(splits[11].strip()) and
		#isfloat(splits[12].strip()) and
		isfloat(splits[-2].strip()) and
		isfloat(splits[-3].strip()))


def main(args):
	inconsistent = False
	filename = args[1]  #
	numtolines = {}          # full line for a given num
	#print("%s" % type(lines))
	nums = []           # set of num scanned so far
	#print("%s" % type(nums))

	# load file
	myfile = open(filename)
	lines = list(myfile)

	for line in lines:
		line = line.strip()

		if "stop," in line:
			num = line.split()[0][:-1]  # '1234>'

			# sanity check
			if not wellformed(line):
				print("warning: malformed entry for '%s':" % (num))
				print("     %s\n" % line)

			if num not in nums:
				nums.append(num)
				numtolines[num] = line
			else:
				if line == numtolines[num]:
					#print("duplicate entries for '%s'" % num)
					pass
				else:
					print("inconsistent duplicate entries for '%s':" % num)
					print("     %s" % line)
					print("     %s" % numtolines[num])
					inconsistent = True

	#
	if inconsistent:
		print("error: exiting due to inconsistency")
		return

	# avoid counting duplicates
	memlimit = 0
	timeout = 0
	unknown = 0
	malformed = 0

	correct = 0
	correct_true = 0
	correct_false = 0
	correct_unconfirmed = 0
	incorrect_true = 0
	incorrect_false = 0
	score = 0

	for num in nums:
		line = numtolines[num]

		if wellformed(line):
			splits = line.split(',')
			overalltime = float(splits[-3].strip())    # s
			overallmemory = float(splits[-2].strip())  # MB

			if overallmemory > 14000:
				print("memory limit for '%s':" % num)
				print("     %s\n" % line)
				memlimit += 1
				continue

			if overalltime > 1800:
				print("timeout for '%s':" % num)
				print("     %s\n" % line)
				timeout += 1
				continue
		else:
			malformed += 1

		# correct
		if 'PASS' in line:
			correct += 1

		if 'PASS' in line and 'TRUE' in line:
			correct_true += 1
			score += 2

		if 'PASS' in line and 'FALSE' in line:
			correct_false += 1
			score += 1

		# wrong
		if 'FAIL' in line and 'FALSE' in line and 'witness-ko' in line:
			correct_unconfirmed += 1

		if 'FAIL' in line and 'TRUE' in line:
			incorrect_true += 1
			score -= 32

		if 'FAIL' in line and 'FALSE' in line and 'witness-ko' not in line:
			incorrect_false += 1
			score -= 16

		# unknown
		if 'FAIL' in line and 'UNKNOWN' in line:
			unknown += 1

	#
	remaining = len(numtolines)-timeout-memlimit-unknown-malformed

	'''
	print ("numtolines:%s" % len(numtolines))
	print ("remaining: %s" % remaining)
	print ("timeout:   %s" % timeout)
	print ("memlimit:  %s" % memlimit)
	print ("unknown:   %s" % unknown)
	print ("malformed: %s" % malformed)
	print ("correct:   %s" % correct)
	print ("correct_u: %s" % correct_unconfirmed)
	'''

	print("total.....................%s" %str(len(numtolines)).rjust(4, '.'))
	print("    timeout...............%s %s" % (str(timeout).rjust(4, '.'),'*' if timeout>0 else ''))
	print("   memlimit...............%s" % str(memlimit).rjust(4, '.'))
	print("    unknown...............%s" % str(unknown).rjust(4, '.'))
	print("  malformed...............%s %s" % (str(malformed).rjust(4, '.'),'**' if malformed>0 else ''))
	print("  remaining...............%s\n" % str(remaining).rjust(4, '.'))

	print("correct...................%s" % str(correct).rjust(4, '.'))
	print("     true.................%s" % str(correct_true).rjust(4, '.'))
	print("    false.................%s\n" % str(correct_false).rjust(4, '.'))

	print("correct unconfirmed.......%s" % str(correct_unconfirmed).rjust(4, '.'))
	print("    false.................%s\n" % str(correct_unconfirmed).rjust(4, '.'))

	print("incorrect.................%s" % str(incorrect_true+incorrect_false).rjust(4, '.'))
	print("     true.................%s" % str(incorrect_true).rjust(4, '.'))
	print("    false.................%s\n" % str(incorrect_false).rjust(4, '.'))

	print("score.....................%s\n" % str(score).rjust(4, '.'))

	if timeout>0:
		print("  (*) this can affect the score:")
		print("      timeouts may not time out in the competition and")
		print("      generate a wrong answer instead.\n" )

	if malformed>0:
		print("  (**) this can affect the score,")
		print("       as it can hide wrong answers.\n")

	if not (remaining == correct + correct_unconfirmed):
		# some incorrects or wrong calculation
		print ("  Warning: remaining != correct + correct_unconfirmed")


if __name__ == "__main__":
    main(sys.argv[0:])















