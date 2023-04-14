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
from time import sleep

# our own packages

sys.path.insert(1, os.path.join(os.path.dirname(__file__), "/opt/victronenergy/dbus-systemcalc-py/ext/velib_python",),)
from vedbus import VeDbusService

Version = 1.4

path_UpdateIndex = '/UpdateIndex'

class UnknownDeviceException(Exception):
  '''Exception to report that no Solis S5 Type inverter was found'''

class s5_inverter:
  def __init__(self, port='/dev/ttyUSB0', address=1):
    self._dbusservice = []
    self.bus = minimalmodbus.Instrument(port, address)
    self.bus.serial.baudrate = 9600
    self.bus.serial.timeout = 0.1

    #use serial number production code to detect solis inverters
    ser = self.read_serial()
    if not self.check_production_date(ser):
      raise UnknownDeviceException

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
        for _ in range(3):
          try:
            if value[1] == 'U32':
              value[4]= self.bus.read_long(value[0],4) * factor
            else:
              value[4] = self.bus.read_register(value[0],1,4) * factor
            break
          except minimalmodbus.ModbusException:
            value[4]= 0
            pass # igonore sporadic checksum or noreply errors but raise others

        # print(f"{key}: {value[-1]} {value[-2]}")
    return self.registers


  def read_status(self):
    for _ in range(3):
      try:
        status = int(self.bus.read_register(3043, 0, 4))
        return status
      except minimalmodbus.ModbusException:
        pass # igonore sporadic checksum or noreply errors but raise others
    
    # print(f'Inverter Status: {status:04X}') # 0 waiting, 3 generating
    return 0


  def _to_little_endian(self, b):
    return (b&0xf)<<12 | (b&0xf0)<<4 | (b&0xf00)>>4 | (b&0xf000)>>12


  def read_serial(self):
    for _ in range(6):
      try:
        serial = {}
        serial["Inverter SN_1"] = self._to_little_endian(int(self.bus.read_register(3060, 0, 4)))
        serial["Inverter SN_2"] = self._to_little_endian(int(self.bus.read_register(3061, 0, 4)))
        serial["Inverter SN_3"] = self._to_little_endian(int(self.bus.read_register(3062, 0, 4)))
        serial["Inverter SN_4"] = self._to_little_endian(int(self.bus.read_register(3063, 0, 4)))
        serial_str = f'{serial["Inverter SN_1"]:04X}{serial["Inverter SN_2"]:04X}{serial["Inverter SN_3"]:04X}{serial["Inverter SN_4"]:04X}'
        return serial_str
      except minimalmodbus.ModbusException:
        sleep(1)
        pass
    return ''


  def read_type(self):
    try:
      return f'{self._to_little_endian(int(self.bus.read_register(2999, 0, 4))):04X}'
    except minimalmodbus.ModbusException:
      return ''

    
  def read_dsp_version(self):
    try:
      return f'{self._to_little_endian(int(self.bus.read_register(3000, 0, 4))):04X}'
    except minimalmodbus.ModbusException:
      return ''
    

  def read_lcd_version(self):
    try:
      return f'{self._to_little_endian(int(self.bus.read_register(3001, 0, 4))):04X}'
    except minimalmodbus.ModbusException:
      return ''


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
  def __init__(self, port, servicename, deviceinstance=288, productname='Solis S5 PV Inverter', connection='unknown'):
    try:
      self._dbusservice = VeDbusService(servicename)

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

      self._dbusservice.add_path('/Ac/Power', None, writeable=True, gettextcallback=lambda a, x: "{:.0f}W".format(x), onchangecallback=self._handlechangedvalue)
      self._dbusservice.add_path('/Ac/Current', None, writeable=True, gettextcallback=lambda a, x: "{:.1f}A".format(x), onchangecallback=self._handlechangedvalue)
      self._dbusservice.add_path('/Ac/MaxPower', None, writeable=True, gettextcallback=lambda a, x: "{:.0f}W".format(x), onchangecallback=self._handlechangedvalue)
      self._dbusservice.add_path('/Ac/Energy/Forward', None, writeable=True, gettextcallback=lambda a, x: "{:.0f}kWh".format(x), onchangecallback=self._handlechangedvalue)
      self._dbusservice.add_path('/Ac/L1/Voltage', None, writeable=True, gettextcallback=lambda a, x: "{:.1f}V".format(x), onchangecallback=self._handlechangedvalue)
      self._dbusservice.add_path('/Ac/L2/Voltage', None, writeable=True, gettextcallback=lambda a, x: "{:.1f}V".format(x), onchangecallback=self._handlechangedvalue)
      self._dbusservice.add_path('/Ac/L3/Voltage', None, writeable=True, gettextcallback=lambda a, x: "{:.1f}V".format(x), onchangecallback=self._handlechangedvalue)
      self._dbusservice.add_path('/Ac/L1/Current', None, writeable=True, gettextcallback=lambda a, x: "{:.1f}A".format(x), onchangecallback=self._handlechangedvalue)
      self._dbusservice.add_path('/Ac/L2/Current', None, writeable=True, gettextcallback=lambda a, x: "{:.1f}A".format(x), onchangecallback=self._handlechangedvalue)
      self._dbusservice.add_path('/Ac/L3/Current', None, writeable=True, gettextcallback=lambda a, x: "{:.1f}A".format(x), onchangecallback=self._handlechangedvalue)
      self._dbusservice.add_path('/Ac/L1/Power', None, writeable=True, gettextcallback=lambda a, x: "{:.0f}W".format(x), onchangecallback=self._handlechangedvalue)
      self._dbusservice.add_path('/Ac/L2/Power', None, writeable=True, gettextcallback=lambda a, x: "{:.0f}W".format(x), onchangecallback=self._handlechangedvalue)
      self._dbusservice.add_path('/Ac/L3/Power', None, writeable=True, gettextcallback=lambda a, x: "{:.0f}W".format(x), onchangecallback=self._handlechangedvalue)
      self._dbusservice.add_path('/ErrorCode', 0, writeable=True, onchangecallback=self._handlechangedvalue)
      self._dbusservice.add_path('/StatusCode', 0, writeable=True, onchangecallback=self._handlechangedvalue)
      self._dbusservice.add_path('/Position', 0, writeable=True, onchangecallback=self._handlechangedvalue)
      self._dbusservice.add_path(path_UpdateIndex, 0, writeable=True, onchangecallback=self._handlechangedvalue)

      gobject.timeout_add(300, self._update) # pause 300ms before the next request
    except UnknownDeviceException:
      logging.warning('No Solis Inverter detected, exiting')
      sys.exit(1)
    except Exception as e:
      logging.critical("Fatal error at %s", 'DbusSolisS5Service.__init', exc_info=e)
      sys.exit(2)

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
      self._dbusservice['/ErrorCode']         = 0 # TODO
      self._dbusservice['/StatusCode']        = self.inverter.read_status()
    except Exception as e:
      logging.info("WARNING: Could not read from Solis S5 Inverter", exc_info=sys.exc_info()[0])
      self._dbusservice['/Ac/Power']          = None
      self._dbusservice['/Ac/Current']        = None
      self._dbusservice['/Ac/MaxPower']       = None
      self._dbusservice['/Ac/Energy/Forward'] = None
      self._dbusservice['/Ac/L1/Voltage']     = None
      self._dbusservice['/Ac/L2/Voltage']     = None
      self._dbusservice['/Ac/L3/Voltage']     = None
      self._dbusservice['/Ac/L1/Current']     = None
      self._dbusservice['/Ac/L2/Current']     = None
      self._dbusservice['/Ac/L3/Current']     = None
      self._dbusservice['/Ac/L1/Power']       = None
      self._dbusservice['/Ac/L2/Power']       = None
      self._dbusservice['/Ac/L3/Power']       = None
      self._dbusservice['/ErrorCode']         = None
      self._dbusservice['/StatusCode']        = None

    # increment UpdateIndex - to show that new data is available
    self._dbusservice[path_UpdateIndex] = (self._dbusservice[path_UpdateIndex] + 1) % 255  # increment index
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
    logging.info("Start Solis S5 Inverter modbus service v" + str(Version))

    if len(sys.argv) > 1:
        port = sys.argv[1]
    else:
        logging.error("Error: no port given")
        sys.exit(4)

    from dbus.mainloop.glib import DBusGMainLoop
    # Have a mainloop, so we can send/receive asynchronous calls to and from dbus
    DBusGMainLoop(set_as_default=True)

    portname = port.split('/')[-1]
    portnumber = int(portname[-1]) if portname[-1].isdigit() else 0
    pvac_output = DbusSolisS5Service(
      port = port,
      servicename = 'com.victronenergy.pvinverter.' + portname,
      deviceinstance = 288 + portnumber,
      connection = 'Modbus RTU on ' + port)

    logging.info('Connected to dbus, and switching over to gobject.MainLoop() (= event based)')
    mainloop = gobject.MainLoop()
    mainloop.run()

  except Exception as e:
    logging.critical('Error at %s', 'main', exc_info=e)
    sys.exit(3)

if __name__ == "__main__":
  main()
