'''
  Author: Stephany Ayala-Cerna, Vicente Arroyos
'''

import minimalmodbus
import time

# Configure the instrument
instrument = minimalmodbus.Instrument('/dev/ttyACM0', 7)  # Replace with your serial port and address
instrument.serial.baudrate = 4800  # Default baudrate from the document
instrument.serial.bytesize = 8
instrument.serial.parity = minimalmodbus.serial.PARITY_NONE
instrument.serial.stopbits = 1
instrument.serial.timeout = 1  # seconds

# Function to read wind speed
def read_wind_speed():
    try:
        # Read wind speed from register 0x0000
        wind_speed = instrument.read_register(0x0000, 1)  # 1 decimal place, unsigned
        print(f"Wind Speed: {wind_speed} m/s")

    except IOError:
        print("Failed to read from instrument")

# Continuously read and display wind speed
while True:
    read_wind_speed()
    time.sleep(2)  # Delay between readings