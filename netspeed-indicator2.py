#/usr/bin/env python
# -*- coding: utf-8 -*-

#Indicator-Netspeed
#
#Author: Dimitris Misdanitis
#Date: 2014
#Version 0.1
#⇧ 349  B/s  ⇩ 0.0  B/s
#
#▲▼ ↓↑ ✔ ⬆⬇ ⇩⇧
import commands
from gi.repository import GObject,GLib
import gtk
import appindicator
import time
import urllib2
import os, subprocess
import io
import threading
from vsgui.api import *
import stat
gtk.gdk.threads_init()


#Thread to get the Overall Network speed (all interfaces except lo) 
#Updates the indicator text
class NetspeedFetcher(threading.Thread):
	def __init__(self, parent):
		threading.Thread.__init__(self)
		self.parent = parent

	def _fetch_speed(self):
		sn=self.parent.get_interfaces()
		try:
			#get the transmitted and received bytes, wait 1 sec, get the values again and see what changed in a second. Thats the netspeed/sec
			if self.parent.active_interface == "All":
				R1=long(commands.getstatusoutput('ls /sys/class/net/|grep -v lo|xargs -I % cat /sys/class/net/%/statistics/rx_bytes|paste -sd+|bc 2>/dev/null')[1])
				T1=long(commands.getstatusoutput('ls /sys/class/net/|grep -v lo|xargs -I % cat /sys/class/net/%/statistics/tx_bytes|paste -sd+|bc 2>/dev/null')[1])
				time.sleep(1)
				R2=long(commands.getstatusoutput('ls /sys/class/net/|grep -v lo|xargs -I % cat /sys/class/net/%/statistics/rx_bytes|paste -sd+|bc 2>/dev/null')[1])
				T2=long(commands.getstatusoutput('ls /sys/class/net/|grep -v lo|xargs -I % cat /sys/class/net/%/statistics/tx_bytes|paste -sd+|bc 2>/dev/null')[1])
			else:
				R1=long(commands.getstatusoutput('cat /sys/class/net/%s/statistics/rx_bytes 2>/dev/null'%self.parent.active_interface)[1])
				T1=long(commands.getstatusoutput('cat /sys/class/net/%s/statistics/tx_bytes 2>/dev/null'%self.parent.active_interface)[1])
				time.sleep(1)
				R2=long(commands.getstatusoutput('cat /sys/class/net/%s/statistics/rx_bytes 2>/dev/null'%self.parent.active_interface)[1])
				T2=long(commands.getstatusoutput('cat /sys/class/net/%s/statistics/tx_bytes 2>/dev/null'%self.parent.active_interface)[1])
		except ValueError:
			R1=0
			R2=0
			T1=0
			T2=0
		down_bytes=R2-R1
		up_bytes=T2-T1
		downformatted=self.parent.sizeof_fmt(down_bytes) 
		upformatted=self.parent.sizeof_fmt(up_bytes)
		#We can change the arrows, when we are offline. But i disabled it.
		#if self.parent.isOnline==True:
		uparrow="⬆" 
		downarrow="⬇"
		#else:
		#	uparrow="⇧"
	#		downarrow="⇩"
		summ=down_bytes+up_bytes

		#This is to change the icons, based on the speed. summ stores the upload+download in bytes.
		#We can make it t set the limits dynamically, based on your network speed. But this is insignificant.
		if summ <= 2000:
			self.parent.ind.set_icon("zero")
			#print "zero"		
		elif summ>2000 and summ<=51200:      #50KB
			self.parent.ind.set_icon("light")
			#print "light"
		elif summ>51200 and summ<=307200:   #300KB
			self.parent.ind.set_icon("medium")
			#print "medium"
		elif summ>307200 and summ<=819200:    #800
			self.parent.ind.set_icon("high")
			#print "high"
		else:
			self.parent.ind.set_icon("full")
			#print "full"
		return "%s%s  %s%s"%(upformatted,uparrow,downformatted,downarrow)

	#this is the thread. We always loop , get the speed from the above function and set the indicator label.
	def run(self):
		while(self.parent.alive.isSet()):
			data = self._fetch_speed()
			self.parent.ind.set_label(data,'⬆8888 MB/s  ⬇8888 MB/s')
			time.sleep(1)
		


