# SSOL-Weather-Sensors

This project has been purposed to connect to industry standard weather sensors.

The first part of this task was to understand what communication protocol is used to connect to these sensors
to then extract data from it.

Serial Communication: MODBUS RS-485

Hardware:
- RaspberryPi 4 or 5
- RS-485 / CAN Hatboard
- External DC Power Supply (~10-30 V)

In order to achieve the MODBUS communication between the RaspberryPi and the weather sensor, use the following library:
MinimalModbus --> https://minimalmodbus.readthedocs.io/en/stable/readme.html

Other documentaion can be found at this link:
Weather Sensors Datasheets/Documentation --> https://drive.google.com/drive/u/1/folders/1Py-3WYEePmtlyG_yQctw7KpAPdwBNnvp
  * If you cannot access this link, please request access to <b>coordinator_uw@avelaccess.org</b>*

