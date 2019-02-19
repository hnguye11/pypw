from __future__ import division
import os, sys
import numpy as np
import random
import cPickle as pickle
import matplotlib
import matplotlib.pyplot as plt

lib_path = os.path.abspath('..\\pypw')
sys.path.append(lib_path)
import pypw


PW_FILE = "%s\\%s"%(os.getcwd(), "IEEE-39-bus.pwb")
BUS_PUVOLT = {1:1.05178, 2:1.05987, 3:1.05655, 4:1.05919, 5:1.07359, 6:1.07428, 7:1.06115, 8:1.05858, 9:1.05402, 10:1.06106, 11:1.06429, 12:1.04934, 13:1.0587, 14:1.05614, 15:1.04089, 16:1.04853, 17:1.05174, 18:1.05233, 19:1.05599, 20:0.99422, 21:1.04355, 22:1.05611, 23:1.05132, 24:1.05258, 25:1.06582, 26:1.06229, 27:1.05173, 28:1.05541, 29:1.05357, 30:1.0475, 31:0.982, 32:0.9831, 33:0.9972, 34:1.0123, 35:1.0493, 36:1.0635, 37:1.0278, 38:1.0265, 39:1.03}
BUS_PILOT = sorted([2, 25, 29, 22, 23, 19, 20, 10, 6, 9])

LOAD_PQ = {(1,1):[0,0], (2,1):[0,0], (3,1):[322,2.4], (4,1):[500,184], (5,1):[0,0], (6,1):[0,0], (7,1):[233.8,84], (8,1):[522,176], (9,1):[0,0], (10,1):[0,0], (11,1):[0,0], (12,1):[7.5,88], (13,1):[0,0], (14,1):[0,0], (15,1):[320,153], (16,1):[329.4,32.3], (17,1):[0,0], (18,1):[158,30], (19,1):[0,0], (20,1):[680,103], (21,1):[274,115], (22,1):[0,0], (23,1):[247.5,84.6], (24,1):[308.6,-92.2], (25,1):[224,47.2], (26,1):[139,17], (27,1):[281,75.5], (28,1):[206,27.6], (29,1):[283.5,26.9], (31,1):[9.2,4.6], (39,1):[1104,250]}
GEN_PQ = {(30,1):[250.00,83.21], (31,1):[571.28,363.94], (32,1):[650.00,1.53], (33,1):[632.00,69.67], (34,1):[508.00,148.79], (35,1):[650.00,167.04], (36,1):[560.00,75.45], (37,1):[540.00,-35.35], (38,1):[830.00,-0.47], (39,1):[1000.00,-36.49]}
GEN_VOLTSP = {(30,1):1.0475, (31,1):0.982, (32,1):0.9831, (33,1):0.9972, (34,1):1.0123, (35,1):1.0493, (36,1):1.0635, (37,1):1.0278, (38,1):1.0265, (39,1):1.03}

GEN_ID = sorted(GEN_PQ.keys())
GEN_NO = len(GEN_ID)
LOAD_ID = sorted(LOAD_PQ.keys())
LOAD_NO = len(LOAD_ID)



def rand(lower, upper):
	return lower + (upper - lower) * random.random()
	

def saveObjectBinary(obj, filename):
	with open(filename, "wb") as output:
		pickle.dump(obj, output, pickle.HIGHEST_PROTOCOL)
	print "# " + filename + " saved"


def loadObjectBinary(filename):
	with open(filename, "rb") as input:
		obj = pickle.load(input)
	print "# " + filename + " loaded"
	return obj


def sample_once():
	vgdot = [rand(-0.05,0.05) for i in range(GEN_NO)]
	qdot = [rand(-0.1,0.1) for i in range(LOAD_NO)]

	ObjectType = "GEN"
	FieldList = ["BusNum", "GenID", "GenVoltSet"]
	Data = sa.GetData(ObjectType, FieldList)
	for i, data in enumerate(Data):
		data[-1] = str(GEN_VOLTSP[int(data[0]), int(data[1])] + vgdot[i])
	sa.SetData(ObjectType, FieldList, Data)

	ObjectType = "LOAD"
	FieldList = ["BusNum", "LoadID", "LoadSMW", "LoadSMVR"]
	Data = sa.GetData(ObjectType, FieldList)
	for i,data in enumerate(Data):
		data[-1] = str(LOAD_PQ[int(data[0]),int(data[1])][1] * (1 + qdot[i]))
	sa.SetData(ObjectType, FieldList, Data)

	sa.SolvePowerFlow()

	ObjectType = "BUS"
	FieldList = ["BusNum", "BusPUVolt"]
	Data = sa.GetData(ObjectType, FieldList)
	vldot = [BUS_PUVOLT[int(data[0])] - float(data[1]) for data in Data]

	return vgdot, qdot, vldot


