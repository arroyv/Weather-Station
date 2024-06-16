'''
  Author: Stephany Ayala-Cerna
  
  modbus.py is a basic python script that shows how to use modbus to communicate with MODBUS RS-485 enabled 
  sensors.

  Library MinimalModbus --> https://minimalmodbus.readthedocs.io/en/stable/apiminimalmodbus.html

  For each sensor:
  Default Baudrate: 4800
    Other options: 2400, 9600
    
  Byte size: 8 
  Parity: None
  Stop Bit: 1
  MODE: RTU

  Use the information above to setup the sensor communication. An example of the set up can be below.

  Use the data sheet to find what registers are used to extract values from. Also find out the conversion value 
  after the raw data has been extracted.
  - An example of extracting values from registers can be seen towards the end of the script
'''

import minimalmodbus

mb_address = 1

sensor = minimalmodbus.Instrument('/dev/ttyS0', mb_address)

sensor.serial.baudrate = 4800
sensor.serial.bytesize = 8
sensor.serial.parity = minimalmodbus.serial.PARITY_NONE
sensor.serial.stopbits = 1
sensor.serial.timeout = 0.5
sensor.mode = minimalmodbus.MODE_RTU

print("")
print("Requesting Data From Sensor...")

# Example of SINGLE Registers:
# sensor.read_registers(REGISTER ADDRESS, NUMBER OF DECIMALS, FUNCTION CODE, IS VALUE SIGNED OR UNSIGNED (TRUE OR FASLSE))

# Example of MULTIPLE Registers
# sensor.read_registers(REGISTER START ADDRESS, NUMBER OF REGISTERS TO READ, FUNCTION CODE)

data =  sensor.read_registers(0,1,3) # Starts at register 0 and reads 1 register using function code 3
print(f"Raw Data is {data}")


