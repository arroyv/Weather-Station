'''
  Author: Stephany Ayala-Cerna, Vicente Arroyos
'''

import minimalmodbus
import time

# Configure the instrumentcd 
instrument = minimalmodbus.Instrument('/dev/ttyACM0', 1)  # Replace with your serial port and address
instrument.serial.baudrate = 4800  # Default baudrate from the document
instrument.serial.bytesize = 8
instrument.serial.parity = minimalmodbus.serial.PARITY_NONE
instrument.serial.stopbits = 1
instrument.serial.timeout = 1  # seconds

# Function to read CO2 concentration
def read_co2_concentration():
    try:
        # Read CO2 concentration from register 0x0002
        co2_concentration = instrument.read_register(0x0002, 0)  # No decimals, unsigned
        print(f"CO2 Concentration: {co2_concentration} ppm")

    except IOError:
        print("Failed to read from instrument")

# Continuously read and display CO2 concentration
while True:
    read_co2_concentration()
    time.sleep(2)  # Delay between readings
