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
            
                response = page_setup_complete('https://www.google.com', my_id[-6:])
                
            conn.send(response)
            conn.close()
    except Exception as e:
        s.close()
        # Throw original exception
        raise e


start_ap()