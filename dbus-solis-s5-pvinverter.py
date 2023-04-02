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

    #use serial number production code to detect solis inverters
    ser = self.read_serial()
    if not self.check_production_date(ser):
      raise Exception("Unknown Device")

    self.registers = {
      # name        : nr , format, factor, unit
      "Active Power": [3004, 'U32', 1, 'W', 0],
      "Energy Today": [3015, 'U16', 1, 'kWh', 0],
      "Energy Total": [3008, 'U32', 1, 'kWh', 0],
      "A phase Voltage": [3033, 'U16', 1, 'V', 0],
      "B phase Voltage": [3034, 'U16', 1, 'V', 0],
      "C phase Voltage": [3035, 'U16', 1, 'V', 0],
      "A phase Current": [3036, 'U16', 1, 'A', 0],
      "B phase Current": [3037, 'U16', 1, 'A', 0],
      "C phase Current": [3038, 'U16', 1, 'A', 0],
    }


  def read_registers(self):
    for key, value in self.registers.items():
        factor = value[2]
        if value[1] == 'U32':
          try:
            value[4]= self.bus.read_long(value[0],4) * factor
          except minimalmodbus.NoResponseError:
            try:
              value[4]= self.bus.read_long(value[0],4) * factor
            except minimalmodbus.NoResponseError:
              logging.info("Modbus read failed")
              value[4]= 0
        else:
          try:
            value[4] = self.bus.read_register(value[0],1,4) * factor
          except minimalmodbus.NoResponseError:
            try:
              value[4] = self.bus.read_register(value[0],1,4) * factor
            except minimalmodbus.NoResponseError:
              logging.info("Modbus read failed")
              value[4]= 0
        # print(f"{key}: {value[-1]} {value[-2]}")
    return self.registers


  def read_status(self):
    try:
      status = int(self.bus.read_register(3043, 0, 4))
    except minimalmodbus.NoResponseError:
      status = int(self.bus.read_register(3043, 0, 4))
    
    # print(f'Inverter Status: {status:04X}') # 0 waiting, 3 generating
    return status


  def _to_little_endian(self, b):
    return (b&0xf)<<12 | (b&0xf0)<<4 | (b&0xf00)>>4 | (b&0xf000)>>12


  def read_serial(self):
    serial = {}
    serial["Inverter SN_1"] = self._to_little_endian(int(self.bus.read_register(3060, 0, 4)))
    serial["Inverter SN_2"] = self._to_little_endian(int(self.bus.read_register(3061, 0, 4)))
    serial["Inverter SN_3"] = self._to_little_endian(int(self.bus.read_register(3062, 0, 4)))
    serial["Inverter SN_4"] = self._to_little_endian(int(self.bus.read_register(3063, 0, 4)))
    serial_str = f'{serial["Inverter SN_1"]:04X}{serial["Inverter SN_2"]:04X}{serial["Inverter SN_3"]:04X}{serial["Inverter SN_4"]:04X}'
    return serial_str
    

  def read_type(self):
    return f'{self._to_little_endian(int(self.bus.read_register(2999, 0, 4))):04X}'
    
  def read_dsp_version(self):
    return f'{self._to_little_endian(int(self.bus.read_register(3000, 0, 4))):04X}'
    

  def read_lcd_version(self):
    return f'{self._to_little_endian(int(self.bus.read_register(3001, 0, 4))):04X}'


  def check_production_date(self, serial):
    try:
      year = int(serial[7:9])
      month = int(serial[9:10],16)
      day = int(serial[10:12])
      #print(f'{year}/{month}/{day}')
      if year>20 and year<30 and month<=12 and day<=31:
        return True
    except:
      return False


