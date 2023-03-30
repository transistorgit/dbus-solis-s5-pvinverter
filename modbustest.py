#!/usr/bin/env python3

"""
"""
import logging
import sys
import os
import minimalmodbus


path_UpdateIndex = '/UpdateIndex'

class inverter:
  def __init__(self):
    self._dbusservice = []
    self.bus = minimalmodbus.Instrument('/dev/ttyUSB0', slaveaddress=1)
    self.bus.serial.baudrate = 9600
    self.bus.serial.timeout = 0.1

    self.registers = {
      # name        : nr , format, factor, unit
      "Active Power": [3004, 'U32', 1, 'W'],
      "Energy Today": [3015, 'U16', 1, 'kWh'],  #-1?
      "DC Voltage 1": [3021, 'U16', 1, 'V'],
      "DC Current 1": [3022, 'U16', 1, 'A'],
      "DC Voltage 2": [3023, 'U16', 1, 'V'],
      "DC Current 2": [3024, 'U16', 1, 'A'],
      "DC Voltage 3": [3025, 'U16', 1, 'V'],
      "DC Current 3": [3026, 'U16', 1, 'A'],
      "DC Voltage 4": [3027, 'U16', 1, 'V'],
      "DC Current 4": [3028, 'U16', 1, 'A'],
      "A phase Current": [3036, 'U16', 1, 'A'],
      "B phase Current": [3037, 'U16', 1, 'A'],
      "C phase Current": [3038, 'U16', 1, 'A'],
      "Inverter temperature": [3041, 'U16', 1, '°C'],
      "Grid frequency": [3042, 'U16', 0.1, 'Hz'],
      "Inverter Status": [3043, 'U16', 1, '']  #hex code 3=generating
    
    }

  def _read_registers(self):
    for key, value in self.registers.items():
        factor = value[2]
        if value[1] == 'U32':
          value.append( self.bus.read_long(value[0],4) * factor)
        else:
          value.append(self.bus.read_register(value[0],1,4) * factor)
        print(f"{key}: {value[-1]} {value[-2]}")


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


inv = inverter()
inv._read_registers()


if __name__ == "__main__":
  main()
