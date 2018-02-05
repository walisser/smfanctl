#!/usr/bin/python3 -u

#
# Hard drive temp control using PWM feature of supermicro
# motherboard. There are two PWM zones controlled. The min/max/avg
# drive temps for each zone are polled, and the PWM for that
# zone is adjusted to maintain temperature around a
# set maximum value.
#
# The control method is:
# 1) The max temp determines if we need to regulate
# 2) The average temp determines which way to regulate
# 3) Amount of temperature change determines amount of correction
#
# Reasoning:
#
# 1) The max temp is the critical factor. Some drives in a zone
#    will run hotter than others, the hottest drive should determine
#    if we need to make an adjustment or not.
#
# 2) The average temp is a better way to determine if the zone
#    temp is rising or falling. Because the max temp only
#    increments in whole numbers, it can not show small
#    changes in the system that could be corrected.
#
# 3) We should apply the smallest correction possible to
#    reduce the number and size of oscillations, rather than
#    arrive at the set temperature quickly.
#    The theory is that continuous thermal cycling could 
#    do more damage than relatively short excursions beyond
#    the set point.
#


# preqs
#     ipmitool (apt-get install ipmitool)
#     areca command line tool (cli64)
# setup
#     modprobe ipmi_devintf
#     
import subprocess,time

class Zone():
    def __init__(self, zone, startPwm, slope, target):
        self.zone = zone
        self.pwm  = startPwm
        self.slope = slope
        self.target = target
        self.lastTemp = 0
        self.ticks = 0
        self.maxPwm = 100
        self.minPwm = 34 # minimum value accepted by the SMC is 25, fans stop at 34

class Reading():
    def __init__(self):
        self.min = float('inf')
        self.max = float('-inf')
        self.avg = 0
        self.count = 0

#
# Above 45c or below 20c is apparently the
# Danger Zone for long-lived hard drives.
# Some also say 30-40c is the sweet spot.
#
# Humidity is also a factor, so choosing
# to run around 39c to reduce
# relative humidity in the drive
#

# zone for drives connected to areca controller
# motherboard pins FAN[1-4]
# temps polled via areca utility and wrapper areca-hwinfo 
# fans DO NOT seem to respond below 34%
arecaZone = Zone(0, 34, 5, 39)

# zone for drives connected to motherboard
# motherboard pins FANA
# temps polled via hddtemp utility running in daemon mode
onboardZone = Zone(1, 34, 5, 39)

def setPwm(zone, value):
    return subprocess.run(args=['./ipmi-fanctl', '-setpwm', '%d'%zone, '%d'%value])

def readArecaTemps():
    r = Reading()

    result = subprocess.run(args=['./areca-hwinfo'], stdout=subprocess.PIPE)
    lines = result.stdout.decode('utf-8').split('\n')
    
    while len(lines) > 0:
        line = lines.pop()
        if line.find('HDD') == 0: # only lines starting with HDD
            fields = line.split()
            if len(fields) < 5:   # the 5th column is temp
                print('unknown areca format')
                break

            temp = int(fields[4])
            r.max = max(temp, r.max)
            r.min = min(temp, r.min)
            r.avg += temp
            r.count += 1

    if r.count > 0:
        r.avg /= r.count
    else:
        r.avg = 60
        r.min = 60
        r.max = 60
        r.count = 1
        print('areca temps: nothing was read')

    return r

def readSmartTemps():
    
    r = Reading()

    # read output from hddtemp daemon
    result = subprocess.run(args=['nc', 'localhost', '7634'], stdout=subprocess.PIPE)

    fields = result.stdout.decode('utf-8').split('|')
    index = 3
    
    while (index < len(fields)):
        temp = int(fields[index])
        r.max = max(temp, r.max)
        r.min = min(temp, r.min)
        r.avg += temp
        r.count += 1
        index += 5

    if (r.count > 0):
        r.avg /= r.count
    else:
        r.avg = 60
        r.min = 60
        r.max = 60
        r.count = 1
        print('hddtemp: nothing was read')
    
    return r

def controlZone(z,t):
   
    z.ticks += 1
   
    tempChange = 0
    if z.lastTemp > 0:
        tempChange = t.avg - z.lastTemp
    else:
        z.lastTemp = t.avg

    #if tempChange != 0:
    print('zone%d:%d change=%.2f pwm=%d last=%.2f avg=%.2f min=%d max=%d' % 
            (z.zone, z.ticks, tempChange, z.pwm, z.lastTemp, t.avg, t.min, t.max))

    
    newPwm = z.pwm

    absChange = abs(tempChange)

    # if one drive changes by one degree, the average
    # moves by this amount
    minChange = 1.0 / t.count

    # the temp must change by more than minchange to do a correction
    # scale up the correction slightly for bigger swings
    if absChange > minChange*4:
        adj = 3
    elif absChange > minChange*2:
        adj = 2
        
    elif absChange > minChange:
        adj = 1
    else:
        tempChange = 0
        adj = 0

    # the change may be 0 but we are way over/under temp
    if (t.max - z.target) > 5:
       tempChange=1
       adj=1
    elif (t.max - z.target) < -5:
       tempChange=-1
       adj=1

    if   tempChange > 0 and t.max >= z.target:
        z.lastTemp = t.avg
        newPwm += adj
    elif tempChange < 0 and t.max <= z.target:
        z.lastTemp = t.avg
        newPwm -= adj

    # clamp pwm to limits of the controller
    newPwm = max(z.minPwm, min(newPwm, z.maxPwm))
    
    if newPwm != z.pwm:
        result = setPwm(z.zone, newPwm)
        if result.returncode == 0:
            print('zone%d: pwm %d => %d' % (z.zone, z.pwm, newPwm))
            z.pwm = newPwm
        else:
            print('zone%d: change rpm failed!' % z.zone)

# set initial pwm
setPwm(arecaZone.zone, arecaZone.pwm)
setPwm(onboardZone.zone, onboardZone.pwm)

while True:
    time.sleep(15)
    controlZone(arecaZone, readArecaTemps())
    controlZone(onboardZone, readSmartTemps())

exit(0)
