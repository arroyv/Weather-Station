'''    
    Author: Stephany Ayala-Cerna, Vicente Arroyos
'''
import minimalmodbus
import time

# Configure the instrument
instrument = minimalmodbus.Instrument('/dev/ttyACM0', 1)  # Replace with your serial port and address
instrument.serial.baudrate = 4800  # Default baudrate from the document
instrument.serial.bytesize = 8
instrument.serial.parity = minimalmodbus.serial.PARITY_NONE
instrument.serial.stopbits = 1
instrument.serial.timeout = 1  # seconds

# Function to read pressure and temperature
def read_pressure_and_temperature():
    try:
        # Read atmospheric pressure from register 0x0000
        pressure = instrument.read_register(0x0000, 1)  # 1 decimals, unsigned
        print(f"Atmospheric Pressure: {pressure} Kpa")

        # Read temperature from register 0x0001 (signed value)
        temperature = instrument.read_register(0x0001, 1, signed=True)  # 1 decimals, signed=True
        print(f"Temperature: {temperature} °C")

    except IOError:
        print("Failed to read from instrument")

# Continuously read and display pressure and temperature
while True:
    read_pressure_and_temperature()
    time.sleep(2)  # Delay between readings

