# 
# Murano Python Simple Device Simulator 
# Copyright 2016 Exosite
# Version 1.0
# 
# This python script simulates a Smart Light bulb by generating simlulated 
# sensor data and taking action on a remote state variable to control on/off.
# It is written to work with the Murano example Smart Light Bulb Consumer example 
# application.
# 
# For more information see: http://beta-docs.exosite.com/murano/get-started
# 
# Requires: 
# - Tested with: Python 2.6 or Python 2.7 
# - A basic knowledge of running Python scripts
# 
# To run:
# Option 1: From computer with Python installed, run command:  python murano_device_simulator.py 
# Option 2: Any machine with Python isntalled, double-click on murano_device_simulator.py to launch 
# the Python IDE, which you can then run this script in.
# 

import time
import datetime
import random
from pprint import pprint
import json

import socket
import sys
import ssl

import urllib 
try:
    from StringIO import StringIO
    import httplib
    input = raw_input
    PYTHON = 2
except ImportError:
    from http import client as httplib
    from io import StringIO, BytesIO
    PYTHON = 3

# -----------------------------------------------------------------
# EXOSITE PRODUCT ID / SERIAL NUMBER IDENTIFIER / CONFIGURATION
# -----------------------------------------------------------------
productid = 'YOUR_PRODUCT_ID_HERE' 
identifier = '000001' #default identifier

SHOW_HTTP_REQUESTS = False
PROMPT_FOR_PRODUCTID_AND_SN = True
AUTO_STOP = True # set to False to keep running indefinitely - this is a safety feature for new devs
LONG_POLL_REQUEST_TIMEOUT = 2*1000 #in milliseconds


# -----------------------------------------------------------------
# ---- SHOULD NOT NEED TO CHANGE ANYTHING BELOW THIS LINE ------
# -----------------------------------------------------------------

host_address = productid+'.m2.exosite.com'
https_port = 443

class FakeSocket():
    def __init__(self, response_str):
        if PYTHON == 2:
            self._file = StringIO(response_str)
        else:
            self._file = BytesIO(response_str)
    def makefile(self, *args, **kwargs):
        return self._file

# LOCAL DATA VARIABLES
FLAG_CHECK_ACTIVATION = False

state = ''
temperature = 70
humidity = 50
uptime = 0
connected = True
last_request = 0
start_time = 0
last_modified = {}

#
# DEVICE MURANO RELATED FUNCTIONS
#

def SOCKET_SEND(http_packet):
		# SEND REQUEST
		s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		ssl_s = ssl.wrap_socket(s)
		ssl_s.connect((host_address, https_port))
		if SHOW_HTTP_REQUESTS: print ('--- Sending ---\r\n' + http_packet + '\r\n----')
		if PYTHON == 2:
			ssl_s.send(http_packet)
		else:
			ssl_s.send(bytes(http_packet, 'UTF-8'))
		# GET RESPONSE
		response = ssl_s.recv(1024)
		ssl_s.close()
		if SHOW_HTTP_REQUESTS: print ('--- Response --- \r\n' + str(response) + '\r\n---')

		#PARSE REPONSE
		fake_socket_response = FakeSocket(response)
		parsed_response = httplib.HTTPResponse(fake_socket_response)
		parsed_response.begin()
		return parsed_response


def ACTIVATE():
		try:
			print ('attempt to activate on Murano')

			http_body = 'vendor='+productid+'&model='+productid+'&sn='+identifier
			# BUILD HTTP PACKET 
			http_packet = ""
			http_packet = http_packet + 'POST /provision/activate HTTP/1.1\r\n'
			http_packet = http_packet + 'Host: '+host_address+'\r\n'
			http_packet = http_packet + 'Connection: Close \r\n'
			http_packet = http_packet + 'Content-Type: application/x-www-form-urlencoded; charset=utf-8\r\n'
			http_packet = http_packet + 'content-length:'+ str(len(http_body)) +'\r\n'
			http_packet = http_packet + '\r\n'
			http_packet = http_packet + http_body

			response = SOCKET_SEND(http_packet)

			# HANDLE POSSIBLE RESPONSES
			if response.status == 200:
				new_cik = response.read()
				print ('Activation Response: New CIK:' + new_cik[0:10]+'..............................')
				return new_cik
			elif response.status == 409:
				print ('Activation Response: Device Aleady Activated, there is no new CIK')
			elif response.status == 404:
				print ('Activation Response: Device Identity ('+identifier+') activation not available or check Product Id ('+productid+')')
			else:
				print ('Activation Response: failed request: ', str(response.status), response.reason)
				return None

		except Exception as err:
			#pass
			print ('exeception: ' + str(err))
		return None

