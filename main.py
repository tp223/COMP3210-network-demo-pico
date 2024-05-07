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
import urequests as requests
import json
from bluetooth_helper import advertising_payload
import bluetooth

# Delay for 5 seconds
time.sleep(5)

# Define network handlers
ap_wlan = network.WLAN(network.AP_IF)
sta_wlan = network.WLAN(network.STA_IF)

ap_wlan.active(False)
sta_wlan.active(False)

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
    ap_wlan.active(False)
    
    # Scan WiFi networks
    sta_wlan.active(True)
    print('Scanning WiFi networks')
    nets = sta_wlan.scan()
    for net in nets:
        print(net)
    sta_wlan.active(False)
    print('WiFi Off')

    # Get pico serial
    my_id = ubinascii.hexlify(machine.unique_id()).decode()
    print(my_id)
    # Generate unique SSID
    net_ssid = "Beacon " + my_id[-6:].upper()
    # Start WiFi in AP mode
    ap_wlan.config(essid=net_ssid, security=0)
    ap_wlan.active(True)

    while ap_wlan.active() == False:
        pass
    
    print('WiFi Active')
    ip = ap_wlan.ifconfig()[0]
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
                # Close the socket
                s.close()
                # Wait for 5 seconds
                time.sleep(5)
                # Disable the AP
                ap_wlan.active(False)
                print('WiFi Off')
                # Wait for 5 seconds
                time.sleep(5)
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
        machine.reset()

    # Check if the device is set up on the server
    # Send POST request to https://navi.knapstack.co.uk/api/beacons/register
    url = 'https://navi.knapstack.co.uk/api/beacon/register'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + api_key
    }
    data = {
        'user_key': setup_key,
        'serial_number': ubinascii.hexlify(machine.unique_id()).decode()
    }
    # Convert data to JSON
    data = json.dumps(data)
    response = requests.post(url, headers=headers, data=data)

    if response.status_code == 200:
        # Check if error is in the response
        if 'error' in response.json():
            print('Error: %s' % response.json()['error'])
        else:
            # Get the api key from the response
            print(response.json())
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
        'Content-Type': 'application/json',
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
        machine.reset()
    
    if setup_complete:
        print('Device setup complete')

def connect_to_wifi():
    with open('wifi.txt', 'r') as f:
        ssid = f.readline().strip()
        password = f.readline().strip()
    print('(wifi.txt) SSID = %s' % ssid)
    print('(wifi.txt) Password = %s' % password)
    sta_wlan.active(True)
    sta_wlan.connect(ssid, password)
    # Wait for up to 10 seconds to connect
    start = time.ticks_ms()
    while not sta_wlan.isconnected():
        if time.ticks_diff(time.ticks_ms(), start) > 10000:
            print('Failed to connect to WiFi')
            return False

    if sta_wlan.isconnected():
        print('Connected to WiFi')
        print('IP: ' + sta_wlan.ifconfig()[0])
        # Wait for 5 seconds
        time.sleep(5)
        return True

def main():
    # Start BLE
    ble = bluetooth.BLE()
    ble.active(True)
    # Get the MAC address
    mac = ubinascii.hexlify(ble.config('mac')[1],':').decode().upper()
    print('BLE MAC: %s' % mac)
    mac_name = mac.replace(':', '')
    # Generate the name
    name = 'NAVI-' + mac_name
    # Generate the payload
    payload = advertising_payload(
        name=name,
        services=[],
    )
    print(payload)
    print("Starting BLE advertising...")
    ble.gap_advertise(100, adv_data=payload)

    # Send the MAC address to the server
    with open('keys.txt', 'r') as f:
            setup_key = f.readline().strip()
            api_key = f.readline().strip()
    print('(keys.txt) Setup Key = %s' % setup_key)
    print('(keys.txt) API Key = %s' % api_key)
    print('Sending MAC address to server...')
    # Send POST request to https://navi.knapstack.co.uk/api/beacon/send-name
    url = 'https://navi.knapstack.co.uk/api/beacon/send-name'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + api_key
    }
    data = {
        'mac': mac,
        'name': name
    }
    # Convert data to JSON
    data = json.dumps(data)
    response = requests.post(url, headers=headers, data=data)

    if response.status_code == 200:
        # Check if error is in the response
        if 'error' in response.json():
            print('Error: %s' % response.json()['error'])
        else:
            print('MAC address sent to server')
    else:
        print('Failed to send MAC address to server')
    
    # Wait for user to stop
    input("Press Enter to stop...")
    ble.active(False)
    print("Bluetooth Disabled")


# Check if wifi.txt exists and attempt to connect to the network
if 'wifi.txt' in os.listdir():
    if not connect_to_wifi():
        start_ap()
        # Restart the device
        machine.reset()
else:
    print('No WiFi credentials found')
    start_ap()
    # Restart the device
    machine.reset()

# Check the device setup status
check_setup()

# Start the main program
print('Starting main program')
main()

