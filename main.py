'''
Author: Tom Pavier
Date: May 2024
'''

import network
import time
import socket
import urandom
import machine
import ubinascii
import os
import requests

keys = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz1234567890'

def randstr(length=10, aSeq=keys):
    return ''.join((urandom.choice(aSeq) for _ in range(length)))

def page_setup(networks, device_id):
    # Get setup.html
    with open('setup.html', 'r') as f:
        html = f.read()
    # Display WiFi networks
    net_list = ''
    for net in networks:
        net_list += '<option value="' + net[0].decode() + '">' + net[0].decode() + '</option>'
    html = html.replace('<!--NETWORKS-->', net_list)
    # Replace all occurrences of <!--DEVICE-ID--> with the device ID
    html = html.replace('<!--DEVICE-ID-->', device_id)
    return html

def page_setup_complete(redirect_url, device_id):
    # Get setup_complete.html
    with open('setup_complete.html', 'r') as f:
        html = f.read()
    # Replace all occurrences of <!--ACCOUNT-SETUP-URL--> with the redirect URL
    html = html.replace('<!--ACCOUNT-SETUP-URL-->', redirect_url)
    # Replace all occurrences of <!--DEVICE-ID--> with the device ID
    html = html.replace('<!--DEVICE-ID-->', device_id)
    return html


def start_ap():
    # Reset WiFi if already active
    wlan = network.WLAN(network.STA_IF)
    wlan.active(False)
    
    # Scan WiFi networks
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    print('Scanning WiFi networks')
    nets = wlan.scan()
    for net in nets:
        print(net)
    wlan.active(False)
    print('WiFi Off')

    # Get pico serial
    my_id = ubinascii.hexlify(machine.unique_id()).decode()
    print(my_id)
    # Generate unique SSID
    net_ssid = "Beacon " + my_id[-6:].upper()
    # Start WiFi in AP mode
    ap = network.WLAN(network.AP_IF)
    
    ap.config(essid=net_ssid, security=0)
    ap.active(True)

    while ap.active() == False:
        pass
    
    print('WiFi Active')
    ip = ap.ifconfig()[0]
    print('IP: ' + ip)
    
    # Socket for web server
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 80))
    s.listen(5)

    try:
        while True:
            conn, addr = s.accept()
            print('Got a connection from %s' % str(addr))
            request = conn.recv(1024)
            print('Content = %s' % str(request))
            # Get request contents without b' and '
            request = str(request.decode('utf-8'))
            # Get URL
            url = str(request).split(' ')[1]
            # Get method
            method = str(request).split(' ')[0]
            print('URL = %s' % url)
            print('Method = %s' % method)
            setup_complete = False
            response = "HTTP/1.1 404 Not Found\nContent-Type: text/html\n\n<!DOCTYPE html><html><head><title>404</title></head><body><h1>404 Not Found</h1></body></html>"
            if url == '/' and method == "GET":
                response = page_setup(nets, my_id[-6:])
            elif url == '/' and method == "POST":
                # Get the SSID and password from the request
                data = request.split('\r\n\r\n')[-1]
                print('Data = %s' % data)
                data = data.split('&')
                ssid = None
                password = None
                for i in range(len(data)):
                    key = data[i].split('=')[0]
                    value = data[i].split('=')[1]
                    print('Key = %s' % key)
                    print('Value = %s' % value)
                    if key == 'network':
                        # URL decode the SSID
                        ssid = value.replace('%3A', ':').replace('%2D', '-').replace('%5F', '_').replace('%2E', '.').replace('+', ' ')
                    elif key == 'password':
                        # URL decode the password
                        password = value.replace('%3A', ':').replace('%2D', '-').replace('%5F', '_').replace('%2E', '.').replace('+', ' ')
                print('SSID = %s' % ssid)
                print('Password = %s' % password)

                # Save the SSID and password to a file
                with open('wifi.txt', 'w') as f:
                    f.write(ssid + '\n')
                    f.write(password + '\n')

                # Generate the setup key for the API and user
                setup_key = randstr(5)
                print('Setup Key = %s' % setup_key)
                api_key = randstr(30)
                print('API Key = %s' % api_key)

                # Save the setup key and API key to a file
                with open('keys.txt', 'w') as f:
                    f.write(setup_key + '\n')
                    f.write(api_key + '\n')

                # Generate the redirect URL
                redirect_url = 'https://navi.knapstack.co.uk/dashboard/beacons/add/' + setup_key
            
                response = page_setup_complete(redirect_url, my_id[-6:])

                setup_complete = True
                
            conn.send(response)
            conn.close()
            if setup_complete:
                # Wait for 5 seconds
                time.sleep(5)
                # Disconnect from the AP
                ap.active(False)
                print('WiFi Off')
                # Break out of the loop
                break
    except Exception as e:
        s.close()
        # Throw original exception
        raise e

