#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Murano Python Simple Device Simulator
# Copyright 2017 Exosite
# Version 2.0
#
# This python script simulates a Smart Light bulb by generating simlulated
# sensor data and taking action on a remote state variable to control on/off.
# It is written to work with the Murano example Smart Light Bulb Consumer example
# application.
#
# For more information see: http://beta-docs.exosite.com/murano/get-started
#
# Requires:
# - Tested with: Python 2.7.9+
# - A basic knowledge of running Python scripts
#
# To run:
# Option 1: From computer with Python installed, run command:  python murano_device_simulator.py
# Option 2: Any machine with Python isntalled, double-click on murano_device_simulator.py to launch
# the Python IDE, which you can then run this script in.
#

import os
import sys
import time
import datetime
import random

import requests
import json


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
UNSET_PRODUCT_ID = 'YOUR_PRODUCT_ID_HERE'
productid = os.getenv('SIMULATOR_PRODUCT_ID', UNSET_PRODUCT_ID)
identifier = os.getenv('SIMULATOR_DEVICE_ID', '000001')  # default identifier

SHOW_HTTP_REQUESTS = False
PROMPT_FOR_PRODUCTID_AND_SN = os.getenv('SIMULATOR_SHOULD_PROMPT', '1') == '1'
LONG_POLL_REQUEST_TIMEOUT = 2 * 1000  # in milliseconds

# -----------------------------------------------------------------
# ---- SHOULD NOT NEED TO CHANGE ANYTHING BELOW THIS LINE ------
# -----------------------------------------------------------------

host_address_base = os.getenv('SIMULATOR_HOST', 'm2.exosite.io')
host_address = None  # set this later when we know the product ID
https_port = 443

# LOCAL DATA VARIABLES
FLAG_CHECK_ACTIVATION = False

state = ''
temperature = 70
humidity = 50
uptime = 0
connected = True
last_modified = {}


#
# DEVICE MURANO RELATED FUNCTIONS
#

def SOCKET_SEND(http_packet):
    context = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
    context.verify_mode = ssl.CERT_REQUIRED
    context.check_hostname = True
    context.load_default_certs()

    # SEND REQUEST
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    ssl_s = context.wrap_socket(s, server_hostname = host_address)
    ssl_s.connect((host_address, https_port))
    if SHOW_HTTP_REQUESTS:
        print("--- Sending ---\r\n {} \r\n----".format(http_packet))
    if PYTHON == 2:
        ssl_s.send(http_packet)
    else:
        ssl_s.send(bytes(http_packet, 'UTF-8'))
    # GET RESPONSE
    response = ssl_s.recv(1024)
    ssl_s.close()
    if SHOW_HTTP_REQUESTS:
        print("--- Response --- \r\n {} \r\n---")

    # PARSE REPONSE
    fake_socket_response = FakeSocket(response)
    parsed_response = httplib.HTTPResponse(fake_socket_response)
    parsed_response.begin()
    return parsed_response


def ACTIVATE():
    try:
        # print("attempt to activate on Murano")

        url = host_address + '/provision/activate'
        headers = {'Content-Type':'application/x-www-form-urlencoded; charset=utf-8'}
        payload = 'id=' + identifier

        response = requests.post(url, data=payload, headers=headers)
        print(response.status_code)
        print(response.text)


        # HANDLE POSSIBLE RESPONSES
        if response.status_code == 200:
            new_cik = response.text
            print("Activation Response: New CIK: {} ..............................".format(new_cik[0:10]))
            return new_cik
        elif response.status_code == 409:
            print("Activation Response: Device Aleady Activated, there is no new CIK")
        elif response.status_code == 404:
            print("Activation Response: Device Identity ({}) activation not available or check Product Id ({})".format(
                identifier,
                productid
                ))
        else:
            print("Activation Response: failed request: {} {}".format(str(response.status_code), response.text))
            return None

    except Exception as e:
        # pass
        print("Exception: {}".format(e))
    return None


def GET_STORED_CIK():
    print("get stored CIK from non-volatile memory")
    try:
        f = open(productid + "_" + identifier + "_cik", "r+")  # opens file to store CIK
        local_cik = f.read()
        f.close()
        print("Stored cik: {} ..............................".format(local_cik[0:10]))
        return local_cik
    except Exception as e:
        print("Unable to read a stored CIK: {}".format(e))
        return None


