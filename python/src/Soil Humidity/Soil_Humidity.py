'''
  Author: Stephany Ayala-Cerna, Vicente Arroyos
'''
#TODO figure out how to connect to soil sensor currenlty no functional

import minimalmodbus
import time

# Configure the instrument
instrument = minimalmodbus.Instrument('/dev/ttyACM0', 1)  # Replace with your serial port and address
instrument.serial.baudrate = 4800  # Default baudrate from the document
instrument.serial.bytesize = 8
instrument.serial.parity = minimalmodbus.serial.PARITY_NONE
instrument.serial.stopbits = 1
instrument.serial.timeout = 1  # seconds

# Function to read soil temperature and humidity
def read_soil_temperature_and_humidity():
    try:
        # Read soil temperature from register 0x0000
        soil_temperature = instrument.read_register(0x0000, 1, signed=True)  # 1 decimal place, signed
        print(f"Soil Temperature: {soil_temperature} °C") 
        # Read soil humidity from register 0x0001
        soil_humidity = instrument.read_register(0x0001, 1)  # 1 decimal place, unsigned
        print(f"Soil Humidity: {soil_humidity} %RH")

    except IOError:
        print("Failed to read from instrument")

# Continuously read and display soil temperature and humidity
while True:
    read_soil_temperature_and_humidity()
    time.sleep(2)  # Delay between readings
