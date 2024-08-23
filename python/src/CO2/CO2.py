# '''
#   Author: Stephany Ayala-Cerna, Vicente Arroyos
# '''

# import minimalmodbus

# mb_address = 1

# sensor = minimalmodbus.Instrument('/dev/ttyS0', mb_address)

# sensor.serial.baudrate = 4800
# sensor.serial.bytesize = 8
# sensor.serial.parity = minimalmodbus.serial.PARITY_NONE
# sensor.serial.stopbits = 1
# sensor.serial.timeout = 0.5
# sensor.mode = minimalmodbus.MODE_RTU

# # sensor.clear_buffers_before_each_transaction = True
# # sensor.close_port_after_each_call = True

# print("")
# print("Requesting Data From Sensor...")


# # Example of SINGLE Registers:
# # sensor.read_register(REGISTER ADDRESS, NUMBER OF DECIMALS, FUNCTION CODE, IS VALUE SIGNED OR UNSIGNED (TRUE OR FASLSE))

# # Example of MULTIPLE Registers
# # sensor.read_registers(REGISTER START ADDRESS, NUMBER OF REGISTERS TO READ, FUNCTION CODE)

# data =  sensor.read_register(0,3,3,False)
# # print(f"Raw Data is {data}")
# print(f"CO2 Concentration {data} ppm")

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
