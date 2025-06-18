'''
  Author: Stephany Ayala-Cerna, Vicente Arroyos
'''

import minimalmodbus
import time

# Configure the instrument
instrument = minimalmodbus.Instrument('/dev/ttyACM0', 6)  # Replace with your serial port and address
instrument.serial.baudrate = 4800  # Default baudrate from the document
instrument.serial.bytesize = 8
instrument.serial.parity = minimalmodbus.serial.PARITY_NONE
instrument.serial.stopbits = 1
instrument.serial.timeout = 1  # seconds

# Define a dictionary to map direction degrees to cardinal directions
direction_map = {
    0: "North",
    45: "Northeast",
    90: "East",
    135: "Southeast",
    180: "South",
    225: "Southwest",
    270: "West",
    315: "Northwest"
}

# Function to read wind direction and print the corresponding direction
def read_wind_direction():
    try:
        # Read wind direction from register 0x0001
        wind_direction_degrees = instrument.read_register(0x0001, 0)  # No decimals, unsigned

        # Get the corresponding cardinal direction
        wind_direction = direction_map.get(wind_direction_degrees, "Unknown Direction")

        # Print and store the direction
        print(f"Wind Direction: {wind_direction_degrees}° ({wind_direction})")
        return wind_direction

    except IOError:
        print("Failed to read from instrument")
        return None

# Continuously read and display wind direction
while True:
    direction = read_wind_direction()
    # You can store or use the 'direction' variable as needed
    time.sleep(2)  # Delay between readings
