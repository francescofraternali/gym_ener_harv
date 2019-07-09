import gym
from gym import error, spaces, utils
from gym.utils import seeding
from time import sleep
import datetime
import numpy as np
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

# using PIR = 1 if you want to include the PIR in the simulation
state_trans = 900 # time in seconds
using_PIR = 1
I_PIR_detect = 0.000102; PIR_detect_time = 2.5

# Super-Capacitor values
SC_volt_min = 2.3; SC_volt_max = 5.4; SC_size = 1.5; SC_begin = 4

# Solar Panel values
V_solar_200lux = 1.5; I_solar_200lux = 0.000031;

# Communication values
I_Wake_up_Advertise = 0.00006; Time_Wake_up_Advertise = 11
I_BLE_Comm = 0.00025; Time_BLE_Comm = 4
I_BLE_Sens_1= ((I_Wake_up_Advertise * Time_Wake_up_Advertise) + (I_BLE_Comm * Time_BLE_Comm))/(Time_Wake_up_Advertise + Time_BLE_Comm)
Time_BLE_Sens_1 = Time_Wake_up_Advertise + Time_BLE_Comm
if using_PIR == 1:
	I_sleep = 0.0000055
else:
	I_sleep = 0.0000032

# Normalization values
SC_norm_die = 3; SC_norm_max = 10; SC_norm_min = 0;
light_max = 10; light_min = 0; light_real_max = 2000; light_real_min = 0;

# Normalize light data around those values
Light_List = []
for i in range(0, light_real_max + 200, 200):
	Light_List.append(i)


class gym_en_harv(gym.Env):
	#metadata = {'render.modes': ['human']}
	observation_space = 11 # 11 for light and for voltage and 2 foe week, weekends

	def __init__(self):
		self.SC_Volt = []
		self.SC_Norm = []
		self.Reward = []
		self.PIR_hist = []
		self.Perf = []
		self.Time = []
		self.Light = []
		self.Action = []

		self.done = 0
		self.light_count = 0

		with open("Light_sample.txt", 'r') as f:
			content = f.readlines()
			self.light_input = [x.strip() for x in content]

	def step(self, action):
		line = self.light_input[self.light_count]
		self.light_count += 1
		line = line.split('|')
		self.time = datetime.datetime.strptime(line[0], '%m/%d/%y %H:%M:%S')
		self.PIR = int(line[7])
		light_pure = int(line[8])

		if self.time >= self.end_time:
			self.done = 1
		if self.light_count == len(self.light_input)-1:
			self.light_count = 0
			self.done = 1


		self.light = (((light_pure - light_real_min) * (light_max - light_min)) / (light_real_max - light_real_min)) + light_min

		self.reward, self.perf = reward_func(action, self.SC_volt)
		self.SC_volt, self.SC_norm = energy_calc(self.SC_volt, light_pure, self.perf, self.PIR)

		self.action = action

		self.SC_Volt.append(self.SC_volt)
		self.SC_Norm.append(self.SC_norm)
		self.Reward.append(self.reward)
		self.PIR_hist.append(self.PIR)
		self.Perf.append(self.perf)
		self.Time.append(self.time)
		self.Light.append(self.light)
		self.Action.append(self.action)

		return self.SC_norm, self.reward, self.done

	def reset(self):
		self.SC_Volt = []
		self.SC_Norm = []
		self.Reward = []
		self.PIR_hist = []
		self.Perf = []
		self.Time = []
		self.Light = []
		self.Action = []
		self.light_count == 0

		with open("Light_sample.txt", 'r') as f:
			for line in f:
				line = line.split('|')
				time = datetime.datetime.strptime(line[self.light_count], '%m/%d/%y %H:%M:%S')
				break

		self.end_time = time + datetime.timedelta(0, 24*60*60)
		self.done = 0
		self.PIR = 0
		self.SC_volt = SC_begin
		self.SC_norm = round((((SC_begin - SC_volt_min) * (SC_norm_max - SC_norm_min)) / (SC_volt_max - SC_volt_min)) + SC_norm_min)

		return self.SC_norm

	def render(self, episode, tot_rew):

		plot_hist(self.Time, self.Light, self.Action, self.Reward, self.Perf, self.SC_Volt, self.SC_Norm, self.PIR_hist, episode, tot_rew)


