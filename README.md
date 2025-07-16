# Weather-Station

This project provides a comprehensive, Raspberry Pi-based weather station platform for collecting, storing, transmitting, and visualizing environmental data from various sensors. It is designed to be modular and highly configurable for different deployment scenarios, such as in a greenhouse or an open field.

---

### ## Key Features

-   [cite_start]**Multi-Sensor Support:** Interfaces with Modbus sensors (for metrics like temperature, humidity, CO2, pressure, wind) and GPIO-based sensors (for rain gauges)[cite: 90, 192].
-   [cite_start]**Wireless Communication:** Built-in LoRa support allows for robust, long-range data transmission between a central base station and multiple remote sensor nodes[cite: 372].
-   [cite_start]**Web Dashboard:** A built-in Flask web server provides a real-time dashboard to view data from all stations in the network and a settings page to manage the station's configuration[cite: 271, 310].
-   [cite_start]**Cloud Integration:** Automatically uploads the latest sensor data to Adafruit IO for historical logging, graphing, and remote monitoring[cite: 351, 359].
-   [cite_start]**Resilient and Dynamic:** The system runs multiple processes in parallel using threading[cite: 137, 347, 380]. [cite_start]It also supports live configuration updates without requiring a restart.
-   [cite_start]**Local Data Storage:** All readings are stored in a local SQLite database, ensuring no data is lost if network connectivity fails[cite: 424, 444].

---

### ## Installation

#### **Prerequisites**
-   A Raspberry Pi (3, 4, or 5 recommended).
-   Python 3 and `git`.
-   Required hardware: USB-to-RS485 adapter, LoRa module (RFM9x), and sensors.

#### **Setup Instructions**

1.  **Grant Hardware Access:**
    Add your user to the `dialout` and `gpio` groups to access serial and GPIO pins. **You must log out and back in** for this to apply.
    ```bash
    sudo usermod -a -G dialout,gpio $USER
    ```

2.  **Clone the Repository:**
    ```bash
    git clone <your-repository-url>
    cd weather-station
    ```

3.  **Create and Activate a Python Virtual Environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

4.  **Install Required Libraries:**
    ```bash
    pip install -r requirements.txt
    ```

5.  **Set Up Environment Variables:**
    [cite_start]If using Adafruit IO, create a `.env` file and add your credentials[cite: 330].
    ```
    # .env
    ADAFRUIT_IO_USERNAME="your_aio_username"
    ADAFRUIT_IO_KEY="your_aio_key"
    ```

6.  **Configure the Station:**
    Open `config.json` and customize it for your needs. At a minimum, you should:
    -   Set a unique `station_id` and `station_name`.
    -   Set the LoRa `role` to `"base"` or `"remote"`.
    -   Enable your specific sensors and services (`lora_enabled`, `adafruit_io_enabled`).

---

### ## Usage

1.  **Start the Application:**
    Run the main script from the project's root directory.
    ```bash
    python run_weather_station.py
    ```
    You can override settings from `config.json` with command-line arguments:
    ```bash
    # Example: Start a remote station with ID 10
    python run_weather_station.py --role remote --id 10
    ```

2.  **Access the Web Dashboard:**
    Open a browser and go to `http://<your_pi_ip_address>:5000`.

---

### ## Troubleshooting

-   **Permission Errors:** Ensure you have run the `usermod` command and have logged out and back in.
-   **No Sensor Data:** Double-check your sensor wiring (Power, Ground, RS485 A/B lines) and verify that the Modbus addresses in `config.json` match the physical addresses of your sensors.
-   **Web App Not Loading:** Make sure the script is running and that your Raspberry Pi is connected to the same network as your computer.