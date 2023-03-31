#!/usr/bin/env python

"""
"""
from gi.repository import GLib as gobject
import platform
import logging
import sys
import os
import _thread as thread
import minimalmodbus

# our own packages

sys.path.insert(1, os.path.join(os.path.dirname(__file__), "/opt/victronenergy/dbus-systemcalc-py/ext/velib_python",),)
from vedbus import VeDbusService

path_UpdateIndex = '/UpdateIndex'

class s5_inverter:
  def __init__(self, port='/dev/ttyUSB0', address=1):
    self._dbusservice = []
    self.bus = minimalmodbus.Instrument(port, address)
    self.bus.serial.baudrate = 9600
    self.bus.serial.timeout = 0.1

    self.registers = {
      # name        : nr , format, factor, unit
      "Active Power": [3004, 'U32', 1, 'W'],
      "Energy Today": [3015, 'U16', 1, 'kWh'],
      "Energy Total": [3008, 'U32', 1, 'kWh'],
      "A phase Voltage": [3033, 'U16', 1, 'V'],
      "B phase Voltage": [3034, 'U16', 1, 'V'],
      "C phase Voltage": [3035, 'U16', 1, 'V'],
      "A phase Current": [3036, 'U16', 1, 'A'],
      "B phase Current": [3037, 'U16', 1, 'A'],
      "C phase Current": [3038, 'U16', 1, 'A'],
    }


  def read_registers(self):
    for key, value in self.registers.items():
        factor = value[2]
        if value[1] == 'U32':
          value.append( self.bus.read_long(value[0],4) * factor)
        else:
          value.append(self.bus.read_register(value[0],1,4) * factor)
        print(f"{key}: {value[-1]} {value[-2]}")
    return self.registers


  def read_status(self):
    status = int(self.bus.read_register(3043, 0, 4))
    print(f'Inverter Status: {status:04X}') # 0 waiting, 3 generating
    return status


  #not working, second half seems wrong
  def read_serial(self):
    def swap(b):
      return (b&0xf)<<16 | (b&0xf0)<<8 | (b>>8)&0xf0 | (b>>16)&0xf
    serial = {}
    serial["Inverter SN_1"] = swap(int(self.bus.read_register(3060, 0, 4)))
    serial["Inverter SN_2"] = swap(int(self.bus.read_register(3061, 0, 4)))
    serial["Inverter SN_3"] = swap(int(self.bus.read_register(3062, 0, 4)))
    serial["Inverter SN_4"] = swap(int(self.bus.read_register(3063, 0, 4)))

    return f'Inverter Serial: {serial["Inverter SN_1"]:04X}{serial["Inverter SN_2"]:04X}{serial["Inverter SN_3"]:04X}{serial["Inverter SN_4"]:04X}'


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

    inverter = s5_inverter()

    gobject.timeout_add(300, self._update) # pause 300ms before the next request


  def _update(self):
    try:

      inverter.read_registers()

      self._dbusservice['/Ac/Power']          = inverter.registers["Active Power"][-1]
      self._dbusservice['/Ac/MaxPower']       = 6000
      self._dbusservice['/Ac/Energy/Forward'] = inverter.registers["Energy Total"][-1]
      self._dbusservice['/Ac/L1/Voltage']     = inverter.registers["A phase Voltage"][-1]
      self._dbusservice['/Ac/L2/Voltage']     = inverter.registers["B phase Voltage"][-1]
      self._dbusservice['/Ac/L3/Voltage']     = inverter.registers["C phase Voltage"][-1]
      self._dbusservice['/Ac/L1/Current']     = inverter.registers["A phase Current"][-1]
      self._dbusservice['/Ac/L2/Current']     = inverter.registers["B phase Current"][-1]
      self._dbusservice['/Ac/L3/Current']     = inverter.registers["C phase Current"][-1]
      self._dbusservice['/Ac/L1/Power']       = inverter.registers["A phase Current"][-1]*inverter.registers["A phase Voltage"][-1]
      self._dbusservice['/Ac/L2/Power']       = inverter.registers["B phase Current"][-1]*inverter.registers["B phase Voltage"][-1]
      self._dbusservice['/Ac/L3/Power']       = inverter.registers["C phase Current"][-1]*inverter.registers["C phase Voltage"][-1]
      self._dbusservice['/Ac/L1/Energy/Forward'] = -1
      self._dbusservice['/Ac/L2/Energy/Forward'] = -1
      self._dbusservice['/Ac/L3/Energy/Forward'] = -1
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
