from __future__ import division
import os, sys
import numpy as np
import random
import time
import matplotlib
import matplotlib.pyplot as plt

lib_path = os.path.abspath('..\\pypw')
sys.path.append(lib_path)
import pypw

############################################
# From Kundur pg. 607:					   #
# ACE_1 = A_1 \Delta P_{12} + B_1 \Delta f #
############################################

#---------------------------------------------------------------------------
# Model setting
FREQUENCY = 60.0				# Nominal frequency
AREA = [1, 2, 3]
BUS = {1: [3, 5, 14, 18, 20, 30, 32, 33, 34, 37, 41, 44, 50], # Manually partition the system into 3 areas
	   2: [1, 10, 12, 13, 17, 19, 28, 29, 31, 35, 38, 39, 40, 56],
	   3: [15, 16, 21, 24, 27, 47, 48, 53, 54, 55]}
TIELINE = [(3, 40, 1), (12, 18, 1), (32, 29, 1), (29, 41, 1), (12, 27, 1), (13, 55, 1), (39, 47, 1), (24, 44, 1)]
TIELINE_NOMINAL = np.array([20.31944656, 37.58109665, -66.40814209, 42.53021622, 37.71585083, 11.84276867, 68.13191223, -50.39382172])
LOAD = {(12, 1): 22.9, (15, 1): 58.2, (48, 1): 55.8, (5, 1): 14.0, (54, 1): 12.43, (18, 1): 45.0, (44, 1): 59.8, (21, 1): 74.4, (34, 1): 22.743, (14, 1): 22.2, (24, 1): 36.3, (37, 1): 27.0, (30, 1): 23.4, (27, 1): 20.0, (53, 1): 59.5, (20, 1): 15.3, (17, 1): 32.8, (10, 1): 16.8, (56, 1): 14.0, (33, 1): 28.0, (13, 1): 23.0, (3, 1): 12.3, (16, 1): 57.8, (55, 1): 22.65, (19, 1): 18.3}
GEN = [(14, 1), (28, 1), (28, 2), (31, 1), (44, 1), (48, 1), (50, 1), (53, 1), (54, 1)]
GOV_INPUT_SETPOINT = {(14, 1): 0.25, (28, 1): 0.83333337307, (28, 2): 0.83333337307, (31, 1): 0.299679249525, (44, 1): 0.9375, (48, 1): 0.280701756477, (50, 1): 0.447058796883, (53, 1): 0.933333337307, (54, 1): 0.654140233994}
GEN_MECH_INPUT = [10.0, 150.0, 150.0, 74.9198150634766, 150.0, 16.0, 38.0, 140.0, 75.2261276245117]
AGC_GEN = {1: [(50, 1), (14, 1)],
		   2: [(31, 1), (28, 1)],
		   3: [(54, 1), (48, 1)]}

AREA_DEMAND_NOMINAL = {area: sum([LOAD[load] for load in LOAD if load[0] in BUS[area]]) for area in AREA}
FROMTO = [12, 23, 31]
AREA_FROMTO = {12: np.array([1, -1, 1, -1, 0, 0, 0, 0]),
			   23: np.array([0, 0, 0, 0, 1, 1, 1, 0]),
			   31: np.array([0, 0, 0, 0, 0, 0, 0, 1])}
AREA_FROMTO_NOMINAL = {fromto: np.dot(TIELINE_NOMINAL, AREA_FROMTO[fromto]) for fromto in FROMTO}
AREA_EXPORT = {1: AREA_FROMTO[12] - AREA_FROMTO[31],
			   2: AREA_FROMTO[23] - AREA_FROMTO[12],
			   3: AREA_FROMTO[31] - AREA_FROMTO[23]}
AREA_EXPORT_NOMINAL = {area: np.dot(TIELINE_NOMINAL, AREA_EXPORT[area]) for area in AREA}
PW_FILE = "%s\\%s"%(os.getcwd(), "GSO_37Bus.pwb")

#---------------------------------------------------------------------------
# AGC control setting
AGC_TIME_STEP = 4				# AGC time step in seconds
K = 1*1e-4						# AGC gain
A = 12							# ACE tieline gain
B = 100							# ACE frequency gain

#---------------------------------------------------------------------------

