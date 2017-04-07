# !/usr/bin/env python
#  This plugin includes example functions that are triggered by events in sip.py

# author: David L Sprague

# Plan is to support flow sensors that are attached to an arduino as well as flow
# sensors attached directly to RPi pins.
# Also will include a "simulated" flow sensor interface to allow testing when the sensor
# hardware isn't available.

# Operation: at the lowest level, the flow sensor generates a series of pulses on an input
# pin of the Arduino or RPi that is related to the flow rate by a forumla given by the
# specs for the flow sensor.  This pulse is used to increment a software counter on
# the Arudino or RPi using an interrupt routine.

# This plugin creates a thread that runs every N seconds (e.g. 5 seconds) that reads
# this counter and determines both the current flow rate (liters or gallons per hour)
# by comparing the current count
# to the last time it was read and using the elapsed time between counter reads.  It also 
# computes the total amount of water flow (in liters or gallons) since the counter
# was reset.

# The flow rates and flow amounts for each line (valve) is stored in a gv.plugin_data['fs']
# dictionary.

# Longer term, this plugin should include a webpage that shows tables/graphs of water usage
# for each line/valve and over various timeframes.

# For example, when a program starts to run, the flow counter will be reset to zero
from blinker import signal
import gv
import time
import thread
import random
import serial

print("flow sensors plugin loaded...")
gv.plugin_data['fs'] = {}
gv.plugin_data['fs']['rates'] = [0]*8

simulated_flow_sensors = True
arduino_usbserial_flow_sensors = False
gpio_flow_sensors = False

gv.plugin_data['fs']['sensor_type'] = 'Seeed 1/2 inch'
gv.plugin_data['fs']['units'] = 'Liters' # 'Liters' or 'Gallons'

# multiply conversion table value by pulses per second to get Liters or Gallons per hour
# to get total amount, divide pulse count by the elapsed time in seconds and then
# multiply by conversion table factor to get Total Liters or Total Gallons during
# the elapsed time period.

#TODO check above description with math!!
conversion_table = {'Seeed 1/2 inch': {'Liters': 60.0/7.5, 'Gallons': 60/7.5/3.78541}} 

def reset_flow_sensors():
    #print "resetting flow sensors"
    gv.plugin_data['fs']['start_time'] = time.time()
    gv.plugin_data['fs']['prev_read_time'] = time.time()
    gv.plugin_data['fs']['prev_read_cntrs'] = [0]*8
    gv.plugin_data['fs']['program_amounts'] = [0]*8
    if simulated_flow_sensors:
        gv.plugin_data['fs']['simulated_counters'] = [0]*8
        return True
    elif arduino_usbserial_flow_sensors:
        serial_ch = serial.Serial('/dev/ttyACM0', 9600)
        gv.plugin_data['fs']['serial_chan'] = serial_ch
        time.sleep(2)
        serial_ch.flushInput()
        serial_ch.flushOutput()
        return True
    elif gpio_flow_sensors:
        pass
        return True
    print("Flow Sensor Type Failed in Read")
    return False

def setup_flow_sensors():
    reset_flow_sensors()
    
setup_flow_sensors()

def read_flow_counters(reset=False):
    if simulated_flow_sensors:
        if reset:
            gv.plugin_data['fs']['simulated_counters'] = [0]*8
        else:
            gv.plugin_data['fs']['simulated_counters'] = [cntr + random.random()*0 + 10 for 
                                                            cntr in gv.plugin_data['fs']['simulated_counters']]
        return gv.plugin_data['fs']['simulated_counters']

    elif arduino_usbserial_flow_sensors:
        serial_ch = gv.plugin_data['fs']['serial_ch']
        serial_ch.write('READ')
        time.sleep(0.01)
        line = serial_ch.readline().rstrip()
        vals = map(int, line.split(','))
        if reset:
            serial_ch.write('RESET')
        return vals

    elif gpio_flow_sensors:
        pass
        return [0]*8
    print("Flow Sensor Type Failed in Read")
    return False

# TODO: add flow sensor gv values for rate and amount units (e.g. 'LpH', 'Liters')
# TODO: and automatically insert the correct units in home HTML

def update_flow_rates():
    sensor_type = gv.plugin_data['fs']['sensor_type']
    units = gv.plugin_data['fs']['units']
    current_time = time.time()
    elapsed_prev_read = current_time-gv.plugin_data['fs']['prev_read_time']
    conv_mult = conversion_table[sensor_type][units]
    curr_cntrs = read_flow_counters()
    prev_cntrs = gv.plugin_data['fs']['prev_read_cntrs']
    gv.plugin_data['fs']['rates'] = [(cntr-prev_cntr)*conv_mult/elapsed_prev_read for
                                         cntr, prev_cntr in zip(curr_cntrs, prev_cntrs)]
    gv.plugin_data['fs']['prev_read_time'] = current_time
    gv.plugin_data['fs']['prev_read_cntrs'] = curr_cntrs

def update_flow_amounts():
    sensor_type = gv.plugin_data['fs']['sensor_type']
    units = gv.plugin_data['fs']['units']
    current_time = time.time()
    elapsed_time = current_time - gv.plugin_data['fs']['start_time']
    #print "e time: " + str(elapsed_time)
    prev_amounts = gv.plugin_data['fs']['program_amounts']
    conv_mult = conversion_table[sensor_type][units]
    new_amounts = [cntr*conv_mult/elapsed_time/60/60 for cntr in read_flow_counters()]
    gv.plugin_data['fs']['program_amounts'] = map(sum, zip(prev_amounts, new_amounts)) 
    #print gv.plugin_data['fs']['program_amounts']

def flow_sensor_loop():
    delta_t = 3.0 # seconds
    while True:
        update_flow_rates()
        update_flow_amounts()
        time.sleep(delta_t)

thread.start_new_thread(flow_sensor_loop, ())

### Stations where sheduled to run ###
# gets triggered when:
#       - A program is run (Scheduled or "run now")
#       - Stations are manually started with RunOnce
def notify_station_scheduled(name, **kw):
    reset_flow_sensors()
    print "Some stations have been scheduled: {}".format(str(gv.rs))
program_started = signal('stations_scheduled')
program_started.connect(notify_station_scheduled)