def sample_multiple(size=1000):
	Vgdot = []
	Qdot = []
	Vldot = []
	
	for count in range(size):
		print count
		vgdot, qdot, vldot = sample_once()
		Vgdot.append(vgdot)
		Qdot.append(qdot)
		Vldot.append(vldot)

	saveObjectBinary(Vgdot, "Vgdot.bin")
	saveObjectBinary(Qdot, "Qdot.bin")
	saveObjectBinary(Vldot, "Vldot.bin")


def learn_c(ratio=0.75):
	Vgdot = loadObjectBinary("Vgdot.bin")
	Qdot = loadObjectBinary("Qdot.bin")
	Vldot = loadObjectBinary("Vldot.bin")

	length = len(Vgdot)

	x = [Vgdot[i] + Qdot[i] + [1] for i in range(length)]
	Y = Vldot

	trainsize = int(length * ratio)
	x_train = np.array(x[:trainsize])
	x_test = np.array(x[trainsize:])

	Coeff = []

	for i in range(LOAD_NO):
		y = [Y[j][i] for j in range(len(Y))]
		y_train = np.array(y[:trainsize])
		y_test = y[trainsize:]
		coeff = np.linalg.lstsq(x_train, y_train)[0]
		Coeff.append(coeff)

		y_pred = [sum(coeff * x_test[j]) for j in range(len(x_test))]
		diff = [abs(y_pred[j] - y_test[j]) for j in range(len(y_test))]
		plt.plot(sorted(diff), "-x", label=str(i))
	
	saveObjectBinary(Coeff, "Coeff.bin")

	C = [Coeff[i][:GEN_NO] for i in range(LOAD_NO)]
	saveObjectBinary(C, "C.bin")

	plt.legend(loc=2, ncol=5)
	plt.grid(True)

	plt.show()


#######################################
# Follow Electricite de France's SVC: #
# Cp * u = alpha * (vp0 - vp)		  #
# or u = Cp^-1 * alpha * (vp0 - vp)	  #
#######################################
def svc(alpha=0.5, delay=0, iteration=20):
	C = loadObjectBinary("C.bin")
	Cp = np.matrix([C[i] for i in range(LOAD_NO) if LOAD_ID[i][0] in BUS_PILOT])
	Cpi = Cp.I
	vp0 = np.array([BUS_PUVOLT[p] for p in BUS_PILOT]) # pilot bus volt setpoints

	# Initialize data arrays
	vg = np.array([GEN_VOLTSP[gid] for gid in GEN_ID]) # initial gen bus volt setpoints
	VG = [vg] * iteration	 # generator bus voltage / control signals
	q_init = np.array([1.0] * LOAD_NO) # reactive power initial
	q_step = np.array([1.2] * LOAD_NO) # reactive power step change
	Q = [q_init] * 5 + [q_step] * (iteration - 5) # step change / disturbances
	VP = [None] * iteration		  # pilot bus voltages / outputs

	# Start the simulation
	for step in range(iteration):		
		# Step 1. Apply control signals to the current cycle
		Data = sa.GetData("GEN", ["BusNum", "GenID", "GenVoltSet"])
		for i, data in enumerate(Data):
			data[-1] = str(VG[max(0,step-delay)][i])
		sa.SetData("GEN", ["BusNum", "GenID", "GenVoltSet"], Data)
		
		# Step 2. Apply disturbances
		Data = sa.GetData("LOAD", ["BusNum", "LoadID", "LoadSMW", "LoadSMVR"])
		for i,data in enumerate(Data):
			data[-2] = str(Q[step][i] * LOAD_PQ[int(data[0]), int(data[1])][0])
			data[-1] = str(Q[step][i] * LOAD_PQ[int(data[0]), int(data[1])][1])
		sa.SetData("LOAD", ["BusNum", "LoadID", "LoadSMW", "LoadSMVR"], Data)
	
		# Step 3. Solve Power Flow Equation
		sa.SolvePowerFlow()
		
		# Step 4. Calculate outputs
		Data = sa.GetData("BUS", ["BusNum", "BusPUVolt"])
		vp = np.array([float(data[-1]) for data in Data if int(data[0]) in BUS_PILOT])
		VP[step] = vp


		# Step 5. Calculate control signal for the next cycle
		u = np.dot(Cpi, alpha * (vp0 - vp)).A1 # 1-d base array
		u *= -1
		vg = np.array(vg + u)
		if step + 1 < iteration:
			VG[step+1] = vg
		
	return VP

sa = pypw.SimAuto()
sa.Connect()
sa.OpenCase(PW_FILE)
VP = svc(delay=1, iteration=25)
for i in range(len(BUS_PILOT)):
	plt.plot([vp[i] for vp in VP], "-x")
plt.show()
sa.CloseCase()
sa.Disconnect()
