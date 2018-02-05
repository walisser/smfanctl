#!/bin/sh
sudo modprobe ipmi_devintf
sudo hddtemp --numeric --daemon /dev/sd[b-f]
while true; do
     cd /home/ghaxt/src/smfanctl
     sudo -u ghaxt ./smfanctl.py >/var/log/smfanctl/smfanctl.log 2>&1
done
