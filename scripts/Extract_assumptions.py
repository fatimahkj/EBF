#!/usr/bin/env python3

import os.path  # To check if file exists
import xml.etree.ElementTree as ET  # To parse XML
import os
import argparse
import shlex
import subprocess
import time
import sys
#import resource
import re

# Start time for this script
start_time = time.time()
property_file_content = ""

__graphml_base__ = '{http://graphml.graphdrawing.org/xmlns}'
__graph_tag__ = __graphml_base__ + 'graph'
__edge_tag__ = __graphml_base__ + 'edge'
__data_tag__ = __graphml_base__ + 'data'
__testSuiteDir__ = "test-suite/"

class AssumptionHolder(object):
    """Class to hold line number and assumption from ESBMC Witness."""

    def __init__(self, line, assumption, threadid):
        """
        Default constructor.

        Parameters
        ----------
        line : unsigned
            Line Number from the source file
        assumption : str
            Assumption string from ESBMC.
        """
        assert(line >= 0)
        assert(len(assumption) > 0)
        self.line = line
        self.assumption = assumption
        self.threadid = threadid

    def debugInfo(self):
        """Print info about the object"""
        print("AssumptionInfo: LINE: {0}, ASSUMPTION: {1}, THREADID: {2}".format(
            self.line, self.assumption, self.threadid))


class AssumptionParser(object):
    """Class to parse a witness file generated from ESBMC and create a Set of AssumptionHolder."""

    def __init__(self, witness):
        """
        Default constructor.

        Parameters
        ----------

        witness : str
            Path to witness file (absolute/relative)
        """
        assert(os.path.isfile(witness))
        self.__xml__ = None
        self.assumptions = list()
        self.__witness__ = witness

    def __openwitness__(self):
        """Parse XML file using ET"""
        self.__xml__ = ET.parse(self.__witness__).getroot()

    def parse(self):
        """ Iterates over all elements of GraphML and extracts all Assumptions """
        if self.__xml__ is None:
            self.__openwitness__()
        graph = self.__xml__.find(
            __graph_tag__)
        for node in graph:
            if(node.tag == __edge_tag__):
                startLine = 0
                assumption = ""
                threadid = 0
                for data in node:
                    if data.attrib['key'] == 'startline':
                        startLine = int(data.text)
                    elif data.attrib['key'] == 'assumption':
                        assumption = data.text
                    elif data.attrib['key'] == 'threadid':
                        threadid = data.text
                if assumption != "":
                    self.assumptions.append(AssumptionHolder(
                        startLine, assumption, threadid))
                    #to have a witness without any assumbtion values uncomment the following lines
                #else:
                 #   self.assumptions.append(AssumptionHolder(
                  #      startLine, '0;', threadid))


    def debugInfo(self):
        """Print current info about the object"""
        print("XML: {0}".format(self.__witness__))
        print("ET: {0}".format(self.__xml__))
        for assumption in self.assumptions:
            assumption.debugInfo()


class MetadataParser(object):
    """Class to parse a witness file generated from ESBMC and extract all metadata from it."""

    def __init__(self, witness):
        """
        Default constructor.

        Parameters
        ----------

        witness : str
            Path to witness file (absolute/relative)
        """
        assert(os.path.isfile(witness))
        self.__xml__ = None
        self.metadata = {}
        self.__witness__ = witness

    def __openwitness__(self):
        """Parse XML file using ET"""
        self.__xml__ = ET.parse(self.__witness__).getroot()

    def parse(self):
        """ Iterates over all elements of GraphML and extracts all Metadata """
        if self.__xml__ is None:
            self.__openwitness__()
        graph = self.__xml__.find(
            __graph_tag__)
        for node in graph:
            if(node.tag == __data_tag__):
                self.metadata[node.attrib['key']] = node.text


def __getNonDetAssumptions__(witness):
    assumptionParser = AssumptionParser(witness)
    assumptionParser.parse()
    assumptions = assumptionParser.assumptions
    return assumptions