def check_setup():
    # Check if keys.txt exists
    if 'keys.txt' in os.listdir():
        with open('keys.txt', 'r') as f:
            setup_key = f.readline().strip()
            api_key = f.readline().strip()
        print('(keys.txt) Setup Key = %s' % setup_key)
        print('(keys.txt) API Key = %s' % api_key)
    else:
        print('No setup keys found - device not set up')
        start_ap()

        with open('keys.txt', 'r') as f:
            setup_key = f.readline().strip()
            api_key = f.readline().strip()
        print('(keys.txt) Setup Key = %s' % setup_key)
        print('(keys.txt) API Key = %s' % api_key)

    # Check if the device is set up on the server
    # Send POST request to https://navi.knapstack.co.uk/api/beacons/register
    url = 'https://navi.knapstack.co.uk/api/beacon/register'
    headers = {
        'Content-Type': 'x-www-form-urlencoded',
        'Authorization': 'Bearer ' + api_key
    }
    data = {
        'user_key': setup_key,
        'serial_number': ubinascii.hexlify(machine.unique_id()).decode()
    }
    response = requests.post(url, headers=headers, data=data)

    if response.status_code == 200:
        # Check if error is in the response
        if 'error' in response.json():
            print('Error: %s' % response.json()['error'])
        else:
            # Get the api key from the response
            api_key = response.json()['api_key']
            print('API Key = %s' % api_key)
            # Save the API key to a file
            with open('keys.txt', 'w') as f:
                f.write(setup_key + '\n')
                f.write(api_key + '\n')
    else:
        print('Failed to register device with server')

    # Wait for setup to complete
    time.sleep(5)
    # Send GET request to https://navi.knapstack.co.uk/api/beacon/poll-setup
    url = 'https://navi.knapstack.co.uk/api/beacon/poll-setup'
    headers = {
        'Content-Type': 'x-www-form-urlencoded',
        'Authorization': 'Bearer ' + api_key
    }

    setup_complete = False
    error = False
    while not setup_complete and not error:
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            # Check if error is in the response
            if 'error' in response.json():
                print('Error: %s' % response.json()['error'])
            else:
                # Check if setup is complete
                if response.json()['status'] == 'completed':
                    print('Device setup complete')
                    setup_complete = True
                elif response.json()['status'] == 'pending':
                    print('Device setup pending')
                elif response.json()['status'] == 'error':
                    print('Device setup failed')
                    error = True
                else:
                    print('Unknown status')
        else:
            print('Failed to poll server for setup status')
        time.sleep(5)
    
    if error:
        print('Device setup failed')
        start_ap()
    
    if setup_complete:
        print('Device setup complete')


failed_to_connect = True

# Check if wifi.txt exists and attempt to connect to the network
if 'wifi.txt' in os.listdir():
    with open('wifi.txt', 'r') as f:
        ssid = f.readline().strip()
        password = f.readline().strip()
    print('(wifi.txt) SSID = %s' % ssid)
    print('(wifi.txt) Password = %s' % password)
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(ssid, password)
    # Wait for up to 10 seconds to connect
    start = time.ticks_ms()
    while not wlan.isconnected():
        if time.ticks_diff(time.ticks_ms(), start) > 10000:
            print('Failed to connect to WiFi')
            break

    if wlan.isconnected():
        failed_to_connect = False
        print('Connected to WiFi')
        print('IP: ' + wlan.ifconfig()[0])

if failed_to_connect:
    print('Failed to connect to WiFi - starting AP')
    start_ap()

# Check the device setup status
check_setup()

# Start the main program
print('Starting main program')
# main()

