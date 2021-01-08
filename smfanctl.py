#!/usr/bin/python3 -u

#
# Hard drive temp control using PWM feature of supermicro ipmi interface
#
# The control method is:
# 1) The hottest drive is set to a fixed temperature (global "setPoint")
# 2) The average of all drives is used to make corrections
#
# Reasoning:
#
# 1) If overheating is the problem, the hottest drive in the array
#    should be what to worry about. It is not likely that a drive
#    would be too cold in an air-cooled (non-condensing) situation.
#
# 2) The average temp is a better way to determine if the zone
#    temp is rising or falling. Because the max temp only
#    increments in whole numbers, it cannot show small
#    changes in the system that could be corrected.
#
# 3) We should apply the smallest correction possible to
#    reduce the number and size of oscillations, rather than
#    arrive at the set temperature quickly.
#    The theory is that continuous thermal cycling could
#    do more damage than relatively short excursions beyond
#    the set point.
#


# requirements
#     ipmitool (apt-get install ipmitool)
#     areca command line tool (cli64, via areca support page)
#     hddtemp running as daemon (apt-get install hddtemp) for ICH/PCH drives
# setup
#     modprobe ipmi_devintf
#

import subprocess,time


# defines independently cooled zone which has
# its own temperature reading and fan control
class Zone():
    def __init__(self, zone, startPwm):
        global setPoint
        self.zone = zone
        self.pwm  = startPwm
        self.target = setPoint
        self.lastTemp = 0 # temp before last pwm change
        self.lastAvg  = 0 # last polled temp
        self.ticks = 0
        self.maxPwm = 100
        self.minPwm = 34 # minimum value accepted by the SMC is 25, fans stop at 34
        self.rising = 0  # number of "rising" readings since last pwm change
        self.falling = 0 # number of "falling" readings since last pwm change
        self.stable = 0  # number of consecutive stable readings

# defines a single reading (poll) of drive temperatures in a Zone
class Reading():
    def __init__(self):
        self.min = float('inf')
        self.max = float('-inf')
        self.avg = 0    # average temperature
        self.count = 0  # number of drives (reporting) in zone
        self.temps = [] # all readings temps in celsius

def setPwm(zone, value):
    return subprocess.run(args=['./ipmi-fanctl', '-setpwm', '%d'%zone, '%d'%value])

# read list of drives attached to areca controller(s) "cli64 disk info"
def readArecaDiskList():
    print('reading areca disk list...')
    driveIds=[]
    result = subprocess.run(args=['./areca-hwinfo','-disk-info'], stdout=subprocess.PIPE)
    lines = result.stdout.decode('utf-8').split('\n')
    lines.reverse()
    while (len(lines) > 0):
        line = lines.pop()
        if line.startswith('==='):
          break

    while (len(lines) > 0):
        line = lines.pop()
        if line.startswith('==='):
          break

        fields = line.split()
        if len(fields) < 4:
            print('unknown areca format')
            break

        driveName = fields[3]
        if (driveName != 'N.A.'):
            driveId = int(fields[0])
            driveIds.append(driveId)

    return driveIds

# read temps using "cli64 disk smart drv=#" where # is the
# device number (first column in "cli64 disk info" list)
def readArecaSmartTemps(driveIds):
    global setPoint
    r = Reading()
    args=['./areca-hwinfo', '-disk-smart']
    args += list(map(str,driveIds))
    result = subprocess.run(args, stdout=subprocess.PIPE)
    lines = result.stdout.decode('utf-8').split('\n')
    lines.reverse()
    while (len(lines) > 0):
        line = lines.pop()
        if line.startswith('194 Temperature'):
            fields = line.split()
            # this is arecas interpretation of raw value,
            # it is wrong for recent wdc drives
            # temp = int(fields[3])
            # temp could be min/max (packed) or raw value, assuming
            # it is always celsius, the lower byte works in either case
            tMax = int(fields[6]) & 0xff
            temp = tMax

            r.max = max(temp, r.max)
            r.min = min(temp, r.min)
            r.avg += temp
            r.count += 1
            r.temps.append(temp)

    if r.count > 0:
        r.avg /= r.count
    else:
        r.avg = setPoint
        r.min = setPoint
        r.max = setPoint
        r.count = 1
        print('readArecaSmartTemps: nothing read')

    return r

# read temps using  "cli64 hw info", does not work on newer adapters
def readArecaTemps():
    global setPoint
    r = Reading()
    result = subprocess.run(args=['./areca-hwinfo'], stdout=subprocess.PIPE)
    lines = result.stdout.decode('utf-8').split('\n')
    lines.reverse()
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
            r.temps.append(temp)

    if r.count > 0:
        r.avg /= r.count
    else:
        r.avg = setPoint
        r.min = setPoint
        r.max = setPoint
        r.count = 1
        print('readArecaTemps: nothing read')

    return r


# read temps from hddtemp daemon, for ICH/PCH drives
def readHddTemps():
    global setPoint
    r = Reading()
    result = subprocess.run(args=['nc', 'localhost', '7634'], stdout=subprocess.PIPE)
    fields = result.stdout.decode('utf-8').split('|')
    index = 3
    while (index < len(fields)):
        name = fields[index-1]
        if (name.startswith('WDC')):
            if (fields[index] == 'ERR'):
                index += 5
                continue
            temp = int(fields[index])
            r.max = max(temp, r.max)
            r.min = min(temp, r.min)
            r.avg += temp
            r.count += 1
            r.temps.append(temp)
        index += 5

    if (r.count > 0):
        r.avg /= r.count
    else:
        r.avg = setPoint
        r.min = setPoint
        r.max = setPoint
        r.count = 1
        print('readHddTemps: nothing read')

    return r

