#!/usr/bin/python
#****************************************/
#	Script:		runPart.py	
#	Author:		Hamid Mushtaq  			
#****************************************/
from xml.dom import minidom
import sys
import os
import time
import subprocess
import math
import glob

USE_YARN_CLIENT_FOR_HADOOP = False

if len(sys.argv) < 3:
	print("Not enough arguments!")
	print("Example of usage: ./runPart.py config.xml 2")
	sys.exit(1)

#exeName = "target/scala-2.11/dnaseqanalyzer_2.11-1.0.jar"
exeName = "dnaseqanalyzer_2.11-1.0.jar"
logFile = "time.txt"
configFilePath = sys.argv[1]
partNumber = sys.argv[2]

if not os.path.isfile(configFilePath):
	print("Config file " + configFilePath + " does not exist!")
	sys.exit(1)

doc = minidom.parse(configFilePath)
mode = doc.getElementsByTagName("mode")[0].firstChild.data
refPath = doc.getElementsByTagName("refPath")[0].firstChild.data
inputFolder = doc.getElementsByTagName("inputFolder")[0].firstChild.data
outputFolder = doc.getElementsByTagName("outputFolder")[0].firstChild.data
tmpFolder = doc.getElementsByTagName("tmpFolder")[0].firstChild.data
# Parameters for this part
configPart = "3" if (int(partNumber) > 3) else partNumber
numInstances = doc.getElementsByTagName("numInstances" + configPart)[0].firstChild.data
numTasks = doc.getElementsByTagName("numTasks" + configPart)[0].firstChild.data
numRegionsForLB = doc.getElementsByTagName("numRegionsForLB")[0].firstChild
part2Iters = "1" if (numRegionsForLB == None) else numRegionsForLB.data
exe_mem = doc.getElementsByTagName("execMemGB" + configPart)[0].firstChild.data + "g"
driver_mem = doc.getElementsByTagName("driverMemGB" + configPart)[0].firstChild.data + "g"

print "mode = |" + mode + "|"

def getNumOfHadoopChunks():
	cat = subprocess.Popen(["hadoop", "fs", "-ls", inputFolder], stdout=subprocess.PIPE)
	count = 0.0
	for line in cat.stdout:
		if inputFolder in line:
			count = count + 1.0
	return count
	
def getNumOfLocalChunks():
	files = glob.glob(inputFolder + "/*.gz")
	return float(len(files))

def executeHadoop(part, ni, em, extra_param):	
	dictHDFSPath = refPath.replace(".fasta", ".dict")
	dictPath = './' + dictHDFSPath[dictHDFSPath.rfind('/') + 1:]
	
	if USE_YARN_CLIENT_FOR_HADOOP:
		os.system('cp ' + configFilePath + ' ./')
		if not os.path.exists(tmpFolder):
			os.makedirs(tmpFolder)
	
	diff_str = "yarn-client" if USE_YARN_CLIENT_FOR_HADOOP else ("yarn-cluster --files " + configFilePath + "," + dictPath)
	
	cmdStr = "$SPARK_HOME/bin/spark-submit " + \
	"--jars lib/htsjdk-1.143.jar " + \
	"--class \"DNASeqAnalyzer\" --master " + diff_str + " " + \
	"--driver-memory " + driver_mem + " --executor-memory " + em + " " + \
	"--num-executors " + ni + " --executor-cores " + numTasks + " " + \
	exeName + " " + os.path.basename(configFilePath) + " " + str(part) + extra_param
	
	print cmdStr
	addToLog("[" + time.ctime() + "] " + cmdStr)
	os.system(cmdStr)
	
	if USE_YARN_CLIENT_FOR_HADOOP:
		os.remove('./' + configFilePath[configFilePath.rfind('/') + 1:])
	
def executeLocal(part, extra_param):
	if not os.path.exists(tmpFolder):
		os.makedirs(tmpFolder)
			
	cmdStr = "$SPARK_HOME/bin/spark-submit " + \
	"--jars lib/htsjdk-1.143.jar " + \
	"--class \"DNASeqAnalyzer\" --master local[*] --driver-memory " + driver_mem + " " + exeName + " " + \
	configFilePath + " " + str(part) + extra_param
	
	print cmdStr
	addToLog("[" + time.ctime() + "] " + cmdStr)   
	os.system(cmdStr)
	
def addToLog(s):
	f = open(logFile,'a+')
	f.write(s + "\n")
	f.close() 

def runHadoopMode(part):
	if part == 1:
		addToLog("########################################\n[" + time.ctime() + "] Part1 started.")
		dictHDFSPath = refPath.replace(".fasta", ".dict")
		dictPath = './' + dictHDFSPath[dictHDFSPath.rfind('/') + 1:]
		if not os.path.exists(dictPath):
			os.system("hadoop fs -get " + dictHDFSPath)
		os.system("hadoop fs -rm -r -f " + outputFolder)
	
	if (part == 2):
		print ">> Number of iterations for part 2 = " + part2Iters
		for i in range(0, int(part2Iters)):
			executeHadoop(2, numInstances, exe_mem, " " + str(i))
	else:
		executeHadoop(part, numInstances, exe_mem, "")
	addToLog("[" + time.ctime() + "] Part" + str(part) + " completed.")
	
def runLocalMode(part):
	if part == 1:
		addToLog("[" + time.ctime() + "] Part1 started.")
		if os.path.isdir(outputFolder):
			os.system("rm -r -f " + outputFolder)
		os.system("mkdir " + outputFolder)
		
	executeLocal(part, "")
	addToLog("[" + time.ctime() + "] Part" + str(part) + " completed.")
	if part == 3:
		os.system('mv ' + tmpFolder + '/*.vcf ' + outputFolder)
	
start_time = time.time()

if (mode == "local"):
	runLocalMode(int(partNumber))
else:
	runHadoopMode(int(partNumber))
	
time_in_secs = int(time.time() - start_time)
mins = time_in_secs / 60
secs = time_in_secs % 60

print "|| Time taken = " + str(mins) + " mins " + str(secs) + " secs ||"
