#!/usr/bin/python

# RRobinson MediPi usage - 	Added flushes to force data to be sent from script whilst reading from within java program
# 							Added exit statements as only wanted one reading at a time. All dump statements have been commented out
#							Specialisation/agent_type is required to be passed in 

import sys
import dbus
import re
import dbus.service
import dbus.mainloop.glib
import os
import glib
import time
from medipi_healthd_parser import *

dump_prefix = "XML"
# This is a hack - the Omron 708-IT when it completes dissociates but does not disconnect. 
# The next connection made afterwards then immediately disconnects. The isResetting boolean
# allows this disconnection without endig the script so that a new connection can be made. 
# This behaviour is assumed for ALL blood pressure devices - though I dont know this as I have only one brand to test. 
isResetting = True
system_ids = {}

def get_system_id(path, xmldata):
	if path in system_ids:
		return system_ids[path]
	sid = ""
	sid = get_system_id_from_mds(xmldata)
	if sid:
		system_ids[path] = sid
	return sid
	
def dump(path, suffix, xmldata):
	xmldata = beautify(xmldata)
	rsid = get_system_id(path, None)
	if len(rsid) > 4:
		rsid = rsid[-4:]
	if rsid:
		rsid += "_"
	f = open(dump_prefix + "_" + rsid + suffix + ".xml", "w")
	f.write(xmldata)
	f.close()

gsdr = {0: "Success", 1: "Segment unknown", 2: "Fail, try later",
	3: "Fail, segment empty", 512: "Fail, other"}

def getsegmentdata_response_interpret(i):
	try:
		s = gsdr[i]
	except KeyError:
		s = "Unknown fail code"
	return s

pmstore_handle = -1
pmsegment_instance = -1
clear_segment = 0
get_segment = 0
get_pmstore = 0
get_mds = 0
set_time = 0
interpret_data = 0

class Agent(dbus.service.Object):

	@dbus.service.method("com.signove.health.agent", in_signature="ss", out_signature="")
	def Connected(self, dev, addr):
		print
		print "Connected from addr %s, dev %s" % (addr, dev)
		sys.stdout.flush()

		# Convert path to an interface
		dev = bus.get_object("com.signove.health", dev)
		dev = dbus.Interface(dev, "com.signove.health.device")

		glib.timeout_add(0, do_something, dev)

	@dbus.service.method("com.signove.health.agent", in_signature="ss", out_signature="")
	def Associated(self, dev, xmldata):
		global isResetting
		isResetting = False
		print
		print "Associated dev %s: XML with %d bytes" % (dev, len(xmldata))

		print "System ID: %s" % get_system_id(dev, xmldata)
#		dump(dev, "associated", xmldata)
		sys.stdout.flush()
		
		# Convert path to an interface
		devpath = dev
		dev = bus.get_object("com.signove.health", dev)
		dev = dbus.Interface(dev, "com.signove.health.device")

		glib.timeout_add(0, getConfiguration, dev, devpath)

		if clear_segment == 1:
			glib.timeout_add(1000, clearSegment, dev, pmstore_handle, pmsegment_instance)
			return
		elif clear_segment == 2:
			glib.timeout_add(1000, clearAllSegments, dev, pmstore_handle)
			return

		if get_mds:
			glib.timeout_add(0, requestMdsAttributes, dev)
		if set_time:
			glib.timeout_add(800, setTime, dev)
		if get_pmstore:
			glib.timeout_add(2000, getPMStore, dev, pmstore_handle)
			glib.timeout_add(3000, getSegmentInfo, dev, pmstore_handle)
		if get_segment:
			glib.timeout_add(5000, getSegmentData, dev, pmstore_handle, pmsegment_instance)

	@dbus.service.method("com.signove.health.agent", in_signature="ss", out_signature="")
	def MeasurementData(self, dev, xmldata):

		print
		print "MeasurementData dev %s" % dev
		if interpret_data:
			Measurement(DataList(xmldata)).describe()
		else:
			print "=== Data: ", xmldata
