# '''
#   Author: Stephany Ayala-Cerna
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
import serial

# Define the instrument (replace '/dev/ttyUSB0' with the appropriate port for your setup)
instrument = minimalmodbus.Instrument('dev/ttyACM0', 1)  # Port name and slave address (default is 0x01)
instrument.serial.baudrate = 4800                         # Baudrate (default is 4800)
instrument.serial.bytesize = 8                            # Number of data bits to be requested
instrument.serial.parity   = serial.PARITY_NONE           # Parity setting
instrument.serial.stopbits = 1                            # Number of stop bits
instrument.serial.timeout  = 1                            # Timeout in seconds

instrument.mode = minimalmodbus.MODE_RTU                  # Modbus mode (RTU or ASCII)
instrument.clear_buffers_before_each_transaction = True   # Clear buffers to avoid sync issues



# Read CO2 concentration (0x0002)
co2_concentration = instrument.read_register(0x0002, 0)  # Reading as an integer (no decimals)
print(f"CO2 Concentration: {co2_concentration} ppm")

# Read Temperature (0x0000)
temperature = instrument.read_register(0x0000, 1)  # Reading as a float (1 decimal place)
print(f"Temperature: {temperature / 10.0} °C")     # The device returns temperature in tenths of a degree

# Read Humidity (0x0001)
humidity = instrument.read_register(0x0001, 1)    # Reading as a float (1 decimal place)
print(f"Humidity: {humidity / 10.0} %RH")         # The device returns humidity in tenths of a percent
