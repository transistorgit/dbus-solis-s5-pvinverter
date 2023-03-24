#!/usr/bin/env python

"""
"""
from gi.repository import GLib as gobject
import platform
import logging
import sys
import os
import _thread as thread

# our own packages

sys.path.insert(1, os.path.join(os.path.dirname(__file__), "/opt/victronenergy/dbus-systemcalc-py/ext/velib_python",),)
from vedbus import VeDbusService

path_UpdateIndex = '/UpdateIndex'

class DbusDummyService:
  def __init__(self, servicename, deviceinstance, paths, productname='Solis S5 PV Inverter', connection='Solis S5 PV Inverter service'):
    self._dbusservice = VeDbusService(servicename)
    self._paths = paths

    logging.debug("%s /DeviceInstance = %d" % (servicename, deviceinstance))

    # Create the management objects, as specified in the ccgx dbus-api document
    self._dbusservice.add_path('/Mgmt/ProcessName', __file__)
    self._dbusservice.add_path('/Mgmt/ProcessVersion', 'Unkown version, and running on Python ' + platform.python_version())
    self._dbusservice.add_path('/Mgmt/Connection', connection)

    # Create the mandatory objects
    self._dbusservice.add_path('/DeviceInstance', deviceinstance)
    self._dbusservice.add_path('/ProductId', 20) #fronius pv inverter
    self._dbusservice.add_path('/ProductName', productname)
    self._dbusservice.add_path('/FirmwareVersion', 0.1)
    self._dbusservice.add_path('/HardwareVersion', 0)
    self._dbusservice.add_path('/Connected', 1)

    for path, settings in self._paths.items():
      self._dbusservice.add_path(
        path, settings['initial'], writeable=True, onchangecallback=self._handlechangedvalue)

    gobject.timeout_add(300, self._update) # pause 300ms before the next request

  def _update(self):
    try:

      inverter_data = {
        'Ac_Power':1234,
        'Ac_MaxPower':6000,
        'Ac_Energy_Forward':0,
        'Voltage_AC_Phase_1':1,
        'Voltage_AC_Phase_2':2,
        'Voltage_AC_Phase_3':3,
        'Current_AC_Phase_1':4,
        'Current_AC_Phase_2':5,
        'Current_AC_Phase_3':6,
        'PowerReal_P_Phase_1':1,
        'PowerReal_P_Phase_2':2,
        'PowerReal_P_Phase_3':3,
        'Ac_L1_Energy_Forward':1,
        'Ac_L2_Energy_Forward':2,
        'Ac_L3_Energy_Forward':3,
        'ErrorCode':0,
        'Position':0,
        'StatusCode':7
      }

      self._dbusservice['/Ac/Power'] = inverter_data['Ac_Power']
      self._dbusservice['/Ac/MaxPower'] = inverter_data['Ac_MaxPower']
      self._dbusservice['/Ac/Energy/Forward'] = inverter_data['Ac_Energy_Forward']
      self._dbusservice['/Ac/L1/Voltage'] = inverter_data['Voltage_AC_Phase_1']
      self._dbusservice['/Ac/L2/Voltage'] = inverter_data['Voltage_AC_Phase_2']
      self._dbusservice['/Ac/L3/Voltage'] = inverter_data['Voltage_AC_Phase_3']
      self._dbusservice['/Ac/L1/Current'] = inverter_data['Current_AC_Phase_1']
      self._dbusservice['/Ac/L2/Current'] = inverter_data['Current_AC_Phase_2']
      self._dbusservice['/Ac/L3/Current'] = inverter_data['Current_AC_Phase_3']
      self._dbusservice['/Ac/L1/Power'] =   inverter_data['PowerReal_P_Phase_1']
      self._dbusservice['/Ac/L2/Power'] =   inverter_data['PowerReal_P_Phase_2']
      self._dbusservice['/Ac/L3/Power'] =   inverter_data['PowerReal_P_Phase_3']
      self._dbusservice['/Ac/L1/Energy/Forward'] = inverter_data['Ac_L1_Energy_Forward']
      self._dbusservice['/Ac/L2/Energy/Forward'] = inverter_data['Ac_L2_Energy_Forward']
      self._dbusservice['/Ac/L3/Energy/Forward'] = inverter_data['Ac_L3_Energy_Forward']
    except:
      logging.info("WARNING: Could not read from Solis S5 Inverter")
      self._dbusservice['/Ac/Power'] = 0  # TODO: any better idea to signal an issue?
    # increment UpdateIndex - to show that new data is available
    index = self._dbusservice[path_UpdateIndex] + 1  # increment index
    if index > 255:   # maximum value of the index
      index = 0       # overflow from 255 to 0
    self._dbusservice[path_UpdateIndex] = index
    return True

  def _handlechangedvalue(self, path, value):
    logging.debug("someone else updated %s to %s" % (path, value))
    return True # accept the change

def main():
  logging.basicConfig(level=logging.DEBUG) # use .INFO for less logging
  thread.daemon = True # allow the program to quit

  from dbus.mainloop.glib import DBusGMainLoop
  # Have a mainloop, so we can send/receive asynchronous calls to and from dbus
  DBusGMainLoop(set_as_default=True)

  pvac_output = DbusDummyService(
    servicename='com.victronenergy.pvinverter.solis_s5',
    deviceinstance=0,
    paths={
      '/Ac/Power': {'initial': 0},
      '/Ac/MaxPower': {'initial': 0},
      '/Ac/Energy/Forward': {'initial': 0},
      '/Ac/L1/Voltage': {'initial': 0},
      '/Ac/L2/Voltage': {'initial': 0},
      '/Ac/L3/Voltage': {'initial': 0},
      '/Ac/L1/Current': {'initial': 0},
      '/Ac/L2/Current': {'initial': 0},
      '/Ac/L3/Current': {'initial': 0},
      '/Ac/L1/Power': {'initial': 0},
      '/Ac/L2/Power': {'initial': 0},
      '/Ac/L3/Power': {'initial': 0},
      '/Ac/L1/Energy/Forward': {'initial': 0},
      '/Ac/L2/Energy/Forward': {'initial': 0},
      '/Ac/L3/Energy/Forward': {'initial': 0},
      '/ErrorCode': {'initial': 0},
      '/Position': {'initial': 0},
      '/StatusCode': {'initial': 7},
      path_UpdateIndex: {'initial': 0},
    })

  logging.info('Connected to dbus, and switching over to gobject.MainLoop() (= event based)')
  mainloop = gobject.MainLoop()
  mainloop.run()

if __name__ == "__main__":
  main()