#		dump(dev, "measurement", xmldata)
		sys.stdout.flush()

	@dbus.service.method("com.signove.health.agent", in_signature="sis", out_signature="")
	def PMStoreData(self, dev, pmstore_handle, xmldata):
		print
		print "PMStore dev %s handle %d" % (dev, pmstore_handle)
		if interpret_data:
			PMStore(DataList(xmldata)).describe()
		else:
			print "=== Data: XML with %d bytes" % len(xmldata)
#		dump(dev, "pmstore_%d" % pmstore_handle, xmldata)
		sys.stdout.flush()

	@dbus.service.method("com.signove.health.agent", in_signature="sis", out_signature="")
	def SegmentInfo(self, dev, pmstore_handle, xmldata):
		print
		print "SegmentInfo dev %s PM-Store handle %d" % (dev, pmstore_handle)
		if interpret_data:
			SegmentInfo(DataList(xmldata)).describe()
		else:
			print "=== XML with %d bytes" % len(xmldata)
#		dump(dev, "segmentinfo_%d" % pmstore_handle, xmldata)
		sys.stdout.flush()

	@dbus.service.method("com.signove.health.agent", in_signature="siii", out_signature="")
	def SegmentDataResponse(self, dev, pmstore_handle, pmsegment, response):
		print
		print "SegmentDataResponse dev %s PM-Store handle %d" % (dev, pmstore_handle)
		print "=== InstNumber %d" % pmsegment
		print "=== Response %s" % getsegmentdata_response_interpret(response)
		if response != 0 and pmsegment < 7:
			dev = bus.get_object("com.signove.health", dev)
			dev = dbus.Interface(dev, "com.signove.health.device")
			glib.timeout_add(0, getSegmentData, dev, pmstore_handle, pmsegment + 1)
		sys.stdout.flush()

	@dbus.service.method("com.signove.health.agent", in_signature="siis", out_signature="")
	def SegmentData(self, dev, pmstore_handle, pmsegment, xmldata):
		print
		print "SegmentData dev %s PM-Store handle %d inst %d" % \
			(dev, pmstore_handle, pmsegment)
		if interpret_data:
			SegmentData(DataList(xmldata)).describe()
		else:
			print "=== Data: %d bytes XML" % len(xmldata)
#		dump(dev, "segmentdata_%d_%d" % (pmstore_handle, pmsegment), xmldata)
		sys.stdout.flush()

	@dbus.service.method("com.signove.health.agent", in_signature="siii", out_signature="")
	def SegmentCleared(self, dev, pmstore_handle, pmsegment, retstatus):
		print
		print "SegmentCleared dev %s PM-Store handle %d" % (dev, pmstore_handle)
		print "=== InstNumber %d retstatus %d" % (pmsegment, retstatus)
		print
		sys.stdout.flush()
		
	@dbus.service.method("com.signove.health.agent", in_signature="ss", out_signature="")
	def DeviceAttributes(self, dev, xmldata):
		print
		print "DeviceAttributes dev %s" % dev
		if interpret_data:
			DeviceAttributes(DataList(xmldata)).describe()
		else:
			print "=== Data: XML with %d bytes" % len(xmldata)
#		dump(dev, "attributes", xmldata)
		sys.stdout.flush()

	@dbus.service.method("com.signove.health.agent", in_signature="s", out_signature="")
	def Disassociated(self, dev):
		print
		print "Disassociated dev %s" % dev
		sys.stdout.flush()
		if agent_type == 0x1007:
			print >> sys.stdout, "END"
			sys.stdout.flush()
			sys.exit(0)

	@dbus.service.method("com.signove.health.agent", in_signature="s", out_signature="")
	def Disconnected(self, dev):
		print
		print "Disconnected %s" % dev
		sys.stdout.flush()
		if not isResetting:
			print >> sys.stdout, "END"
			sys.stdout.flush()
			sys.exit(0)

def requestMdsAttributes (dev):
	dev.RequestDeviceAttributes()
	return False

def setTime(dev):
	print "Setting time to now"
	dev.SetTime(time.time())
	sys.stdout.flush()
	return False

