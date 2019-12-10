# smfanctl
Fan speed control for Supermicro motherboards to regulate hdd temperatures in a NAS or RAID enclosure. 
Uses hddtemp and Areca RAID temperature for input.

This is a very simple scheme, with two objectives. 

The first objective is to keep the maximum drive temperature in the population near a safe level,
while the environment temperature and/or drive activity fluctuates.

The second objective is to minimize the number of corrections (i.e. temperature oscillations due to regulation),
rather than stay as close as possible to the setpoint. The reasoning is thermal cycling will be reduced, which
could be a larger issue than temperature.

The fan speed is adjusted if one of the two cases are met:
  1. The maximum drive temperature is more than 10 degrees from the setpoint
  2. The population average temp changed since the last adjustment,
     and the amount of change is greater than if one drive changed by one degree.

The max drive temp will hold +/- 10 degrees from the setpoint. As long as the average
population temperature is stable there will be no correction to get closer to the setpoint.

Since drive temperatures are whole numbers, it is common that a single drive temperature twiddles 
between two values (e.g. 35 and 36 C). These events are ignored to reduce oscillations.

The adjustment applied is always small (usually 1% PWM) to minimize the chance
of overshooting/undershooting the setpoint, at the cost of taking longer to 
stabilize should the drives be far above or below the setpoint at startup.

