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

# This plugin creates a thread that runs every N seconds (e.g. 3 seconds) and that reads
# this counter and determines both the current flow rate (liters or gallons per hour)
# and the total amount of water flow (in liters or gallons) since the counter was reset.

# The flow rates and flow amounts for each line (valve) is stored in a gv.plugin_data['fs']
# dictionary.

# TODO: put selection of sensor_type and units into SIP Options or on the Plugin's webpage
# TODO: update international language files for the word "Usage" (and any other required words??)
# TODO: add graphs and tables to Plugin's webpage showing monthly usage, etc
# TODO: to support longer term usage statistics we probably need to maintain a separate water usage
#          log, for example one that contains the total by month for each valve.
# TODO: decide whether to support flow_sensors directly connected to Pi or only via Arduino.
# TODO: should we store flow amounts as milliLiters rather than Liters so we can use Ints not Floats?
#           then convert to Liters/Gallons for display?
# TODO: add ability to detect stuck or leaking valves by monitoring flow of from all valves
#         even when no program is running
# TODO: add mechanism to have usage logs sent to user via email, perhaps daily or weekly
# TODO: we might need a Signal to designate that a program/run-once/manual-run has just completed.
#         this could be used to update a usage logfile that we use for charts/tables

import time
import thread
import random
import serial
import gv
from blinker import signal

print("flow sensors plugin loaded...")
gv.plugin_data['fs'] = {}
gv.plugin_data['fs']['rates'] = [0]*8

# *** Set only one of these to True to determine how the flow_sensor counter values are obtained
simulated_flow_sensors = False
arduino_usbserial_flow_sensors = True
gpio_flow_sensors = False

gv.plugin_data['fs']['sensor_type'] = 'Seeed 1/2 inch' # or 'Seed 3/4 inch'
gv.plugin_data['fs']['units'] = 'Liters' # 'Liters' or 'Gallons'
if gv.plugin_data['fs']['units'] == 'Gallons':
    gv.plugin_data['fs']['rate_units'] = 'GpH'
else:
    gv.plugin_data['fs']['rate_units'] = 'LpH'

# multiply conversion table value by pulses per second to get Liters or Gallons per hour
# to get total amount, divide pulse count by the elapsed time in seconds and then
# multiply by conversion table factor to get Total Liters or Total Gallons during
# the elapsed time period.

# TODO: for some valves like the 1/2" and 3/4" brass valves we may need an offset in addition to
#         a multiplier value so the correct would have the form of Counter*Mult + Offset rather
#         than just Counter*Mult.

CONVERSION_MULTIPLIER = {'Seeed 1/2 inch': {'Liters': 60.0/7.5, 'Gallons': 60/7.5/3.78541},
                         'Seeed 3/4 inch': {'Liters': 60.0/5.5, 'Gallons': 60/5.5/3.78541}}

# TODO: add support for other types of RPi serial interfaces with different /dev/names

def reset_flow_sensors():
    """
    Resets parameters used by this plugin for all three flow_sensor types.
    Used at initialization and at the start of each Program/Run-Once 
    """
    #print "resetting flow sensors"
    gv.plugin_data['fs']['start_time'] = time.time()
    gv.plugin_data['fs']['prev_read_time'] = time.time()
    gv.plugin_data['fs']['prev_read_cntrs'] = [0]*8
    gv.plugin_data['fs']['program_amounts'] = [0]*8
    if simulated_flow_sensors:
        gv.plugin_data['fs']['simulated_counters'] = [0]*8
        return True

    elif arduino_usbserial_flow_sensors:
        serial_ch = serial.Serial('/dev/ttyACM0', 9600, timeout=1)
        gv.plugin_data['fs']['serial_chan'] = serial_ch
        time.sleep(0.1)
        serial_ch.write("RS\n")
        serial_ch.flush()
        time.sleep(0.1)
        print("values from Arduino on establishing serial port")
        print(serial_ch.readline())
        return True

    elif gpio_flow_sensors:
        pass
        return True
    print("Flow Sensor Type Failed in Reset")
    return False

def setup_flow_sensors():
    """
    Resets parameters used by this plugin for all three flow_sensor types.
    Used at initialization and at the start of each Program/Run-Once
    """
    reset_flow_sensors()

def read_flow_counters(reset=False):
    """
    Reads counters corresponding to each flow sensor.
    Supports simulated flow sensors (for testing UI), flow sensors connected to an Arduino and
      perhaps flow sensors connected directly to the Pi.
    """
    if simulated_flow_sensors:
        if reset:
            gv.plugin_data['fs']['simulated_counters'] = [0]*8
        else:
            gv.plugin_data['fs']['simulated_counters'] = [cntr + random.random()*40 + 180 for
                                                          cntr in gv.plugin_data['fs']['simulated_counters']]
        return gv.plugin_data['fs']['simulated_counters']

    elif arduino_usbserial_flow_sensors:
        serial_ch = gv.plugin_data['fs']['serial_chan']
        if reset:
            serial_ch.write('RS\n')
        else:
            serial_ch.write('RD\n')
        serial_ch.flush()
        print("Writing to Arduino")
        time.sleep(0.1)
        line = serial_ch.readline().rstrip()
        print("serial input from Arduino is: " + line)
        vals = map(int, line.split(','))
        return vals

    elif gpio_flow_sensors:
        pass
        return [0]*8

    print("Flow Sensor Type Failed in Read")
    return False

def update_flow_values():
    """
    Updates gv values for the current flow rate and accumulated flow amount for each flow sensors.
    """
    sensor_type = gv.plugin_data['fs']['sensor_type']
    units = gv.plugin_data['fs']['units']
    current_time = time.time()

    elapsed_prev_read = current_time - gv.plugin_data['fs']['prev_read_time']  # for flow rate
    # print("elapsed time: " + str(elapsed_time))

    conv_mult = CONVERSION_MULTIPLIER[sensor_type][units]
    prev_cntrs = gv.plugin_data['fs']['prev_read_cntrs']

    curr_cntrs = read_flow_counters()

    gv.plugin_data['fs']['rates'] = [(cntr-prev_cntr)*conv_mult/elapsed_prev_read for \
                                     cntr, prev_cntr in zip(curr_cntrs, prev_cntrs)]
    gv.plugin_data['fs']['program_amounts'] = [cntr*conv_mult/60/60 for cntr in curr_cntrs]

    # print("Rates:" + str(gv.plugin_data['fs']['rates']))
    # print("Amounts:" + str(gv.plugin_data['fs']['program_amounts']))

    gv.plugin_data['fs']['prev_read_time'] = current_time
    gv.plugin_data['fs']['prev_read_cntrs'] = curr_cntrs
   

def flow_sensor_loop():
    """
    This tread will update the flow sensor values every N seconds.
    """
    delta_t = 3.0 # seconds
    while True:
        update_flow_values()
        time.sleep(delta_t)

setup_flow_sensors()
thread.start_new_thread(flow_sensor_loop, ())

### Stations where sheduled to run ###
# gets triggered when:
#       - A program is run (Scheduled or "run now")
#       - Stations are manually started with RunOnce
def notify_station_scheduled(name, **kw):
    """
    Subscribes to the stations_scheduled signal and used to reset the flow_sensor counters
      and flow rate/amount values in the gv.
    """
    reset_flow_sensors()
    print("Some stations have been scheduled: {}".format(str(gv.rs)))
program_started = signal('stations_scheduled')
program_started.connect(notify_station_scheduled)

