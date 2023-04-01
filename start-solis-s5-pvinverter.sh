#!/bin/bash
#

. /opt/victronenergy/serial-starter/run-service.sh

# app=$(dirname $0)/dbus-solis-s5-pvinverter.py

# start -x -s $tty
app="python /opt/victronenergy/dbus-solis-s5-pvinverter/dbus-solis-s5-pvinverter.py"
args="/dev/$tty"
start $args
