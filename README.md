# SSOL-Weather-Sensors

## Overview

This project enables monitoring of environmental conditions using a Raspberry Pi 5 connected to MODBUS sensors via a USB-to-4CH RS485 interface. The system collects data such as temperature, humidity, CO2 levels, wind direction, and speed, and then logs it to Adafruit IO or prints it to the terminal.

## Hardware Requirements

- **Raspberry Pi 5**
- **USB-to-4CH RS485 Interface** (utilizes `/dev/ttyAMA` ports for MODBUS communication)
- **MODBUS-compatible sensors**:
  - Atmospheric pressure and temperature
  - Atmospheric temperature and humidity
  - CO2 concentration
  - Light intensity
  - Wind direction and speed
- **Power Supply**: Ensure sensors are powered as per manufacturer specifications.
- External DC Power Supply (~10–30 V)

## Software Requirements

- **Python**: Ensure Python 3 is installed.
- **MinimalModbus Library**: For MODBUS communication.
- **Adafruit IO Python Library**: For cloud-based logging.

### Environment Setup

1. **Create and Activate Python Virtual Environment**
   ```bash
   sudo apt update
   sudo apt install python3-venv -y
   python3 -m venv weather_station_env
   source weather_station_env/bin/activate

2. **Install Required Libraries**
   ```bash
   pip install minimalmodbus Adafruit_IO

## Code Details

### 1. Main Components

- **weather_station.py**: Contains the base `Sensor` class and specialized classes for each sensor type (e.g., `AtmosphericPressureSensor`, `CO2Sensor`).
- **run_weather_station.py**: Discovers connected sensors and manages their data collection and logging.
- **Individual sensor scripts**:  
  - `atmospheric.py` (pressure and temperature)  
  - `atmospheric_T_H.py` (humidity and temperature)  
  - `CO2.py` (CO2 concentration)  
  - `light.py` (light intensity)  
  - `Wind_direction.py` (wind direction)  
  - `Wspeed.py` (wind speed)  

### 2. Key Features

- Configurable polling rates and logging to Adafruit IO.
- Shared port locking for multiple sensors.
- Support for `/dev/ttyAMA` ports on Raspberry Pi 5.

## Running the Code

### Running Individual Sensor Scripts

1. Edit the serial port in each script to match the connected device (e.g., `/dev/ttyAMA0`):
   
   ```bash
   python atmospheric.py

**Output example:**
- Atmospheric Pressure: 101.5 Kpa  
- Temperature: 25.0 °C

**Running the Weather Station**
1. Update Adafruit IO credentials in `run_weather_station.py`:
   ```python
   ADAFRUIT_IO_USERNAME = "your_username"
   ADAFRUIT_IO_KEY = "your_key"

# Instructions

## Setup

1. **Connect all sensors** and run the script:
   ```bash
   python run_weather_station.py

The script discovers connected sensors and starts collecting and logging data.

## Troubleshooting

### No Response from Sensors
- Check the serial port and MODBUS address in the script.
- Verify power connections.

### Permission Errors
- Add the current user to the dialout group:
  ```bash
  sudo usermod -a -G dialout $USER

## Data Errors

- Validate register addresses and MODBUS parameters in the sensor documentation.
- Use debugging flags (`debug=True`) for detailed logs.

## MODBUS Communication

To achieve MODBUS communication between the Raspberry Pi and the weather sensor, use the following library:

- [MinimalModbus](https://minimalmodbus.readthedocs.io/en/stable/readme.html)

## Additional Documentation

Further documentation can be found at:

- [Weather Sensors Datasheets/Documentation](https://drive.google.com/drive/u/1/folders/1Py-3WYEePmtlyG_yQctw7KpAPdwBNnvp)

*If you cannot access this link, please request access from:  
**coordinator_uw@avelaccess.org**.*
