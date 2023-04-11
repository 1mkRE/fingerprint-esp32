import machine
from machine import Pin, I2C
from machine import UART
from time import sleep
from time import time
import ssd1306
import onewire, ds18x20
import _thread as th

uart = UART(2, 19200, bits=8, parity=None, stop=1, tx=17, rx= 16, timeout=2000) 

i2c = I2C(scl=Pin(22), sda=Pin(21), freq=10000)

display = ssd1306.SSD1306_I2C(128, 64, i2c)

dat = Pin(4)

ds_sensor = ds18x20.DS18X20(onewire.OneWire(dat))

Finger_WAKE_Pin = Pin(34, Pin.IN)
Post_Status = Pin(39, Pin.IN)
Door_Status = Pin(36, Pin.IN)
Bell_1st_Floor = Pin(18, Pin.IN)
Bell_2nd_Floor = Pin(19, Pin.IN)
Finger_RST_Pin = Pin(13, Pin.OUT)
Esp32_Status_Led = Pin(2, Pin.OUT)
Relais_Door = Pin(25, Pin.OUT)
Relais_1st_Floor = Pin(26, Pin.OUT)
Relais_2nd_Floor = Pin(27, Pin.OUT)
Relais_Move = Pin(14, Pin.OUT)
ErrorLed = Pin(33, Pin.OUT)
StatusLed = Pin(32, Pin.OUT)

# Antwort nummern festlegung
ACK_SUCCESS           = 0x00
ACK_FAIL              = 0x01
ACK_FULL              = 0x04
ACK_NO_USER           = 0x05
ACK_TIMEOUT           = 0x08
ACK_GO_OUT            = 0x0F 

# Kommando festlegung
CMD_HEAD              = 0xF5
CMD_TAIL              = 0xF5
CMD_MATCH             = 0x0C
CMD_USER_CNT          = 0x09

response_buf = []

interrupt_activ = False
sens = False
door_counter = 0
name = ''
status = ''                                 
fail_messages = ['Neregistrovan!','Time Out chyba!','Chyba']
temp = ''
Door = ''
Post = ''

#***************************************************************************
# Access Point
#***************************************************************************/

try:
  import usocket as socket
except:
  import socket

import network

import esp
esp.osdebug(None)

import gc
gc.collect()

ssid = 'Home'
password = 'matrix1402'
value = True
s = None

ap = network.WLAN(network.AP_IF)
ap.active(True)
ap.config(essid=ssid, password=password)

while ap.active() == False:
  pass

print('Connection successful')
print(ap.ifconfig())

def web_page():
  
  html = """<html><head><title>Security System Web Server</title>
   <meta name="viewport" content="width=device-width, initial-scale=1">
   <meta charset="UTF-8">
   <meta name="description" content="Security System Web Server">
   <meta name="keywords" content="HTML">
   <meta name="author" content="Matthias Krawczynski">
   <link rel="icon" href="data:,">
   <style>
   body { text-align: center; font-family: "Trebuchet MS", Arial;}

   table { border-collapse: collapse; width:35%; margin-left:auto; margin-right:auto; }
   th { padding: 12px; background-color: #554f4a; color: white; }
   tr { border: 5px solid #ddd; padding: 12px; }
   td { border: none; padding: 12px; }
   .sensor { color:white; font-weight: bold; background-color: #bcbcbc; padding: 1px;}
   </style>
   </head>

   <body>
   <h1><b>Security system</b></h1>
   <table>
    <tr>
      <th>U啪ivatelsk茅 informace</th>
      <th>Detail</th>
    </tr>
    <tr>
      <td><b>Posledn铆 n谩v拧t臎vn铆k:</b></td>
      <td><span class="sensor">""" + name + """</span></td>
    </tr>
    <tr>
      <td><b>Posledn铆 zaznamen谩na ud谩lost:</b></td>
      <td><span class="sensor">""" + status + """</span></td></tr>
    </table> 
    <table>
    <tr>
      <th>Obecne informace</th>
      <th>Detail</th>
    </tr>
    <tr>
      <td><b>Stav dve艡铆:</b></td>
      <td><span class="sensor">""" + Door + """</span></td>
    </tr>
    <tr>
      <td><b>Stav po拧tovn铆 schr谩nka:</b></td>
      <td><span class="sensor">""" + Post + """</span></td></tr>
    <tr>
      <td><b>Teplota za艡铆zen铆:</b>
      </td><td><span class="sensor">""" + temp + """ 掳C</span></td>
    </tr>
   </table>  
   </body>
   </html>"""
  return html

#***************************************************************************
# Verschiedene Funktionen
#***************************************************************************/

def OpenSocket():
  global s
  try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    s.bind(('', 80))
    s.listen(5)
  except OSError as e:
    print(e)

def InterruptDoorOpen(pin34):
  global interrupt_activ
  interrupt_activ = True
  connection_close()
  
def Bell(floor):
  if floor == 1:
    showdisplay('Zvoni', 'Prvni patro',44, 20)
    Relais_1st_Floor.value(1)
    sleep(2)
    Relais_1st_Floor.value(0)
  elif floor == 2:
    showdisplay('Zvoni', 'Druhe patro',44, 20)
    Relais_2nd_Floor.value(1)
    sleep(2)
    Relais_2nd_Floor.value(0)
  else:
    pass
  
