#!/usr/bin/env python3

"""
"""
import logging
import sys
import os
import minimalmodbus


path_UpdateIndex = '/UpdateIndex'

class s5_inverter:
  def __init__(self):
    self._dbusservice = []
    self.bus = minimalmodbus.Instrument('/dev/ttyUSB0', slaveaddress=1)
    self.bus.serial.baudrate = 9600
    self.bus.serial.timeout = 0.1

    '''
       "DC Voltage 1": [3021, 'U16', 1, 'V'],
      "DC Current 1": [3022, 'U16', 1, 'A'],
      "DC Voltage 2": [3023, 'U16', 1, 'V'],
      "DC Current 2": [3024, 'U16', 1, 'A'],
      "DC Voltage 3": [3025, 'U16', 1, 'V'],
      "DC Current 3": [3026, 'U16', 1, 'A'],
      "DC Voltage 4": [3027, 'U16', 1, 'V'],
      "DC Current 4": [3028, 'U16', 1, 'A'],
      "Inverter temperature": [3041, 'U16', 1, '°C'],
      "Grid frequency": [3042, 'U16', 0.1, 'Hz'],
      "Reactive Power": [3055, 'U32', 1, 'Var'],
      "Apparent Power": [3057, 'U32', 1, 'VA'],
      
      '''

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
    print(f'Inverter Status: {status:04X}')
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

    print(f'Inverter Serial: {serial["Inverter SN_1"]:04X}{serial["Inverter SN_2"]:04X}{serial["Inverter SN_3"]:04X}{serial["Inverter SN_4"]:04X}')


def main():
  logging.basicConfig(level=logging.DEBUG) # use .INFO for less logging


inv = s5_inverter()
inv.read_registers()
inv.read_status()
inv.read_serial()


if __name__ == "__main__":
  main()
