### Ubuntu Network indicator
Hi all,

This is an indicator applet to monitor the system network speed and also the network speed per process.
You can also monitor the bandwidth per device (e.g eth0,wlan0, or all of them)
I have tested this on Ubuntu 14.04.

![](http://www.imageupload.co.uk/images/2014/09/20/netspeed-indicator.png)

## DEB file
A .deb file is available [here](deploy/netspeed-indicator_1.0_amd64.deb)

If you install the deb file, you will find the program in /opt/netspeed-indicator
Also it will copy a softlink of run.sh in /usr/bin directory.

##How to run the indicator
You can run the indicator by typing in terminal: netspeed-indicator
OR you can go to /opt/netspeed-indicator and type "python netspeed-indicator2.py"


I'll be very happy if you download it,use it, check the python code and extend it.


Cheers!
