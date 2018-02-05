#!/bin/sh
(
g++ -o ipmi-fanctl ipmi-fanctl.cpp &&
g++ -o areca-hwinfo areca-hwinfo.cpp && 
sudo chown root:root ipmi-fanctl areca-hwinfo && 
sudo chmod 4755 ipmi-fanctl areca-hwinfo
)
