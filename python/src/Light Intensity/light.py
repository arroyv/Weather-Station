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

# Function to read light intensity
def read_light_intensity():
    try:
        # Read light intensity from register 0x0006
        light_intensity = instrument.read_register(0x0006, 0)  # No decimals, unsigned
        print(f"Light Intensity: {light_intensity} Lux")

    except IOError:
        print("Failed to read from instrument")

# Continuously read and display light intensity
while True:
    read_light_intensity()
    time.sleep(2)  # Delay between readings