def RunAGC(EndTime, LoadVariation, AttackVariation, isPrint=True, isPlot=False, logFile=None):
	Time = np.arange(0, EndTime, AGC_TIME_STEP)
	Ace = {area: [0 for t in Time] for area in AREA}
	Agc = {gen: [0 for t in Time] for area in AREA for gen in AGC_GEN[area]}
	CurrentLoad = dict(LOAD)

	LogAttack = {fromto: [0 for t in Time] for fromto in FROMTO}
	LogDemand = {area: [0 for t in Time] for area in AREA}
	LogFrequency = [0 for t in Time]
	LogTieline = {tieline: [0 for t in Time] for tieline in TIELINE}
	LogExport = {area: [0 for t in Time] for area in AREA}
	LogGenPMech = {gen: [0 for t in Time] for gen in GEN}
	sa.OpenCase(PW_FILE)

	# Set new simulation end time
	ObjectType = "TSCONTINGENCY"
	FieldList = sa.GetFieldList(ObjectType, "PRIMARY") + ["EndTime"]
	Data = sa.GetData(ObjectType, FieldList)
	Data[0][-1] = str(EndTime)
	sa.SetData(ObjectType, FieldList, Data)

	startTime = time.time()

	################################################
    # 1. Create events at time step i			   #
	# 2. Run simulation from time step i to i+1	   #
	# 3. Obtain results at time step i+1		   #
    ################################################

	for i in range(len(Time)-1):
		# Compute AGC control signal, apply to governor setpoint
		for area in AREA:
			for gen in AGC_GEN[area]:
				genID = "GEN %d %d"%(gen[0], gen[1])
				Agc[gen][i] = GOV_INPUT_SETPOINT[gen] - K * AGC_TIME_STEP * sum(Ace[area])
				sa.TSCreateEvent(pypw.TS_DEFAULT_CTG, str(Time[i]), genID, pypw.TS_GOV_SETPOINT_VAL%Agc[gen][i])

		# Random load variation
		if LoadVariation != None:
			for l in LOAD:
				newLoad = LOAD[l] * LoadVariation[l][i]
				changeBy = newLoad - CurrentLoad[l]
				sa.TSCreateEvent(pypw.TS_DEFAULT_CTG, str(Time[i]), "LOAD %d %d"%(l[0], l[1]), pypw.TS_LOAD_CHANGEBY_VAL%changeBy)
				CurrentLoad[l] = newLoad

		# Run TS
		sa.TSRunAndPause(pypw.TS_DEFAULT_CTG, str(Time[i+1]))

		# Get average system frequency
		FieldList = ["GEN %d %d | TSGenW"%(gen[0], gen[1]) for gen in GEN]
		Header, Data = sa.TSGetContingencyResults(pypw.TS_DEFAULT_CTG, FieldList, str(Time[i]), str(Time[i+1]))
		frequency = np.mean(Data[-2][1:]) # Take *second last* value if StartTime/StopTime is used
		dFrequency = frequency - FREQUENCY
		LogFrequency[i+1] = dFrequency

		# Get tieline flow
		FieldList = ["BRANCH %d %d %d | TSACLineFromP"%(tieline[0], tieline[1], tieline[2]) for tieline in TIELINE]
		Header, Data = sa.TSGetContingencyResults(pypw.TS_DEFAULT_CTG, FieldList, str(Time[i]), str(Time[i+1]))
		Tieline = np.array(Data[-2][1:]) # Take *second last* value if StartTime/StopTime is used
		
		if AttackVariation != None:
			Attack = np.array([AttackVariation[tieline][i+1] for tieline in TIELINE])
		else:
			Attack = np.array([0.0 for tieline in TIELINE])

		for fromto in FROMTO:
			LogAttack[fromto][i+1] = np.dot(Attack, AREA_FROMTO[fromto])

		for j,tieline in enumerate(TIELINE):
			LogTieline[tieline][i+1] = (Tieline + Attack - TIELINE_NOMINAL)[j]

		# Calculate area control error
		for area in AREA:
			export = np.dot(Tieline + Attack, AREA_EXPORT[area])
			dExport = export - AREA_EXPORT_NOMINAL[area]
			Ace[area][i+1] = A * dExport + B * dFrequency
			LogExport[area][i+1] = dExport

			# Obtain area demand fluctuation
			FieldList = ["LOAD %d %d | TSLoadP"%(load[0], load[1]) for load in LOAD if load[0] in BUS[area]]
			Header, Data = sa.TSGetContingencyResults(pypw.TS_DEFAULT_CTG, FieldList, str(Time[i]), str(Time[i+1]))
			LogDemand[area][i+1] = sum(Data[-2][1:]) - AREA_DEMAND_NOMINAL[area]

		FieldList = ["GEN %d %d | TSGenPMech"%(gen[0], gen[1]) for gen in GEN]
		Header, Data = sa.TSGetContingencyResults(pypw.TS_DEFAULT_CTG, FieldList, str(Time[i]), str(Time[i+1]))
		for j,gen in enumerate(GEN):
			LogGenPMech[gen][i+1] = Data[-2][j+1] - GEN_MECH_INPUT[j]

		if isPrint:
			print "EndTime = %.1f (Speedup = %.1fx)"%(Time[i+1], Time[i+1] / (time.time() - startTime))

	# Log
	if logFile != None:
		openfile = open(logFile, "w")
		for i in range(len(Time)-1):
			data = [Time[i]]
			data += [LogDemand[area][i] + AREA_DEMAND_NOMINAL[area] for area in AREA]
			data += [LogExport[area][i] + AREA_EXPORT_NOMINAL[area] for area in AREA]
			data += [LogAttack[fromto][i] for fromto in FROMTO]
			data += [LogFrequency[i] + FREQUENCY]

			openfile.write("%s\n"%",".join(map(str, data)))
		openfile.close()

	# Plot
	if isPlot:
		fig = plt.figure()
		fig.add_subplot(511)
		FieldList = ["GEN %d %d | TSGenPMech"%(gen[0], gen[1]) for area in AREA for gen in AGC_GEN[area]]
		Header, Data = sa.TSGetContingencyResults(pypw.TS_DEFAULT_CTG, FieldList, str(0), str(EndTime), IsTranspose=True)
		for i in range(1, len(Data)):
			plt.plot(Data[0][:-1], Data[i][:-1], "-", label=Header[i])
		plt.legend(loc=2); plt.xlim(0, EndTime); plt.grid()

		fig.add_subplot(512)
		for tieline in TIELINE:
			plt.plot(LogTieline[tieline], '-', label="Tieline %s"%str(tieline))
		plt.legend(loc=2, ncol=2); plt.grid()

		fig.add_subplot(513)
		FieldList = ["LOAD %d %d | TSLoadP"%(load[0], load[1]) for load in LOAD]
		Header, Data = sa.TSGetContingencyResults(pypw.TS_DEFAULT_CTG, FieldList, str(0), str(EndTime), IsTranspose=True)
		for i in range(1, len(Data)):
			plt.plot(Data[0][:-1], Data[i][:-1], "-", label=Header[i])
		plt.xlim(0, EndTime); plt.legend(loc=2, ncol=2); plt.grid()

		fig.add_subplot(514)
		for area in AREA:
			plt.plot(Ace[area], "-", label="Ace area %d"%area)
		plt.legend(loc=2); plt.grid()

		fig.add_subplot(515)
		plt.plot(LogFrequency, "-k", label="Frequency")
		plt.legend(loc=2); plt.grid()
	
	sa.CloseCase()
	return LogFrequency

###########################################################################

EndTime = 200
length = int(EndTime / AGC_TIME_STEP)
sa = pypw.SimAuto()
sa.Connect()
LoadVariation = {load:[1 + 0.1 * random.random() if i >= 20 else 1 for i in range(length)] for load in LOAD}
RunAGC(EndTime, LoadVariation, None, isPlot=True, logFile=None)
sa.Disconnect()
plt.show()

# RunAGC(EndTime, LoadVariation, AttackVariation, isPlot=False, logFile="result/test/both_%d.csv"%count)
# AttackVariation = {tieline:[] for tieline in TIELINE}
# openfile = open("result/access_setting_vs_mae/Attack_i.csv")
# for line in openfile:
# 	tmp = line.strip().split(",")
# 	for i,tieline in enumerate(TIELINE):
# 		AttackVariation[tieline].append(float(tmp[i]))
# openfile.close()
# Frequency = RunAGC(EndTime, LoadVariation, AttackVariation, isPlot=True, logFile="result/detection/lower_freq_sim.csv")

