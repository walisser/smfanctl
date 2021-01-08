# smfanctl
Fan speed control for Supermicro motherboards to regulate hdd temperatures in a NAS or RAID enclosure. 
Uses hddtemp daemon and Areca cli64 tool for temperature input, and ipmi extension to set PWM values.

This is a very simple scheme, not a proper PID control loop. 

The fan speed is set as follows:
  1. Initial speed is set to something reasonable
  2. Speed is increased/decreased to hold the temperature of the hottest drive (default 30C)
  3. Speed steps are small, (usually 1% pwm), maybe more if swings are large, and
     no step is made if temperature seems to be moving in the right direction.

Installation Tips
- install and configure hddtemp as a daemon (use hddtemp-initd script as example) (test with "nc localhost 7634")
- install ipmitool and ensure ipmi-devintf is in kernel modules (test with "sudo ipmitool sensor")
- disable SMC fan speed control by setting default fan speed to "Full" in bios or ipmi
- for areca controllers, download cli64 from areca support and copy to this directory

- setup user that will run smfanctl daemon (not root), make dirs owned by this user
- move this directory to /opt/ (so you have /opt/smfanctl), owned by <user>
- create the directory /var/log/opt, owned by <user>
- ./compile.sh
- test suid helper programs (areca-hwinfo, ipmi-fanctl)

- modify smfanctl.py for your setup
  - set min pwm of your fans (default 34)
  - temp setpoint (default 30C)
  - control loop (zones, default pwm etc)

- run smfanctl.py as <user> to test
- make it a daemon (use smfanctl-initd script as example, at least modify <user>)
- 
- 