def controlZone(z,t):

    z.ticks += 1
    tempChange = 0

    # track temp before last pwm change to estimate
    # amount of correction needed
    if z.lastTemp > 0:
        tempChange = t.avg - z.lastTemp
    else:
        z.lastTemp = t.avg

    # the temp is either rising, falling, or stable based
    # on consecutive readings. skip corrections if the temp
    # is moving in the right direction
    if z.lastAvg > 0:
        if t.avg > z.lastAvg:
            z.rising += 1 
            z.falling = 0
            z.stable = 0
        elif t.avg < z.lastAvg:
            z.falling += 1
            z.rising = 0
            z.stable = 0
        else:
            z.stable += 1
            if z.stable > 1:
                z.rising = 0
                z.falling = 0

        z.lastAvg = t.avg
    else:
        z.lastAvg = t.avg

    print('zone%d ticks=%d num=%d change=%.2f rising/falling/stable=%d/%d/%d pwm=%d last=%.2f avg=%.2f min=%d max=%d temps=%s' %
            (z.zone, z.ticks, t.count, tempChange, z.rising, z.falling, z.stable,
                z.pwm, z.lastTemp, t.avg, t.min, t.max, ','.join(list(map(str,t.temps)))))

    newPwm = z.pwm

    # change since last pwm change
    absChange = abs(tempChange)

    # if one drive changes by one degree, the average
    # moves by this amount
    minChange = 1.0 / t.count

    # scale the correction slightly for bigger swings
    if absChange > minChange*4:
        adj = 3
    elif absChange > minChange*2:
        adj = 2
    elif absChange > minChange:
        adj = 1
    else:
        adj = 0

    #
    # we have a correction based on change since the last correction,
    # but we don't necessarily need to apply it
    #
    # if the hottest drive is not at the setpoint, and
    # temp is not moving in the right direction, correct
    #
    # if the temp as at the setPoint, correct by 1 pwm
    #
    if (t.max - z.target) > 0 and z.falling <= 0:
       tempChange=1
       if adj == 0:
           adj = 1
       print('zone%d overtemp, correct %d' % (z.zone, adj))
    elif (t.max - z.target) < 0 and z.rising <= 0:
       tempChange=-1
       if adj == 0:
           adj = 1
       print('zone%d undertemp, correct %d' % (z.zone, adj))
    else:
        # we are on the setpoint, do small adjustment if the average moves
        if z.rising > 0:
            tempChange = 1
            adj = 1
            z.rising = 0
            print('zone%d stabilizing, correct %d' % (z.zone, adj*tempChange))
        elif z.falling > 0:
            tempChange = -1
            adj = 1
            z.falling = 0
            print('zone%d stabilizing, correct %d' % (z.zone, adj*tempChange))
        else:
            tempChange = 0
            adj = 0
            print('zone%d stable' % z.zone)

    # final check
    if tempChange > 0 and t.max >= z.target:
        newPwm += adj
    elif tempChange < 0 and t.max <= z.target:
        newPwm -= adj
    elif tempChange != 0:
       print('zone%d veto pwm change' % z.zone)

    # clamp pwm to limits of the controller
    newPwm = max(z.minPwm, min(newPwm, z.maxPwm))

    if newPwm != z.pwm:
        z.lastTemp = t.avg
        result = setPwm(z.zone, newPwm)
        if result.returncode == 0:
            print('zone%d: pwm %d => %d' % (z.zone, z.pwm, newPwm))
            z.pwm = newPwm
        else:
            print('zone%d: change rpm failed!' % z.zone)

    print('----------')

#
# notable publications on drive temperature
#

#
# google - 2007 - "Failure Trends in a Large Disk Drive Population"
# http://static.googleusercontent.com/media/research.google.com/en//archive/disk_failures.pdf
# tldr: 30-45C is a good range, < 30 sees significant rise in AFR, > 45C minor increase in AFR
#

#
# microsoft/UVa - 2013 - impact of temperature and disk failures
# http://www.cs.virginia.edu/~gurumurthi/papers/acmtos13.pdf
# tldr: AFR increases with temperature, above 5% at only 28C
#

#
# backblaze - 2014 - correlation of temperature and failure
# https://www.backblaze.com/blog/hard-drive-temperature-does-it-matter/
# tldr: no correlation or weak for some models
#


# target temperature of hottest drive
setPoint = 30

# dual-zone configuration
# This motherboard has two controllable zones,
# (CPU and peripheral/PCI). The cpu cooler has been
# set to a fixed rpm using a splitter, making both
# zones available.

# zone 1 for drives connected to areca controller
# motherboard headers FAN[1-4], for two fans set
# to the same rpm. temps polled via areca utility
# and wrapper areca-hwinfo. fans do not turn below
# 34% pwm
arecaZone = Zone(0, 60)

# zone 2 for drives connected to motherboard
# motherboard header FANA for a single fan
# temps polled via hddtemp utility running in daemon mode
onboardZone = Zone(1, 55)

# set initial pwm
setPwm(arecaZone.zone, arecaZone.pwm)
setPwm(onboardZone.zone, onboardZone.pwm)

# areca polling requires the id of each disk to poll
# hddtemp polling returns all connected drives
arecaIds = readArecaDiskList()
print('areca ids='+','.join(list(map(str,arecaIds))))

while True:
    #controlZone(arecaZone, readArecaTemps())
    controlZone(arecaZone, readArecaSmartTemps(arecaIds))
    controlZone(onboardZone, readHddTemps())
    # poll time should be long, smart seems to update every 60s
    # and areca polling is slow
    time.sleep(120)

exit(0)
