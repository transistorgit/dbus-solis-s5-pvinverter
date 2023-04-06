# dbus-solis-s5-pvinverter Service

based on the project https://github.com/victronenergy/dbus-fronius

## Purpose

This service is meant to be run on a raspberry Pi with Venus OS from Victron.

The Python script cyclically reads data from the Solis S5 PV Inverter via Modbus RTU and publishes information on the dbus, using the service name com.victronenergy.pvinverter.solis-s5. The measured values are shown in the Remote Console and can be used by Node Red.

## Interface
The Venus Device needs an USB-RS485 Converter. The line is connected to the 4-Pin Wifi Dongle Port of the Inverter. There is also an 2-Pin Port, but that is for the grid meter only.
* Pin1 5V
* Pin2 Gnd
* Pin3 Data +
* Pin4 Data -

You can measure the 5V/Gnd pins and then use the other two. Use a twisted pair cable like Ethernet or signal cable marked 1x2, 2x2, 3x2 etc. The x2 means that there are 2 wires twisted. This is needed to make it robust agains interference. If you have problems making the connection, at first try to change polarity, at second try to use 120 Ohms termination resistors on one or both ends, especially on long lines. Long can be 20-200m.

## Installation

0. install pip:

   `opkg update`

   `opkg install python3-pip`
   
   then install pip3:

   `pip3 install minimalmodbus`

1. Clone the repo or copy the files to the folder `/data/etc/dbus-solis-s5-pvinverter`

2. Set permissions for py and .sh files if not yet executable:

   `chmod +x /data/etc/dbus-solis-s5-pvinverter/service/run`

   `chmod +x /data/etc/dbus-solis-s5-pvinverter/*.sh`

   `chmod +x /data/etc/dbus-solis-s5-pvinverter/*.py`

3. add service line to `/data/conf/serial-starter.d`:

   `service solis_s5 dbus-solis-s5-pvinverter`

   also append our service short name "solis_s5" to default alias (append it like this):

   `alias default gps:vedirect:sbattery:solis_s5`

4. run `./install.sh`

   The daemon-tools should automatically start this service within seconds.

## Debugging

### Check if its running
You can check the status of the service with svstat:

`svstat /service/dbus-solis-s5-pvinverter.ttyUSB0`

try different USB Ports like ttyUSB1 as the service may use another one

It will show something like this:

`/service/dbus-solis-s5-pvinverter: up (pid 10078) 325 seconds`

If the number of seconds is always 0 or 1 or any other small number, it means that the service crashes and gets restarted all the time.

### Analysing
When you think that the script crashes, start it directly from the command line:

`python /data/etc/dbus-solis-s5-pvinverter/dbus-solis-s5-pvinverter.py`

and see if it throws any error messages.

The logs can be checked here; `/var/log/dbus-solis-s5-pvinverter.ttyUSBx`

### Restart the script

If you want to restart the script, for example after changing it, just run the following command:

`/data/etc/dbus-solis-s5-pvinverter/kill_me.sh`

The daemon-tools will restart the scriptwithin a few seconds.

## Hardware

In my installation at home, I am using the following Hardware:

- Solis S5-GR3P6K 6kW tri phase PV inverter
- Voltwerk VS5 5kW single phase (old one, not yet connected)
- Victron MultiPlus-II 3kW - Battery Inverter (single phase)
- Raspberry Pi 3B+ - For running Venus OS
- 2 DIY LiFePO4 Batteries with Daly Smart BMS, connected with dbus-serialbattery
- currently dbus-AggragateBatteries to gather the Daly data
- SmartShunt