def GET_STORED_CIK():
		print ('get stored CIK from non-volatile memory')
		try:
			f = open(productid+"_"+identifier+"_cik","r+") #opens file to store CIK
			local_cik = f.read()
			f.close()
			print ('stored cik: ' + local_cik[0:10]+'..............................')
			return local_cik
		except:
			print ('problem getting stored CIK')
			return None

def STORE_CIK(cik_to_store):
		print ('storing new CIK to non-volatile memory')
		f = open(productid+"_"+identifier+"_cik","w") #opens file that stores CIK
		f.write(cik_to_store)
		f.close()
		return True


def WRITE(WRITE_PARAMS):
#		try:
			#print 'write data to Murano'

			http_body = WRITE_PARAMS
			# BUILD HTTP PACKET 
			http_packet = ""
			http_packet = http_packet + 'POST /onep:v1/stack/alias HTTP/1.1\r\n'
			http_packet = http_packet + 'Host: '+host_address+'\r\n'
			http_packet = http_packet + 'X-EXOSITE-CIK: '+cik+'\r\n'
			http_packet = http_packet + 'Connection: Close \r\n'
			http_packet = http_packet + 'Content-Type: application/x-www-form-urlencoded; charset=utf-8\r\n'
			http_packet = http_packet + 'content-length:'+ str(len(http_body)) +'\r\n'
			http_packet = http_packet + '\r\n'
			http_packet = http_packet + http_body

			response = SOCKET_SEND(http_packet)

			# HANDLE POSSIBLE RESPONSES
			if response.status == 204:
				#print 'write success'
				return True,204
			elif response.status == 401:
				print ('401: Bad Auth, CIK may be bad')
				return False,401
			elif response.status == 400:
				print ('400: Bad Request: check syntax')
				return False,400
			elif response.status == 405:
				print ('405: Bad Method')
				return False,405		
			else:
				print (str(response.status), response.reason, 'failed:')
				return False,response.status

#		except Exception as err:
			#pass
			print ('exeception: ' + str(err))
#		return None

def READ(READ_PARAMS):
		try:
			print ('read data from Murano')

			# BUILD HTTP PACKET 
			http_packet = ""
			http_packet = http_packet + 'GET /onep:v1/stack/alias?'+READ_PARAMS+' HTTP/1.1\r\n'
			http_packet = http_packet + 'Host: '+host_address+'\r\n'
			http_packet = http_packet + 'X-EXOSITE-CIK: '+cik+'\r\n'
			#http_packet = http_packet + 'Connection: Close \r\n'
			http_packet = http_packet + 'Accept: application/x-www-form-urlencoded; charset=utf-8\r\n'
			http_packet = http_packet + '\r\n'

			response = SOCKET_SEND(http_packet)

			# HANDLE POSSIBLE RESPONSES
			if response.status == 200:
				#print 'read success'
				return True,response.read()
			elif response.status == 401:
				print ('401: Bad Auth, CIK may be bad')
				return False,401
			elif response.status == 400:
				print ('400: Bad Request: check syntax')
				return False,400
			elif response.status == 405:
				print ('405: Bad Method')
				return False,405		
			else:
				print (str(response.status), response.reason, 'failed:')
				return False,response.status

		except Exception as err:
			#pass
			print ('exeception: ' + str(err))
		return False,'function exception'

def LONG_POLL_WAIT(READ_PARAMS):
		try:
			#print 'long poll state wait request from Murano'
			# BUILD HTTP PACKET 
			http_packet = ""
			http_packet = http_packet + 'GET /onep:v1/stack/alias?'+READ_PARAMS+' HTTP/1.1\r\n'
			http_packet = http_packet + 'Host: '+host_address+'\r\n'
			http_packet = http_packet + 'Accept: application/x-www-form-urlencoded; charset=utf-8\r\n'
			http_packet = http_packet + 'X-EXOSITE-CIK: '+cik+'\r\n'
			http_packet = http_packet + 'Request-Timeout: ' + str(LONG_POLL_REQUEST_TIMEOUT) + '\r\n'
			if last_modified.get(READ_PARAMS) != None:
				http_packet = http_packet + 'If-Modified-Since: ' + last_modified.get(READ_PARAMS) + '\r\n'
			http_packet = http_packet + '\r\n'

			response = SOCKET_SEND(http_packet)

			# HANDLE POSSIBLE RESPONSES
			if response.status == 200:
				#print 'read success'
				if response.getheader("last-modified") != None:
					# Save Last-Modified Header (Plus 1s)
					lm = response.getheader("last-modified")
					next_lm = (datetime.datetime.strptime(lm , "%a, %d %b %Y %H:%M:%S GMT")
						      + datetime.timedelta(seconds=1)).strftime("%a, %d %b %Y %H:%M:%S GMT")
					last_modified[READ_PARAMS] = next_lm
				return True,response.read()
			elif response.status == 304:
				#print '304: No Change'
				return False,304			
			elif response.status == 401:
				print ('401: Bad Auth, CIK may be bad')
				return False,401
			elif response.status == 400:
				print ('400: Bad Request: check syntax')
				return False,400
			elif response.status == 405:
				print ('405: Bad Method')
				return False,405		
			else:
				print (str(response.status), response.reason)
				return False,response.status

		except Exception as err:
			pass
			print ('exeception: ' + str(err))
		return False,'function exception'