def STORE_CIK(cik_to_store):
    print("storing new CIK to non-volatile memory")
    f = open(productid + "_" + identifier + "_cik", "w")  # opens file that stores CIK
    f.write(cik_to_store)
    f.close()
    return True


def WRITE(WRITE_PARAMS):
    # print "write data to Murano"

    url = host_address + '/onep:v1/stack/alias'
    headers = {'Content-Type':'application/x-www-form-urlencoded; charset=utf-8', 'X-EXOSITE-CIK': cik}
    payload = WRITE_PARAMS

    response = requests.post(url, data=payload, headers=headers)

    # HANDLE POSSIBLE RESPONSES
    if response.status_code == 204:
        # print "write success"
        return True, 204
    elif response.status_code == 401:
        print("401: Bad Auth, CIK may be bad")
        return False, 401
    elif response.status_code == 400:
        print("400: Bad Request: check syntax")
        return False, 400
    elif response.status_code == 405:
        print("405: Bad Method")
        return False, 405
    else:
        print(str(response.status_code), response.text, 'failed:')
        return False, response.status_code

    # This code is unreachable and should be removed
    #       except Exception as err:
    # pass
    # print("exception: {}".format(str(err)))


    # return None

def READ(READ_PARAMS):
    try:
        # print("read data from Murano")

        url = host_address + '/onep:v1/stack/alias?' + READ_PARAMS
        headers = {'Accept':'application/x-www-form-urlencoded; charset=utf-8', 'X-EXOSITE-CIK': cik}

        response = requests.get(url, headers=headers)

        # HANDLE POSSIBLE RESPONSES
        if response.status_code == 200:
            # print "read success"
            return True, response.text
        elif response.status_code == 401:
            print("401: Bad Auth, CIK may be bad")
            return False, 401
        elif response.status_code == 400:
            print("400: Bad Request: check syntax")
            return False, 400
        elif response.status_code == 405:
            print("405: Bad Method")
            return False, 405
        else:
            print(str(response.status_code), response.text, 'failed:')
            return False, response.status_code

    except Exception as e:
        # pass
        print("Exception: {}".format(e))
    return False, 'function exception'


def LONG_POLL_WAIT(READ_PARAMS):
    try:
        # print "long poll state wait request from Murano"
        # BUILD HTTP PACKET

        url = host_address + '/onep:v1/stack/alias?' + READ_PARAMS
        headers = {'Accept':'application/x-www-form-urlencoded; charset=utf-8', 'Request-Timeout': str(LONG_POLL_REQUEST_TIMEOUT), 'X-EXOSITE-CIK': cik}

        if last_modified.get(READ_PARAMS) != None:
            headers["If-Modified-Since"] = last_modified.get(READ_PARAMS)

        response = requests.get(url, headers=headers)

        # HANDLE POSSIBLE RESPONSES
        if response.status_code == 200:
            # print "read success"
            alias_value = response.text
            status, resp = WRITE(alias_value)
            if response.headers.get('last-modified', None) != None:
                # Save Last-Modified Header (Plus 1s)
                lm = response.headers.get('last-modified', '')
                next_lm = (datetime.datetime.strptime(lm, "%a, %d %b %Y %H:%M:%S GMT") + datetime.timedelta(seconds=1)).strftime("%a, %d %b %Y %H:%M:%S GMT")
                last_modified[READ_PARAMS] = next_lm
            return True, alias_value
        elif response.status_code == 304:
            # print "304: No Change"
            return False, 304
        elif response.status_code == 401:
            print("401: Bad Auth, CIK may be bad")
            return False, 401
        elif response.status_code == 400:
            print("400: Bad Request: check syntax")
            return False, 400
        elif response.status_code == 405:
            print("405: Bad Method")
            return False, 405
        else:
            print(str(response.status_code), response.text)
            return False, response.status_code

    except Exception as e:
        pass
        print("Exception: {}".format(e))
    return False, 'function exception'


# --------------------------
# APPLICATION STARTS RUNNING HERE
# --------------------------


# --------------------------
# BOOT
# --------------------------

# Verify interpreter version is adequate
req_version = (2,7,9)
cur_version = sys.version_info
if cur_version < req_version:
    print("# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-= #")
    print("#        This application must be run using Python 2.7.9 or greater.        #")
    print("#  You can find the latest releases here: https://www.python.org/downloads/ #")
    print("# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-= #")
    exit()