class DbusSolisS5Service:
  def __init__(self, port, servicename, deviceinstance, paths, productname='Solis S5 PV Inverter', connection='Solis S5 PV Inverter service'):
    self._dbusservice = VeDbusService(servicename)
    self._paths = paths

    logging.debug("%s /DeviceInstance = %d" % (servicename, deviceinstance))
    self.inverter = s5_inverter(port)

    # Create the management objects, as specified in the ccgx dbus-api document
    self._dbusservice.add_path('/Mgmt/ProcessName', __file__)
    self._dbusservice.add_path('/Mgmt/ProcessVersion', 'Unkown version, and running on Python ' + platform.python_version())
    self._dbusservice.add_path('/Mgmt/Connection', connection)

    # Create the mandatory objects
    self._dbusservice.add_path('/DeviceInstance', deviceinstance)
    self._dbusservice.add_path('/ProductId', 1234) # pv inverter?
    self._dbusservice.add_path('/ProductName', productname)
    self._dbusservice.add_path('/FirmwareVersion', f'DSP:{self.inverter.read_dsp_version()}_LCD:{self.inverter.read_lcd_version()}')
    self._dbusservice.add_path('/HardwareVersion', self.inverter.read_type())
    self._dbusservice.add_path('/Connected', 1)

    for path, settings in self._paths.items():
      self._dbusservice.add_path(
        path, settings['initial'], writeable=True, onchangecallback=self._handlechangedvalue)

    gobject.timeout_add(300, self._update) # pause 300ms before the next request


  def _update(self):
    try:

      self.inverter.read_registers()

      self._dbusservice['/Ac/Power']          = self.inverter.registers["Active Power"][4]
      self._dbusservice['/Ac/Current']        = self.inverter.registers["A phase Current"][4]+self.inverter.registers["B phase Current"][4]+self.inverter.registers["C phase Current"][4]
      self._dbusservice['/Ac/MaxPower']       = 6000
      self._dbusservice['/Ac/Energy/Forward'] = self.inverter.registers["Energy Total"][4]
      self._dbusservice['/Ac/L1/Voltage']     = self.inverter.registers["A phase Voltage"][4]
      self._dbusservice['/Ac/L2/Voltage']     = self.inverter.registers["B phase Voltage"][4]
      self._dbusservice['/Ac/L3/Voltage']     = self.inverter.registers["C phase Voltage"][4]
      self._dbusservice['/Ac/L1/Current']     = self.inverter.registers["A phase Current"][4]
      self._dbusservice['/Ac/L2/Current']     = self.inverter.registers["B phase Current"][4]
      self._dbusservice['/Ac/L3/Current']     = self.inverter.registers["C phase Current"][4]
      self._dbusservice['/Ac/L1/Power']       = self.inverter.registers["A phase Current"][4]*self.inverter.registers["A phase Voltage"][4]
      self._dbusservice['/Ac/L2/Power']       = self.inverter.registers["B phase Current"][4]*self.inverter.registers["B phase Voltage"][4]
      self._dbusservice['/Ac/L3/Power']       = self.inverter.registers["C phase Current"][4]*self.inverter.registers["C phase Voltage"][4]
      self._dbusservice['/StatusCode']        = self.inverter.read_status()
    except Exception as e:
      logging.info("WARNING: Could not read from Solis S5 Inverter", exc_info=sys.exc_info()[0])
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
  thread.daemon = True # allow the program to quit
  logging.basicConfig(format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                      datefmt='%Y-%m-%d %H:%M:%S',
                      level=logging.INFO,
                      handlers=[
                          logging.FileHandler(
                              "%s/current.log" % (os.path.dirname(os.path.realpath(__file__)))),
                          logging.StreamHandler()
                      ])

  try:
      logging.info("Start Solis S5 Inverter modbus service")

      if len(sys.argv) > 1:
          port = sys.argv[1]
      else:
          logging.error("Error: no port given")
          exit(1)

      from dbus.mainloop.glib import DBusGMainLoop
      # Have a mainloop, so we can send/receive asynchronous calls to and from dbus
      DBusGMainLoop(set_as_default=True)

      pvac_output = DbusSolisS5Service(
        port=port,
        servicename='com.victronenergy.pvinverter.solis_s5',
        deviceinstance=178,
        paths={
          '/Ac/Power': {'initial': 0},
          '/Ac/Current': {'initial': 0},
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
          '/ErrorCode': {'initial': 0},
          '/Position': {'initial': 0},
          '/StatusCode': {'initial': 0},
          path_UpdateIndex: {'initial': 0},
        })

      logging.info('Connected to dbus, and switching over to gobject.MainLoop() (= event based)')
      mainloop = gobject.MainLoop()
      mainloop.run()

  except Exception as e:
      logging.critical('Error at %s', 'main', exc_info=e)
      exit(1)

if __name__ == "__main__":
  main()