# --------------------------
# APPLICATION STARTS RUNNING HERE 
# --------------------------


# --------------------------
# BOOT
# --------------------------

#Check if CIK locally stored already
if PROMPT_FOR_PRODUCTID_AND_SN == True or productid=='YOUR_PRODUCT_ID_HERE':
	print ('Check for Device Parameters Enabled (hit return after each question)')
	productid = input("Enter the Murano Product ID: ")
	host_address = productid+'.m2.exosite.com'

	print ('The default Host Address is: '+ host_address)
	hostok = input("If OK, hit return, if you prefer a different host address, type it here: ")
	if hostok != "":
		host_address = hostok

	print ('The default Device Identity is: '+ identifier)
	identityok = input("If OK, hit return, if you prefer a different Identity, type it here: ")
	if identityok != "":
		identifier = identityok

start_time = int(time.time())
print ('\r\n-----')
print ('Murano Example Smart Lightbulb Device Simulator booting...')
print ('Product Id: '+ productid)
print ('Device Identity: '+ identifier)
print ('Product Unique Host: '+ host_address)
print ('-----')
cik = GET_STORED_CIK()
if cik == None:
	print ('try to activate')
	act_response = ACTIVATE()
	if act_response != None:
		cik = act_response
		STORE_CIK(cik)
		FLAG_CHECK_ACTIVATION = False
	else:
		FLAG_CHECK_ACTIVATION = True

# --------------------------
# MAIN LOOP
# --------------------------
print ('starting main looop')

counter = 100 #for debug purposes so you don't have issues killing this process
LOOP = True
lightbulb_state = 0

while LOOP:
	uptime = int(time.time()) - start_time
	#if time.time() - last_request > REQUEST_LOOP_INTERVAL:

	if (uptime%10) == 0:
		print ('---')
		print ('Application: Running - Run Time: ' + str(uptime) + ' sec')
		if lightbulb_state == '1':
			print ('Light Bulb: On')
		else:
			print ('Light Bulb: Off')

	if True:
		last_request = time.time()
		if cik != None and FLAG_CHECK_ACTIVATION != True:
			# GENERATE RANDOM TEMPERATURE VALUE
			temperature = random.randint(temperature-1,temperature+1)
			if temperature > 120: temperature = 120
			if temperature < 1: temperature = 1
			# GENERATE RANDOM HUMIDITY VALUE
			humidity = random.randint(humidity-1,humidity+1)
			if humidity > 100: humidity = 100
			if humidity < 1: humidity = 1
			
			#print('Write Sensor Data')
			status,resp = WRITE('temperature='+str(temperature)+'&humidity='+str(humidity)+'&uptime='+str(uptime))
			if status == False and resp == 401:
				FLAG_CHECK_ACTIVATION = True
			
			#print('Look for on/off state change')
			status,resp = LONG_POLL_WAIT('state')
			if status == False and resp == 401:
				FLAG_CHECK_ACTIVATION = True
			if status == False and resp == 304:
				#print('No New State Value')
				pass
			if status == True:
				print('New State Value:' + str(resp))
				new_value = resp.split('=')

				if lightbulb_state != new_value[1]:
					lightbulb_state = new_value[1]
					if new_value[1] == '1':
						print ('Turn Light Bulb On')
					else:
						print ('Turn Light Bulb Off')
			
			if FLAG_CHECK_ACTIVATION == True:
				print('ACTIVATION STATE: NOT ACTIVATED')
			#else:
			#	print('ACTIVATION STATE: ACTIVATED')

	if FLAG_CHECK_ACTIVATION == True:
		if (uptime%10) == 0:
			print ('---')
			print ('Device CIK may be expired or not available (not added to product) - trying to activate')
		act_response = ACTIVATE()
		if act_response != None:
			cik = act_response
			STORE_CIK(cik)
			FLAG_CHECK_ACTIVATION = False
		else:
			#print ('Wait 10 seconds and attempt to activate again')
			time.sleep(1)

	if AUTO_STOP == True & counter > 0:
		if (counter%10) == 0:
			print('auto stopping app loop in ~' +str(counter)+ ' seconds')
		counter = counter - 1

	if AUTO_STOP == True & counter <= 0:
		print('auto stopping this simulator application loop')
		LOOP=False
		break