def ReadTemp():
  global temp
  global ds_addr
  ds_sensor.convert_temp()
  sleep(0.75)
  temp = str(round(ds_sensor.read_temp(roms[0]),2))
  
def ReadInputs():
  global Door
  global Post
  if Door_Status.value() == 1:
    Door='Zav艡eno'
  else:
    Door='Otev艡eno'
    
  if Post_Status.value() == 1:
    Post='Po拧tovn铆 schr谩nka pr谩zdn谩'
  else:
    Post='Nova po拧ta ve schr谩nce'
  
Finger_WAKE_Pin.irq(trigger=Pin.IRQ_RISING, handler=InterruptDoorOpen)

def showdisplay(head,main,head_offset, main_offset):
  display.fill(0)
  display.text(head, head_offset, 20)
  display.text(main, main_offset, 30)
  display.show()

def LedError():
  ErrorLed.value(0)
  sleep(0.25)
  ErrorLed.value(1)
  sleep(0.25)
  ErrorLed.value(0)
  sleep(0.25)
  ErrorLed.value(1)  

def OpenDoor(event):
  if event == 0:
    StatusLed.value(0)
    Relais_Door.value(1)
    sleep(5)
    StatusLed.value(1)
    Relais_Door.value(0)
  elif event == 1:
    ErrorLed.value(0)
    sleep(2)
    ErrorLed.value(1)
  else:
    pass
    
def username(usernumber):
  user_name = ['Default', 'Matthias', 'Kamila', 'Andreas', 'Kaja' , 'Elias' , 'Ester']
  if usernumber > 0 and usernumber < 7:
    return user_name[usernumber]
  else:
    return user_name[0]
  
def connection_close():
  global s
  if s:
    s.close()

#***************************************************************************
# Thread Funktionen
#***************************************************************************/

def BellRinging():
  while True:
    if Bell_1st_Floor.value():
      sleep(0.5)
      if Bell_1st_Floor.value():
        Bell(1)
        showdisplay('Rodina','Krawczynski',38, 20)
  
    if Bell_2nd_Floor.value():
      sleep(0.5)
      if Bell_2nd_Floor.value():
        Bell(2)
        showdisplay('Rodina','Krawczynski',38, 20)
  
def Finger():
  global interrupt_activ
  global s
  while True:  
    if interrupt_activ == True:
      StartVerify()    
      interrupt_activ = False
      showdisplay('Rodina','Krawczynski',38, 20)
    else:
      pass
  
    try:
      conn, addr = s.accept()  
      ReadTemp()
      ReadInputs()
      response = web_page()
      conn.send(response)
      conn.close()
    except OSError as e:
      print(e)

#***************************************************************************
# Kommando senden und auf Modul Antwort warten
#***************************************************************************/
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
  return  ACK_SUCCESS;

#***************************************************************************
# Prufen ob Modul korrekt gestartet ist
#***************************************************************************/
def GetSensorStatus():
  global response_buf
  command_buf = [CMD_USER_CNT, 0, 0, 0, 0]
  r = TxAndRxCmd(command_buf, 8, 5)
  if r == ACK_SUCCESS and response_buf[0] == CMD_HEAD and response_buf[7] == CMD_TAIL:
    return True
  else:
    return False
    
#***************************************************************************
# Prufen ob user ID ist zwischen 1 und 3
#***************************************************************************/         
def IsMasterUser(user_id):
  if user_id == 1 or user_id == 2 or user_id == 3: 
    return True
  else: 
    return False
 
#***************************************************************************
# Fingerabdruck pruefen
#***************************************************************************        
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
  Finger_RST_Pin.value(1) # Starte Modul
  if sens == False:
    sens = GetSensorStatus() # Warte auf Modul start
  if sens == True:
    sleep(1.5)
    r = VerifyUser()
    print(r)
    if r == ACK_SUCCESS:
      Finger_RST_Pin.value(0)
      sens = False
      showdisplay('Vitejte',name,35, 30)
      OpenDoor(0)
      status = 'Dve艡e otev艡eno'
    elif r == ACK_NO_USER:
      status = fail_messages[0]
      showdisplay('Pozor',status,38, 10)
      Finger_RST_Pin.value(0) 
      sens = False
      OpenDoor(1)
    elif r == ACK_TIMEOUT:
      status = fail_messages[1]
      showdisplay('Varovani',status,35, 5)
      Finger_RST_Pin.value(0) 
      sens = False
      LedError()
    elif r == ACK_GO_OUT:
      status = fail_messages[2]
      showdisplay('System',status,36, 38)
      Finger_RST_Pin.value(0)
      sens = False
      LedError()
    else:
      pass
  sleep(0.5)
  Finger_RST_Pin.value(0)
  OpenSocket()

ErrorLed.value(1)
StatusLed.value(1)
roms = ds_sensor.scan()
showdisplay('Rodina','Krawczynski',38, 20)
OpenSocket()

th.start_new_thread(BellRinging,())
th.start_new_thread(Finger,())

