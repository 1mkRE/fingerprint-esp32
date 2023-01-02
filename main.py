import machine
from machine import Pin, I2C
from machine import UART
from time import sleep
from time import time
import ssd1306

uart = UART(2, 19200, bits=8, parity=None, stop=1, tx=17, rx=16, timeout=2000)

i2c = I2C(scl=Pin(22), sda=Pin(21), freq=10000)

display = ssd1306.SSD1306_I2C(128, 64, i2c)

# Antwort nummern festlegung
ACK_SUCCESS = 0x00
ACK_FAIL = 0x01
ACK_FULL = 0x04
ACK_NO_USER = 0x05
ACK_TIMEOUT = 0x08
ACK_GO_OUT = 0x0F
ACK_START = 0xFF

# Kommando festlegung
CMD_HEAD = 0xF5
CMD_TAIL = 0xF5
CMD_ADD_1 = 0x01
CMD_ADD_2 = 0x02
CMD_ADD_3 = 0x03
CMD_MATCH = 0x0C
CMD_DEL = 0x04
CMD_DEL_ALL = 0x05
CMD_USER_CNT = 0x09
CMD_COM_LEV = 0x28
CMD_LP_MODE = 0x2C
CMD_TIMEOUT = 0x2E
CMD_FINGER_DETECTED = 0x14

response_buf = []

interrupt_activ = False
sens = False
name = ''
status = ''
fail_messages = ['Not registred!', 'Time Out Error!', 'Error']
state = 0

# ***************************************************************************
# Access Point
# ***************************************************************************/

try:
    import usocket as socket
except:
    import socket

import network

import esp

esp.osdebug(None)

import gc

gc.collect()

ssid = 'SSID'
password = 'Password'
value = True
User = ''
s = None

ap = network.WLAN(network.AP_IF)
ap.active(True)
ap.config(essid=ssid, password=password)

while ap.active() == False:
    pass

print('Connection successful')
print(ap.ifconfig())


def web_page():
    if value == 1:
        Door = "CLOSE"
    else:
        Door = "OPEN"

    html = """<html><head><title>Security System Web Server</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta charset="UTF-8">
  <meta name="description" content="Security System Web Server">
  <meta name="keywords" content="HTML">
  <meta name="author" content="MAK">
  <link rel="icon" href="data:,">
  <style>
  body { text-align: center; font-family: "Trebuchet MS", Arial;}
  .button{display: inline-block; background-color: #313c48; border: none; border-radius:
  4px; color: white; padding: 16px 70px; text-decoration: none; font-size: 30px; margin: 2px; cursor: pointer;}
  table { border-collapse: collapse; width:35%; margin-left:auto; margin-right:auto; }
  th { padding: 12px; background-color: #554f4a; color: white; }
  tr { border: 1px solid #ddd; padding: 12px; }
  td { border: none; padding: 12px; }
  .sensor { color:white; font-weight: bold; background-color: #bcbcbc; padding: 1px;}
  </style>
  </head>

  <body>
  <h1><b>Security system</b></h1>
  <table>
  <tr>
  <th>Last user information</th>
  </tr>
  <tr><td><b>Name</b></td><td><span class="sensor">""" + name + """</span></td></tr>
  <tr><td><b>Event</b></td><td><span class="sensor">""" + status + """</span></td></tr>
  <table>
  <tr>
  <th>Door Status</th>
  </tr>
  <tr><td><b>Door status</b></td><td><span class="sensor">""" + Door + """</span></td></tr>
  <tr><td><b>Post status</b></td><td><span class="sensor">""" + Door + """</span></td></tr>
  </body></html>"""
    return html


# ***************************************************************************
# Ende Access Point
# ***************************************************************************/

Finger_WAKE_Pin = Pin(34, Pin.IN)
Finger_RST_Pin = Pin(5, Pin.OUT)
led = Pin(2, Pin.OUT)


def InterruptDoorOpen(pin):
    global interrupt_activ
    interrupt_activ = True
    connection_close()
    print('Interrupt')


Finger_WAKE_Pin.irq(trigger=Pin.IRQ_RISING, handler=InterruptDoorOpen)


# ***************************************************************************
# Verschiedene Funktionen
# ***************************************************************************/
def showdisplay(head, main, head_offset, main_offset):
    display.fill(0)
    display.text(head, head_offset, 20)
    display.text(main, main_offset, 30)
    display.show()


def LedError():
    led.value(1)
    sleep(0.25)
    led.value(0)
    sleep(0.25)
    led.value(1)
    sleep(0.25)
    led.value(0)


def OpenDoor():
    led.value(1)
    sleep(5)
    led.value(0)


def username(usernumber):
    user_name = ['Default', 'User1', 'User2', 'User3', 'User4', 'User5', 'User6']
    if usernumber > 0 and usernumber < 7:
        return user_name[usernumber]
    else:
        return user_name[0]


def connection_close():
    global s
    if s:
        s.close()
        # s = None


