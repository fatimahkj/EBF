#!/usr/bin/env python
from __future__ import print_function


'''
def usage(cmd, errormsg, showhelp=True, detail=False):
	if showhelp:
		config = core.utils.extractparamvalue(cseqenv.cmdline, '-l','--load', core.config.defaultchain)
		currentconfig = core.config.defaultchain if config == core.config.defaultchain else config
		currentconfig = core.utils.colors.HIGHLIGHT+currentconfig+core.utils.colors.NO
		defaultorcurrent = 'default' if config == core.config.defaultchain else 'currently'

		print("")
		print("                  viz    ")
		print("")
		print("Usage: ")
		print("")
		print("   %s -h [-l <config>]" % cmd)
		print("   %s -i <input.c> [options]" % cmd)
		print("")
		print(" input options:")
		print("   -i<file>, --input=<file>    input filename")
		print("")

	if errormsg:
		print(errormsg + '\n')
		sys.exit(1)

	sys.exit(0)
'''
import sys
import pygraphviz as pgv
import networkx as nx
#import matplotlib.pyplot as plt

def main():
	cmd = sys.argv

	#G = nx.DiGraph(strict=False,directed=True)
	G = nx.DiGraph(directed=True,strict=False,rankdir="TB", ranksep='1.0 equally', compound='true')
	#filename = '_cs_OOPSLA2019_fib_1_unsafe.c.steps'
	#filename = 'OOPSLA2019_fib_2_unsafe.c.steps'
	#filename = '_cs_OOPSLA2019_fib_2_unsafe.c.log-with-choices'
	#filename = '_cs_OOPSLA2019_fib_2_unsafe.c.log-with-choices_16cores'
	#filename = 'OOPSLA2019_fib_3_unsafe.c.log-with-choices'
	##filename =  '_cs_OOPSLA2019_fib_5_unsafe.c.log-with-choices'

	filename = 'fib_2_unsafe.c.steps'


	dimacs = 'fib_2_unsafe.c.dimacs'
	d = open(dimacs, "r")

	symbol = {}   # program variable for a given propositional variable
	offset = {}   # 

	for l in d.read().splitlines():
		if l.startswith('c '):
			print("l:  (%s)" % l)

			l1 = l[2:]   # key value1 value2 ... 
			l2 = l1[:l1.find(' ')]   # key
			l3 = l1[len(l2)+1:]   # value(s)

			if l2.isdigit():  # we don't want these: c 47 goto_symex::\guard#29
				continue

			if l2 == 'F':   # we don't want there: c F __CPROVER_malloc_is_new_array#1
				continue

			print("l1: (%s)" % l1)
			print("l2: (%s)" % l2)
			print("l3: (%s)" % l3)



			# c __cs_create#return_value!0#2 105 106 107 108 109 110 111 112 113 114 115 116 117 118 119 120 121 122 123 124 125 126 127 128 129 130 131 132 133 134 135 136
			for i,propvar in enumerate(l3.split(' ')):
				if propvar != 'F' and propvar != 'T' and propvar != '':
					#print("converting %s" % propvar)
					propvar = int(propvar)

					#print ("[%s] = %s" % (propvar, l2))
					symbol[propvar] = l2   # which var in the program?
					offset[propvar] = i    # which bit exactly?







	f = open(filename, "r")

	currentnodeatlevel = {}    #
	subgraphbetweenrestarts = {}
	nodesatlevel = {}


	newnode = 'start'
	G.add_node(newnode,penwidth=5)

	currentnodeatlevel[0] = newnode

	nodesatlevel[0] = []
	#nodesatlevel[0].append(newnode)

	subgraphbetweenrestarts[0] = []
	subgraphbetweenrestarts[0].append(newnode)
	

	maxlevel = 0
	backjumps = 0
	restarts = 0

	endnodename = None

	for l in f.read().splitlines():
		if l.startswith('level:'):
			#level:0 choice:1817=1
			l = l.split(' ')

			level = int(l[0][len('level:'):])

			if l[1].startswith('choice:'):
				var = int(l[1][len('choice:'):].split('=')[0])
				value = int(l[1][len('choice:'):].split('=')[1])

				print("level:%s  var:%s  value:%s" % (level,var,value))

				if var not in symbol:
					newnode = '(%s,%s) %s=%s' % (backjumps,level,var,value)
				else:
					var = '%s:%s' % (symbol[var],offset[var])
					newnode = 'OK (%s,%s) %s=%s' % (backjumps,level,var,value)

				G.add_node(newnode,penwidth=5)

				if level>0:
					G.add_edge(currentnodeatlevel[level-1],newnode,arrowhead="none",penwidth=3)  
				else:					
					G.add_edge(currentnodeatlevel[0],newnode,arrowhead="none",penwidth=3)

				if not nodesatlevel.has_key(level):
					nodesatlevel[level] = []
				nodesatlevel[level].append(newnode)


				if not subgraphbetweenrestarts.has_key(backjumps):
					subgraphbetweenrestarts[backjumps] = []
				subgraphbetweenrestarts[backjumps].append(newnode)

				currentnodeatlevel[level] = newnode

				maxlevel = max(level,maxlevel)

				if newnode.endswith('-1=0'): endnodename = newnode

				last = 0

			elif l[1].startswith('backjump:'):
				jumpto = int(l[1][len('backjump:'):])

				print("level:%s  backjump:%s" % (level,jumpto))

				'''
				newnode = '(%s,%s)' % (backjumps,level)

				if not nodesatlevel.has_key(level):
					nodesatlevel[level] = []
				nodesatlevel[level].append(newnode)

				G.add_edge(newnode,currentnodeatlevel[jumpto])  # add edge to jump back
				'''
				if last == 0:
					backjumps += 1
				last = 1

			elif l[1].startswith('restart:'):
				restarts += 1
				print("restart no. %s" % restarts)

				newnode = 'start %s' % restarts
				G.add_node(newnode)

				currentnodeatlevel[0] = newnode

				nodesatlevel[0] = []
				#nodesatlevel[0].append(newnode)

				subgraphbetweenrestarts[0] = []
				subgraphbetweenrestarts[0].append(newnode)
				
				#maxlevel = 0
				#backjumps = 0
				#restarts = 0
			else:
				print("unrecognized entry (%s)" % l)

	#G.draw('file.pdf',prog='circo')  

	#pos = nx.kamada_kawai_layout(G)

	H = nx.nx_agraph.to_agraph(G)
	H.node_attr['shape'] = 'box' #'circle'


	# clusters of choices between restarts in the attempt to draw subtrees left to right
	for i in range(0,backjumps):
		if subgraphbetweenrestarts.has_key(i):
			print("--> adding to cluster %s nodes %s <--" % (i,subgraphbetweenrestarts[i]))
			H.add_subgraph(subgraphbetweenrestarts[i],label='%s' % i)

			''' only the graph structure, no labels for the nodes '''
			'''
			for j in subgraphbetweenrestarts[i]:
				n = H.get_node(j)
				n.attr['label'] = ''
			'''

	startnode = H.get_node('start')
	startnode.attr['fillcolor']='yellow'
 	startnode.attr['style']='filled'
 	startnode.attr['shape']='circle'

 	# add SAT node for satisfiable instances
 	if endnodename:
		endnode = H.get_node(endnodename)
		endnode.attr['fillcolor']='red'
	 	endnode.attr['style']='filled'
		endnode.attr['shape']='circle'
		endnode.attr['label'] = 'SAT'

	# use ranks to keep the nodes at the same level
	for i in range(0,maxlevel):
		print("--> adding to rank %s nodes %s <--" % (i,nodesatlevel[i]))
		H.add_subgraph(nodesatlevel[i],rank='same')

	for n in H.nodes_iter():
		if n.get_name().startswith('OK'):
		 	n.attr['label']=n.get_name()
			n.attr['fillcolor']='orange'
		 	n.attr['style']='filled'


	# backjump nodes
	# (adding them backwards to retain the layout)
	'''
	# example for fib1
	a = H.get_node('(0,3) 1051=1')
	c = H.get_node('(0,0) 1817=1')
	H.add_edge(c,a)
	'''

	#
	H.draw('file.pdf', prog='dot')  #  prog=neato|dot|twopi|circo|fdp|nop.
	H.draw('file.png', prog='dot')  #  prog=neato|dot|twopi|circo|fdp|nop.
	H.write("file.dot")


if __name__ == "__main__":
	main()







