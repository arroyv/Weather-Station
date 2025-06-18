'''
  Author: Stephany Ayala-Cerna, Vicente Arroyos
'''

import minimalmodbus
import serial
import time
import sys

# --------------------------------------------------------------------------------
# 1) LIST OF CANDIDATE PORTS
# --------------------------------------------------------------------------------
ports = ['/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyACM2', '/dev/ttyACM3']

# --------------------------------------------------------------------------------
# 2) COMMON MODBUS PARAMETERS
# --------------------------------------------------------------------------------
SLAVE_ADDRESS = 1       # default Modbus ID for RS-WS-N01-TR
BAUDRATE       = 4800   # default baud
BYTESIZE       = 8
PARITY         = serial.PARITY_NONE
STOPBITS       = 2
TIMEOUT        = 1      # seconds

# Register addresses (per spec):
REG_TEMPERATURE = 0  # signed 16-bit, tenths of °C
REG_HUMIDITY    = 1  # unsigned 16-bit, tenths of %RH

def try_open_port(port_name):
    """
    Attempt to create a minimalmodbus.Instrument on port_name and do a quick
    read of register 0 (temperature). If it succeeds, return the Instrument
    object. Otherwise, return None.
    """
    try:
        inst = minimalmodbus.Instrument(port_name, SLAVE_ADDRESS)
        inst.serial.baudrate = BAUDRATE
        inst.serial.bytesize = BYTESIZE
        inst.serial.parity   = PARITY
        inst.serial.stopbits = STOPBITS
        inst.serial.timeout  = TIMEOUT
        inst.mode = minimalmodbus.MODE_RTU

        # Try reading temperature register once as a sanity check:
        _ = inst.read_register(REG_TEMPERATURE, 0, signed=True)
        return inst

    except Exception:
        return None


def find_working_instrument(port_list):
    """
    Loop through port_list, try to open each one. Return the first working
    minimalmodbus.Instrument, or None if none succeed.
    """
    for p in port_list:
        print(f"Trying {p} ...", end=' ')
        inst = try_open_port(p)
        if inst is not None:
            print("OK")
            return inst
        else:
            print("no response")
    return None


def read_temperature(inst):
    raw = inst.read_register(REG_TEMPERATURE, 0, signed=True)
    return raw / 10.0

def read_humidity(inst):
    raw = inst.read_register(REG_HUMIDITY, 0, signed=False)
    return raw / 10.0


if __name__ == '__main__':
    print("Searching for RS-485 soil transmitter on candidate ports...")
    instrument = find_working_instrument(ports)

    if instrument is None:
        print("\nERROR: Could not find a valid Modbus device on any of:")
        for p in ports:
            print("  ", p)
        sys.exit(1)

    print("\n==> Using port:", instrument.serial.port)
    print("Starting polling loop (Ctrl+C to stop)...\n")

    try:
        while True:
            try:
                temp = read_temperature(instrument)
                rh   = read_humidity(instrument)
                timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                print(f"[{timestamp}]  Temperature: {temp:.1f} °C   Humidity: {rh:.1f} %RH")
            except IOError as e:
                print(f"IOError: {e!r}  (check wiring/baud/address)")
            except ValueError as e:
                print(f"ValueError (bad response?): {e!r}")

            time.sleep(5)

    except KeyboardInterrupt:
        print("\nPolling stopped by user.")