# ***************************************************************************
# Kommando senden und auf Modul Antwort warten
# ***************************************************************************/
def TxAndRxCmd(command_buf, rx_bytes_need, timeout):
    global response_buf
    CheckSum = 0
    tx_buf = []

    tx_buf.append(CMD_HEAD)
    for byte in command_buf:
        tx_buf.append(byte)
        CheckSum ^= byte

    tx_buf.append(CheckSum)
    tx_buf.append(CMD_TAIL)
    print(tx_buf)
    uart.write(bytes(tx_buf))

    response_buf = []
    time_before = time()
    time_after = time()
    while time_after - time_before < timeout and len(response_buf) < rx_bytes_need:  # Warte auf Antwort
        bytes_can_recv = uart.any()
        if bytes_can_recv != 0:
            response_buf += uart.read(bytes_can_recv)
        time_after = time()

    print(response_buf)
    for i in range(len(response_buf)):
        response_buf[i] = int(response_buf[i])

    if len(response_buf) != rx_bytes_need:
        return ACK_TIMEOUT

    if response_buf[0] != CMD_HEAD:
        return ACK_FAIL
    if response_buf[rx_bytes_need - 1] != CMD_TAIL:
        return ACK_FAIL
    if response_buf[1] != tx_buf[1]:
        return ACK_FAIL

    CheckSum = 0
    for index, byte in enumerate(response_buf):
        if index == 0:
            continue
        if index == 6:
            if CheckSum != byte:
                return ACK_FAIL
        CheckSum ^= byte
    return ACK_SUCCESS;


# ***************************************************************************
# Prufen ob Modul korrekt gestartet ist
# ***************************************************************************/
def GetSensorStatus():
    global response_buf
    print('Sensor gestartet')
    command_buf = [CMD_USER_CNT, 0, 0, 0, 0]
    r = TxAndRxCmd(command_buf, 8, 5)
    if r == ACK_SUCCESS and response_buf[0] == CMD_HEAD and response_buf[7] == CMD_TAIL:
        return True
    else:
        return False


# ***************************************************************************
# Prufen ob user ID ist zwischen 1 und 3
# ***************************************************************************/
def IsMasterUser(user_id):
    if user_id == 1 or user_id == 2 or user_id == 3:
        return True
    else:
        return False


# ***************************************************************************
# Fingerabdruck pruefen
# ***************************************************************************
def VerifyUser():
    global name
    global response_buf
    sleep(0.25)
    command_buf = [CMD_MATCH, 0x00, 0x00, 0x00, 0x00]
    r = TxAndRxCmd(command_buf, 8, 5)
    if r == ACK_TIMEOUT:
        return ACK_TIMEOUT
    elif r == ACK_SUCCESS and IsMasterUser(response_buf[4]) == True:
        name = username(response_buf[3])
        return ACK_SUCCESS
    elif response_buf[4] == ACK_NO_USER:
        return ACK_NO_USER
    elif response_buf[4] == ACK_TIMEOUT:
        return ACK_TIMEOUT
    else:
        return ACK_GO_OUT


def StartVerify():
    global sens
    global name
    global status
    global s
    sleep(0.25)
    Finger_RST_Pin.value(1)  # Starte Modul
    if sens == False:
        sens = GetSensorStatus()  # Warte auf Modul start
    if sens == True:
        sleep(1.5)
        r = VerifyUser()
        print(r)
        if r == ACK_SUCCESS:
            Finger_RST_Pin.value(0)
            sens = False
            showdisplay('Welcome', name, 35, 30)
            OpenDoor()
            status = 'Door opened!'
            print("Welcome " + name)
        elif r == ACK_NO_USER:
            status = fail_messages[0]
            showdisplay('Warning', status, 35, 5)
            print(status)
            Finger_RST_Pin.value(0)
            sens = False
            LedError()
        elif r == ACK_TIMEOUT:
            status = fail_messages[1]
            showdisplay('Warning', status, 35, 5)
            print(status)
            Finger_RST_Pin.value(0)
            sens = False
            LedError()
        elif r == ACK_GO_OUT:
            status = fail_messages[2]
            showdisplay('Warning', status, 35, 42)
            print(status)
            Finger_RST_Pin.value(0)
            sens = False
            LedError()
    sleep(0.5)
    Finger_RST_Pin.value(0)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('', 80))
        s.listen(5)
    except OSError as e:
        print(e)


showdisplay('Family', 'Family name', 35, 20)
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(('', 80))
s.listen(5)

while True:
    # print('OK')
    if interrupt_activ == True:
        # print('Just in IF')
        StartVerify()
        interrupt_activ = False
        showdisplay('Family', 'Family Name', 35, 20)
        try:
            print('Try1')
            conn, addr = s.accept()
            print('Got a connection from %s' % str(addr))
            # request = conn.recv(1024)
            # print('Content = %s' % str(request))
            response = web_page()
            conn.send(response)
            conn.close()
        except OSError as e:
            print(e)
    else:
        try:
            # print('Try2')
            conn, addr = s.accept()
            print('Got a connection from %s' % str(addr))
            # request = conn.recv(1024)
            # print('Content = %s' % str(request))
            response = web_page()
            conn.send(response)
            conn.close()
        except OSError as e:
            print(e)