# not finished yet
def reward_func(action, SC_norm):
	perf = action
	reward = action

	if SC_norm <= SC_norm_die:
		reward = -300
	if perf == 0 and SC_norm <= SC_norm_die:
		reward = -100
	'''
    if perf == 0:
        reward = 1
    else:
        reward = 0
    '''
	return reward, perf


def energy_calc(SC_volt, light, perf, PIR):

	if perf == 3:
		effect = 60; effect_PIR = 7
	elif perf == 2:
		effect = 15; effect_PIR = 3
	elif perf == 1:
		effect = 3; effect_PIR = 2
	else:
		effect = 1; effect_PIR = 1

	Energy_Rem = SC_volt * SC_volt * 0.5 * SC_size

	if SC_volt <= SC_volt_min: # Node is death and not consuming energy
		Energy_Prod = state_trans * V_solar_200lux * I_solar_200lux * (light/200)
		Energy_Used = 0
	else: # Node is alive
		if using_PIR == 1:
			effect_PIR = 0

		Energy_Used = ((state_trans - (Time_BLE_Sens_1 * effect)) * SC_volt * I_sleep) + (Time_BLE_Sens_1 * effect * SC_volt * I_BLE_Sens_1) + (PIR * I_PIR_detect * PIR_detect_time * effect_PIR)
		Energy_Prod = state_trans * V_solar_200lux * I_solar_200lux * (light/200)

	# Energy cannot be lower than 0
	Energy_Rem = max(Energy_Rem - Energy_Used + Energy_Prod, 0)

	SC_volt = np.sqrt((2*Energy_Rem)/SC_size)

	# Setting Boundaries for Voltage
	if SC_volt > SC_volt_max:
		SC_volt = SC_volt_max

	if SC_volt < SC_volt_min:
		SC_volt = SC_volt_min

	SC_norm = round((((SC_volt - SC_volt_min) * (SC_norm_max - SC_norm_min)) / (SC_volt_max - SC_volt_min)) + SC_norm_min)

	return SC_volt, SC_norm

def plot_hist(Time, Light, Action, Reward, Perf, SC_Volt, SC_Norm, PIR, episode, tot_rew):
    #Start Plotting
    fig, ax = plt.subplots(1)
    fig.autofmt_xdate()
    plt.plot(Time, Light, 'b', label = 'Light')
    plt.plot(Time, Action, 'y*', label = 'Action',  markersize = 15)
    plt.plot(Time, Reward, 'k+', label = 'Reward')
    #plt.plot(Time, Perf, 'g', label = 'Performance')
    plt.plot(Time, SC_Volt, 'r+', label = 'SC_Voltage')
    plt.plot(Time, SC_Norm, 'm^', label = 'SC_Voltage_Normalized')
    plt.plot(Time, PIR, 'c^', label = 'Occupancy')
    xfmt = mdates.DateFormatter('%m-%d-%y %H:%M:%S')
    ax.xaxis.set_major_formatter(xfmt)
    ax.tick_params(axis='both', which='major', labelsize=10)
    legend = ax.legend(loc='center right', shadow=True)
    plt.legend(loc=9, prop={'size': 10})
    plt.title('Epis: ' + str(episode) + ' tot_rew: ' + str(tot_rew), fontsize=15)
    plt.ylabel('Super Capacitor Voltage[V]', fontsize=15)
    plt.xlabel('Time[h]', fontsize=20)
    ax.grid(True)
    #fig.savefig('Saved_Data/Graph_hist_' + Text + '.png', bbox_inches='tight')
    plt.show()
    #plt.close(fig)
