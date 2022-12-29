import machine
from machine import Pin, I2C
from machine import UART
from time import sleep
from time import time
import ssd1306

uart = UART(2, 19200, bits=8, parity=None, stop=1, tx=17, rx=16, timeout=2000)

i2c = I2C(scl=Pin(22), sda=Pin(21), freq=10000)

display = ssd1306.SSD1306_I2C(128, 64, i2c)

Finger_WAKE_Pin = Pin(34, Pin.IN)
Finger_RST_Pin = Pin(5, Pin.OUT)
led = Pin(2, Pin.OUT)


def InterruptDoorOpen(pin):
    global interrupt_activ
    interrupt_activ = True


Finger_WAKE_Pin.irq(trigger=Pin.IRQ_RISING, handler=InterruptDoorOpen)