def getConfiguration(dev, devpath):
	config = dev.GetConfiguration()
	print
	print "Configuration: XML with %d bytes" % len(config)
	print
#	dump(devpath, "config", config)
	if interpret_data:
		Configuration(DataList(config)).describe()
	sys.stdout.flush()
	return False

def getSegmentInfo(dev, handle):
	ret = dev.GetSegmentInfo(handle)
	print
	print "GetSegmentInfo ret %d" % ret
	print
	sys.stdout.flush()
	return False

def getSegmentData(dev, handle, instance):
	ret = dev.GetSegmentData(handle, instance)
	print
	print "GetSegmentData ret %d" % ret
	print
	sys.stdout.flush()
	return False

def clearSegment(dev, handle, instance):
	ret = dev.ClearSegment(handle, instance)
	print
	print "ClearSegment ret %d" % ret
	print
	sys.stdout.flush()
	return False

def clearAllSegments(dev, handle):
	ret = dev.ClearAllSegments(handle)
	print
	print "ClearAllSegments ret %d" % ret
	print
	sys.stdout.flush()
	return False

def getPMStore(dev, handle):
	ret = dev.GetPMStore(handle)
	print
	print "GetPMStore ret %d" % ret
	print
	sys.stdout.flush()
	return False

def do_something(dev):
	# print dev.AbortAssociation()
	# print dev.Connect()
	# print dev.RequestMeasurementDataTransmission()
	# print dev.RequestActivationScanner(55)
	# print dev.RequestDeactivationScanner(55)
	# print dev.ReleaseAssociation()
	# print dev.Disconnect()
	return False

args = sys.argv[1:]

i = 0
while i < len(args):
	arg = args[i]

	if arg == '--mds':
		get_mds = 1
	elif arg == '--set-time':
		set_time = 1
	elif arg == "--interpret" or arg == "--interpret-xml":
		interpret_data = 1
	elif arg == '--prefix':
		dump_prefix = args[i + 1]
		i += 1
	elif arg == '--get-segment':
		get_segment = 1
		get_pmstore = 1
	elif arg == '--clear-segment':
		clear_segment = 1
		get_pmstore = 1
	elif arg == '--clear-all-segments':
		clear_segment = 2
		get_pmstore = 1
	elif arg == '--store' or arg == '--pmstore' or arg == '--pm-store':
		pmstore_handle = int(args[i + 1])
		get_pmstore = 1
		i += 1
	elif arg == '--instance' or arg == '--inst' or arg == '--segment' or \
				arg == '--pm-segment'  or arg == '--pmsegment':
		pmsegment_instance = int(args[i + 1])
		i += 1
	elif arg == '--agent-type':
		agent_type = int(args[i + 1],16)
		i += 1
	else:
		raise Exception("Invalid argument %s" % arg)

	i += 1
	

dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

bus = dbus.SystemBus()

def bus_nameownerchanged(service, old, new):
	if service == "com.signove.health":
		if old == "" and new != "":
			start()
		elif old != "" and new == "":
			stop()

bus.add_signal_receiver(bus_nameownerchanged,
			"NameOwnerChanged",
			"org.freedesktop.DBus",
			"org.freedesktop.DBus",
			"/org/freedesktop/DBus")

def stop():
	global system_ids
	print "Detaching..."
	system_ids = {}
	sys.stdout.flush()

def start():
	print >> sys.stdout, "START"
	print "Starting..."
	sys.stdout.flush()
	try:
		obj = bus.get_object("com.signove.health", "/com/signove/health")
	except:
		print "healthd service not found, waiting..."
#		print >> sys.stdout, "END"
		sys.stdout.flush()
		return
#		sys.exit(0)
	srv = dbus.Interface(obj, "com.signove.health.manager")
	print "Configuring..."
#	srv.ConfigurePassive(agent, [0x1004, 0x1007, 0x1029, 0x100f])
	srv.ConfigurePassive(agent, [agent_type])
	print "Waiting..."
	sys.stdout.flush()


agent = Agent(bus, "/com/signove/health/agent/%d" % os.getpid())

start();

mainloop = glib.MainLoop()
mainloop.run()