# Check if CIK locally stored already
if PROMPT_FOR_PRODUCTID_AND_SN is True or productid == UNSET_PRODUCT_ID:
    print("Check for Device Parameters Enabled (hit return after each question)")
    productid = input("Enter the Murano Product ID: ")
    host_address = 'https://' + productid + '.' + host_address_base

    print("The Host Address is: {}".format(host_address))
    # hostok = input("If OK, hit return, if you prefer a different host address, type it here: ")
    # if hostok != "":
    #   host_address = hostok

    print("The default Device Identity is: {}".format(identifier))
    identityok = input("If OK, hit return, if you prefer a different Identity, type it here: ")
    if identityok != "":
        identifier = identityok
else:
    host_address = 'https://' + productid + '.' + host_address_base

start_time = int(time.time())
print("\r\n-----")
print("Murano Example Smart Lightbulb Device Simulator booting...")
print("Product Id: {}".format(productid))
print("Device Identity: {}".format(identifier))
print("Product Unique Host: {}".format(host_address))
print("-----")
cik = GET_STORED_CIK()
if cik is None:
    print("try to activate")
    act_response = ACTIVATE()
    if act_response is not None:
        cik = act_response
        STORE_CIK(cik)
        FLAG_CHECK_ACTIVATION = False
        # Set default starting value for state, Off
        status, resp = WRITE('state=0')
    else:
        FLAG_CHECK_ACTIVATION = True

# --------------------------
# MAIN LOOP
# --------------------------
print("starting main loop")

counter = 100  # for debug purposes so you don't have issues killing this process
LOOP = True
lightbulb_state = 0
init = 1

# Check current system expected state
status, resp = READ('state')
if not status and resp == 401:
    FLAG_CHECK_ACTIVATION = True
if not status and resp == 304:
    # print("No New State Value")
    pass
if status:
    # Report updated value for state
    WRITE(resp)
    new_value = resp.split('=')
    lightbulb_state = int(new_value[1])
    if lightbulb_state == 1:
        print("Light Bulb is On")
    else:
        print("Light Bulb is Off")

while LOOP:
    uptime = int(time.time()) - start_time
    last_request = time.time()

    connection = 'Connected'
    if FLAG_CHECK_ACTIVATION:
        connection = "Not Connected"

    output_string = (
        "Connection: {0:s}, Run Time: {1:5d}, Temperature: {2:3.1f} F, Humidity: {3:3.1f} %, Light State: {4:1d}").format(connection, uptime, temperature, humidity, lightbulb_state)
    print("{}".format(output_string))

    if cik is not None and not FLAG_CHECK_ACTIVATION:
        # GENERATE RANDOM TEMPERATURE VALUE

        temperature = round(random.uniform(temperature - 0.2, temperature + 0.2), 1)
        if temperature > 120:
            temperature = 120
        if temperature < 1:
            temperature = 1
        # GENERATE RANDOM HUMIDITY VALUE
        humidity = round(random.uniform(humidity - 0.2, humidity + 0.2), 1)
        if humidity > 100:
            humidity = 100
        if humidity < 1:
            humidity = 1

        status, resp = WRITE('temperature=' + str(temperature) + '&humidity=' + str(humidity) + '&uptime=' + str(uptime))
        if not status and resp == 401:
            FLAG_CHECK_ACTIVATION = True

        # print("Look for on/off state change")
        status, resp = LONG_POLL_WAIT('state')
        if not status and resp == 401:
            FLAG_CHECK_ACTIVATION = True
        if not status and resp == 304:
            # print("No New State Value")
            pass
        if status:
            # print("New State Value: {}".format(str(resp)))
            new_value = resp.split('=')

            if lightbulb_state != int(new_value[1]):
                lightbulb_state = int(new_value[1])
                if lightbulb_state == 1:
                    print("Action -> Turn Light Bulb On")
                else:
                    print("Action -> Turn Light Bulb Off")

    if FLAG_CHECK_ACTIVATION:
        if (uptime % 10) == 0:
            # print("---")
            print("Device CIK may be expired or not available (not added to product) - trying to activate")
        act_response = ACTIVATE()
        if act_response is not None:
            cik = act_response
            print(cik)
            STORE_CIK(cik)
            FLAG_CHECK_ACTIVATION = False
        else:
            # print("Wait 10 seconds and attempt to activate again")
            time.sleep(1)
