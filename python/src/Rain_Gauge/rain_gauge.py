"""
rain_gauge.py

Counts tipping‐bucket pulses on GPIO 17 and converts to millimeters of rain.
Each pulse = 0.5 mm (per RS-05B spec) :contentReference[oaicite:1]{index=1}.
"""

import time
import RPi.GPIO as GPIO
import threading

# ==== Configuration ====
GPIO_PIN = 17           # BCM numbering for the input
MM_PER_TIP = 0.5        # 0.5 mm rainfall per bucket tip (spec) :contentReference[oaicite:2]{index=2}
DEBOUNCE_MS = 200       # Debounce time in milliseconds

# ==== Global variables ====
lock = threading.Lock()
tip_count = 0

def bucket_tipped(channel):
    """
    Callback triggered on each falling edge (bucket tip).
    Increments tip_count with basic debounce.
    """
    global tip_count, last_time

    now = time.time() * 1000  # current time in ms
    # Simple software debounce: ignore if within DEBOUNCE_MS of the last tip
    with lock:
        if now - bucket_tipped.last_time >= DEBOUNCE_MS:
            tip_count += 1
            bucket_tipped.last_time = now
            print(f"Bucket tipped! Total tips: {tip_count}")

# Initialize last_time attribute
bucket_tipped.last_time = 0

def setup_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(GPIO_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    # Detect falling edge: reed closes → pin pulled low
    GPIO.add_event_detect(GPIO_PIN,
                          GPIO.FALLING,
                          callback=bucket_tipped,
                          bouncetime=DEBOUNCE_MS)

def main():
    try:
        setup_gpio()
        print("Rain gauge monitoring started. Press Ctrl+C to exit.")
        while True:
            time.sleep(10)  # Main thread sleeps; callback handles counting

            # Optionally, every 10 seconds, print cumulative rainfall:
            with lock:
                mm_rain = tip_count * MM_PER_TIP
            print(f"Cumulative rainfall: {mm_rain:.1f} mm")

    except KeyboardInterrupt:
        print("\nTerminating...")

    finally:
        GPIO.cleanup()
        with lock:
            total_mm = tip_count * MM_PER_TIP
        print(f"Final tip count = {tip_count}, Total rainfall = {total_mm:.1f} mm")

if __name__ == "__main__":
    main()