class indicatorNetspeed:
	interfaces = []     #This list stores the interfaces.
	active_interface = 'All'  #Which device is monitored? The default is All (except lo)
	proc_rows = []
	menu_process=[]     #This list stores the 15 gtk menu items i use to display the bandwith per process
	isOnline=True       #We assume that initially we are online.
	bandwidthPerProcess_active=False    #Start monitor bandwith perprocess(nethogs) when the indicator starts
	nethogs_alive=False                #Is nethogs alive? At this point it's not..
	nethogs_process = ""               #Is there any subprocess that reads from the nethogs? At this point there isn't.
	sudo_pass=""                      #Stores the sudo password. We nee this to run the nethogs!

	def __init__(self):
		self.folder=os.path.dirname(os.path.realpath(__file__))    #Get the aplication's folder.
		n=self.get_interfaces()                                    #Get the interfaces (that also fills the interfaces list
		
		#This is our indicator object! (name, icon,type)
		self.ind = appindicator.Indicator ("indicator-netspeed",
									"zero",
									appindicator.CATEGORY_SYSTEM_SERVICES)
		self.ind.set_icon_theme_path("%s/icons"%self.folder)    #Set the icon theme folder!
		self.ind.set_status (appindicator.STATUS_ACTIVE)
		self.ind.set_label("⇧ 0.0  B/s  ⇩ 0.0  B/s",'⬆8888 MB/s  ⬇8888 MB/s') #Initially set the label to ⇧ 0.0  B/s  ⇩ 0.0  B/s
		
		self.build_menu()    #Build the menu
		self.alive = threading.Event()  
		self.alive.set()
		self.fetch = NetspeedFetcher(self)
		self.fetch.start()   # Start fetcher thread
		self.nethogs_thread=threading.Thread(target=self._tail_forever, args=("",))   #set the bandwidth/process monitor thread
		if self.bandwidthPerProcess_active:    #If the functionality is active
			self.nethogs_thread.start()    #Start the thread!

	#this is the method that reads from the nethogs
	#I use my the latest version of nethogs, because it doesn't require to pass the device as parameter.
	#I compiled it to 64bit machine. I'm not sure if this works on an 32bit ubuntu. 
	def _tail_forever(self,args=None):
		#is_nethogs_executable=os.access('nethogs/nethogs', os.X_OK)
		#if is_nethogs_executable == False:
		#	st = os.stat('%s/nethogs/nethogs'%(self.folder))
		#	os.chmod('%s/nethogs/nethogs'%(self.folder), st.st_mode | stat.S_IEXEC) #If nethogs is not executable, make it.
		FNULL =io.open(os.devnull, 'w')     #set an FNULL variable to point to /dev/null
		args1 = ['echo', '%s'%self.sudo_pass]
		args2 = ['sudo', '-S', '%s/nethogs/nethogs'%(self.folder),'-d','2','-t']
		p1 = subprocess.Popen(args1, stdout=subprocess.PIPE)
		self.nethogs_process = subprocess.Popen(args2, stdin=p1.stdout,stdout=subprocess.PIPE,stderr=FNULL) #run the nethogs with 2>/dev/null
		data=[]
		while self.bandwidthPerProcess_active:
			line = self.nethogs_process.stdout.readline() #continuously read from the process 
			if (line=="\n" or line.count("\t")==2):  #From here is the nethogs output processing
				if line!="\n":
					tmp=line.replace("\n","").split("\t")
					name=tmp[0].split("/")
					s=[]
					if name[-2] != "0" and (tmp[1]!='0' and tmp[2]!='0'):
						s.append(name[-2])
						s.append(name[-1])
						s.append(tmp[1])
						s.append(tmp[2])
						data.append(s)
					#print ">>>>"
					#print data
					#print "===="
				#print line.replace("\n","")
				if len(data)>0 and data[0]!='':
					self.proc_rows=data   #the self.proc_rows stores the output each time.
					self.nethogs_alive=True  #And as we received data from the nethogs process, it is alive!
				if line=="\n":
					self.update_process_menu()   #update the menu item.
					data=[]
					time.sleep(1)   #sleep when i receive \n
			if not line:
				print "BREAK"    #If we read null line that means something went wrong, break! kill the nethogs, uncheck the menu.
				self.nethogs_alive=False
				self.nethogs_process=""
				self.kill_nethogs()
				self.bandwidthPerProcess_active=False
				self.nethogs_menu.set_active(False)
				break
		self.nethogs_alive=False
		self.update_process_menu()

	#this method gets the pid and returns the process name
	def _pid_to_name(self,pid):
		cmd='cat /proc/%s/comm 2>/dev/null'%pid
		out=commands.getstatusoutput(cmd)
		if out[1]=='' :
			#out='PID:%s'%pid
			out=""
		else:
			out=out[1]
		return out
	
	#This process updates the menu items
	def update_process_menu(self,args=None):
		#bandwith per process
		if len(self.proc_rows)>0 and self.bandwidthPerProcess_active:     #As long as we have something to update and functionality is active
			#print self.proc_rows
			i=0
			names=[]
			for row in self.proc_rows[0:15] :   #Take only the 0->14 lines
				#print row_items
				if row[0]!='' and row[0].find("[sudo]")==-1:
					name=self._pid_to_name(row[0])
					if name !="":
						_str="% 4.2f KB/s⬆  % 4.2f KB/s⬇"%(float(row[2]),float(row[3]))
						self.menu_process[i].set_label("%s %s"%(_str.ljust(40),name))
						if self.menu_process[i].get_visible()==False: #This line helps to not call too many time the dbus. It fixed the dbus segmentation faults
							self.menu_process[i].set_visible(True)
						i=i+1
			while i<len(self.menu_process):
				if self.menu_process[i].get_visible()==True: #This line helps to not call too many time the dbus. It fixed the dbus segmentation faults
					self.menu_process[i].set_visible(False)
				i=i+1
		if self.bandwidthPerProcess_active == False:
			i=0
			while i<len(self.menu_process):
				if self.menu_process[i].get_visible()==True: #This line helps to not call too many time the dbus. It fixed the dbus segmentation faults
					self.menu_process[i].set_label("")
					self.menu_process[i].set_visible(False)
				i=i+1
			


	#This method builds the Menu
	def build_menu(self,args=None):
		# create a menu
		self.menu = gtk.Menu()
		self.wifi_submenu = gtk.Menu()
		self.devices_submenu=gtk.Menu()

		self.devices_menu=gtk.MenuItem("Device (%s)"%self.active_interface)
		self.devices_menu.set_submenu(self.devices_submenu)
		self.menu.add(self.devices_menu)
	
		self.menu_item_all=gtk.RadioMenuItem(None, "All")
		self.menu_item_all.connect("toggled", self.on_button_toggled, 'All')
		self.menu_item_all.set_active(True)
		self.devices_submenu.append(self.menu_item_all)
		self.menu.append(gtk.SeparatorMenuItem())
		for iface in self.get_interfaces():
			if iface !='All':
				menu_iface=gtk.RadioMenuItem(self.menu_item_all, iface)
				menu_iface.connect("toggled", self.on_button_toggled, iface)
				self.devices_submenu.append(menu_iface)
				menu_iface.show()
		#nethogsmonitor menus
		self.nethogs_menu=gtk.CheckMenuItem("Enable Monitor")
		self.nethogs_menu.set_active(self.bandwidthPerProcess_active)
		self.menu.add(self.nethogs_menu)
		self.nethogs_menu.connect("activate",self.on_nethogs_menu_click);

		for i in range(15):
			self.menu_process.append(gtk.MenuItem(""))
			self.menu.add(self.menu_process[i])
			self.menu_process[i].set_visible(False)
		#seperator
		self.menu.append(gtk.SeparatorMenuItem())
		#Quit button
		exit_menu = gtk.ImageMenuItem(stock_id=gtk.STOCK_QUIT)
		exit_menu.connect('activate', self.on_exit)
		self.menu.add(exit_menu)
		self.menu.show_all()
		self.ind.set_menu(self.menu)
		self.update_process_menu() #After you build the menu, update it, to clear any empty menu items

	#Callback method,on click of interface submenu
	def on_button_toggled(self,button, name):
		if button.get_active():
			self.active_interface = name
			self.devices_menu.set_label("Device (%s)"%self.active_interface)
			i=0
			
			while i<len(self.menu_process):
				self.menu_process[i].set_label("")
				self.menu_process[i].set_visible(False)
				i=i+1
		#	print self.active_interface

	#Callback method when you check/uncheck the "Enable Monitor" menu item
	def on_nethogs_menu_click(self,event=None):
		self.bandwidthPerProcess_active=self.nethogs_menu.get_active()
		if self.bandwidthPerProcess_active:
			if self.sudo_pass == "":
				pass_ok=False
				while pass_ok==False:
					tmp1=ask_passwd("Please type your sudo password. Nethogs requires sudo permissions.")
					tmp2=False
					if tmp1!=False:
						tmp2=ask_passwd("Type again your sudo password.")
				
					if tmp1 == tmp2:
						if tmp1!=False:
							pass_ok=True
							self.sudo_pass=tmp1
						else:
							self.bandwidthPerProcess_active=False
							self.nethogs_menu.set_active(self.bandwidthPerProcess_active)
							break


			if self.nethogs_alive==False and self.nethogs_process=="" and self.sudo_pass!="":
				self.nethogs_thread=threading.Thread(target=self._tail_forever, args=("",))
				self.nethogs_thread.start()
				
		else:
			if self.nethogs_alive and self.nethogs_process!="":
				self.kill_nethogs()
				self.nethogs_process=""

	#Callback , when you clickexit
	def on_exit(self, event=None):
		self.alive.clear()
		self.kill_nethogs()
		gtk.main_quit()

	#gets the interfaces of the machine
	def get_interfaces(self):
		self.interfaces= []
		self.interfaces.append('All')
		output=commands.getoutput('ls /sys/class/net/')
		ifaces=output.split('\n')
		for iface in ifaces:
			self.interfaces.append(iface)
		return self.interfaces
	
	def main(self):
		gtk.main()

	#Format the bytes to B/s , KB/s , MB/s , GB/s 
	def sizeof_fmt(self,num):
		for x in ['B/s','KB/s','MB/s','GB/s']:
			if num < 1024.0 and num > -1024.0:
				if x == 'B/s':
					if num ==0:
						return "%4.2f%s" % (num, x)
					else:
						return "%4.0f%s" % (num, x)
				else:
					return "%4.1f%s" % (num, x)
			num /= 1024.0
		return "%4.1f %s" % (num, 'TB')

	#Ping google to check if we are online. I don't use this method now.
	def internet_on(self):
		try:
			response=urllib2.urlopen('http://74.125.228.100',timeout=1)
			return True
		except urllib2.URLError as err: pass
		return False

	#Kill nethogs process!
	def kill_nethogs(self):
		cmd='ps -aux|grep "netspeed-indicator.*nethogs"|grep -v "grep"|awk \'{print $2}\''
		out=commands.getstatusoutput(cmd)
		if len(out)>1 and out[1]!="":
			pids=out[1].split("\n")
			for pid in pids:
				cmd="echo '%s'|sudo -S kill -9 %s"%(self.sudo_pass,pid)
				out=commands.getstatusoutput(cmd)
#Start everything
if __name__ == "__main__":
    ind = indicatorNetspeed()
    ind.main()	
		 

