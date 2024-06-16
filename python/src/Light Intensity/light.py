'''
  Author: Stephany Ayala-Cerna
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

# sensor.clear_buffers_before_each_transaction = True
# sensor.close_port_after_each_call = True

print("")
print("Requesting Data From Sensor...")


# Example of SINGLE Registers:
# sensor.read_register(REGISTER ADDRESS, NUMBER OF DECIMALS, FUNCTION CODE, IS VALUE SIGNED OR UNSIGNED (TRUE OR FASLSE))

# Example of MULTIPLE Registers
# sensor.read_registers(REGISTER START ADDRESS, NUMBER OF REGISTERS TO READ, FUNCTION CODE)

while (1):
    data =  sensor.read_register(6, 0, 3, False)
    # print(f"Raw Data is {data}")
    print(f"Light Intensity: {data} Lux")





