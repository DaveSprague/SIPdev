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
import web  # web.py framework
import gv  # Get access to SIP's settings
from urls import urls  # Get access to ospi's URLs
from ospi import template_render  #  Needed for working with web.py templates
from webpages import ProtectedPage  # Needed for security
import json  # for working with data file
import time
import thread
import random
import serial
from blinker import signal

# Add new URLs to access classes in this plugin.
urls.extend([
    '/flow_sensors-sp', 'plugins.flow_sensors.settings',
    '/flow_sensors-save', 'plugins.flow_sensors.save_settings'
    ])

gv.plugin_menu.append(['Flow Sensors Plugin', '/flow_sensors-sp'])
mySettings = { }
print "defined mySettings"
mySettings = {'method': 'Simulated', 'sensor_type': 'Seeed 1/2 inch','units': 'Gallons' }
print "my settings are: " + str(mySettings)

class settings(ProtectedPage):
    """
    Load an html page for entering plugin settings.
    """
    
    def GET(self):
        global mySettings
        print ("GET method in settings class")
        try:
            with open('./data/flow_sensors.json', 'r') as f:  # Read settings from json file if it exists
                mySettings = json.load(f)
                reset_flow_sensors()
        except IOError:  # If file does not exist return empty value
            print("No flow_sensors.json file")
            print "my settings here are: " + str(mySettings)
        return template_render.flow_sensors(mySettings)  # open settings page

class save_settings(ProtectedPage):
    """
    Save user input to json file.
    Will create or update file when SUBMIT button is clicked
    CheckBoxes only appear in qdict if they are checked.
    """
    # TODO: fix update of mySettings with new settings values in qdict!!!
    def GET(self):
        global mySettings
        qdict = web.input()  # Dictionary of values returned as query string from settings page.
        print "qdict = " + str(qdict)  # for testing
        print "mySettings : " + str(mySettings)
        with open('./data/flow_sensors.json', 'w') as f:  # Edit: change name of json file
             json.dump(qdict, f) # save to file
             print "flow sensor settings file saved"
             print "mySettings : " + str(mySettings)
        raise web.seeother('/')  # Return user to home page.

##################################################
# The following code runs when the plugin is loaded
###################################################

print("flow sensors plugin loaded...")
gv.plugin_data['fs'] = {}
gv.plugin_data['fs']['rates'] = [0]*8

gv.plugin_data['fs']['sensor_type'] = 'Seeed 1/2 inch' # or 'Seed 3/4 inch'
gv.plugin_data['fs']['units'] = 'Gallons' # 'Liters' or 'Gallons'
if gv.plugin_data['fs']['units'] == 'Gallons':
    gv.plugin_data['fs']['rate_units'] = 'GpH'
else:
    gv.plugin_data['fs']['rate_units'] = 'LpH'

# add this plugin's log value to the SIP log
gv.logged_values.append( [_('usage'), lambda : '{:.3f}'.format(gv.plugin_data["fs"]["program_amounts"][gv.lrun[0]]) ])

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
    print "resetting flow sensors"
    print "mySettings : " + str(mySettings)
    gv.plugin_data['fs']['start_time'] = time.time()
    gv.plugin_data['fs']['prev_read_time'] = time.time()
    gv.plugin_data['fs']['prev_read_cntrs'] = [0]*8
    gv.plugin_data['fs']['program_amounts'] = [0]*8

    if mySettings['method'] == 'Simulated':
        gv.plugin_data['fs']['simulated_counters'] = [0]*8
        return True

    elif mySettings['method'] == 'Arduino-Serial':
        serial_ch = serial.Serial('/dev/ttyACM0', 9600, timeout=1)
        gv.plugin_data['fs']['serial_chan'] = serial_ch
        time.sleep(0.1)
        serial_ch.write("RS\n")
        serial_ch.flush()
        time.sleep(0.1)
        line = serial_ch.readline()
        print("values from Arduino on establishing serial port")
        print(line)
        return True

    elif mySettings['method'] == 'RaspberryPi-GPIO':
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
    print "reading flow sensors"
    print "mySettings : " + str(mySettings)
    if mySettings['method'] == 'Simulated':
        if reset:
            gv.plugin_data['fs']['simulated_counters'] = [0]*8
        else:
            gv.plugin_data['fs']['simulated_counters'] = [cntr + random.random()*40 + 180 for
                                                          cntr in gv.plugin_data['fs']['simulated_counters']]
        return gv.plugin_data['fs']['simulated_counters']

    elif mySettings['method'] == 'Arduino-Serial':
        serial_ch = gv.plugin_data['fs']['serial_chan']
        if reset:
            serial_ch.write('RS\n')
        else:
            serial_ch.write('RD\n')
        serial_ch.flush()
        #print("Writing to Arduino")
        time.sleep(0.2)
        line = serial_ch.readline().rstrip()
        #print("serial input from Arduino is: " + line)
        #print("serial input has been printed")
        if line == '':
            return [0]*8
        else:
            vals = map(int, line.split(','))
        return vals

    elif mySettings['method'] == 'RaspberryPi-GPIO':
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
    #print("Some stations have been scheduled: {}".format(str(gv.rs)))
program_started = signal('stations_scheduled')
program_started.connect(notify_station_scheduled)

