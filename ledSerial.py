import serial
import threading
import time
import json
import os
from tkinter import messagebox
from threading import Lock

class LedController:
    def __init__(self):
        self.num_leds = 104
        self.recent_leds = set()
        self._req_id = 0
        self.ser = None
        self.port = None
        self.baudrate = 9600
        self.timeout = 1

        # Protect set mutations across threads
        self._req_lock = threading.Lock()   # for highlight request gating
        self._led_lock = threading.Lock()
        self._lock = Lock()

        self.load_config()
        self.connect_serial()

    def load_config(self):
        """Load serial config from config.json"""
        config_path = os.path.join(os.path.dirname(__file__), "Databases", "config.json")
        try:
            with open(config_path, "r") as file:
                config = json.load(file)
                serial_config = config.get("SERIAL", {})
                self.port = serial_config.get("PORT", "")
                self.baudrate = serial_config.get("BAUDRATE", 9600)
                self.timeout = serial_config.get("TIMEOUT", 1)
        except Exception as e:
            print(f"Error loading config file: {e}")
            messagebox.showerror("Config Error", "Failed to load serial settings from config.json")

    def connect_serial(self):
        """Establish serial connection with LED controller"""
        try:
            if not self.port:
                raise ValueError("Serial port not defined in config.json")
            self.ser = serial.Serial(port=self.port, baudrate=self.baudrate, timeout=self.timeout)
            time.sleep(0.5)  # Let Arduino initialize
            self.turn_off_all()
        except Exception as e:
            print(f"Error opening serial port: {e}")
            messagebox.showerror("LED System Error", "LED Controller Failed To Load")
            self.ser = None

    def reconnect(self):
        print("Attempting to reconnect to LED controller...")
        self.connect_serial()

    def location_to_index(self, location_code):
        if not location_code:
            return None
        row_part = ''.join(filter(str.isdigit, location_code))
        col_part = ''.join(filter(str.isalpha, location_code)).upper()
        try:
            row = int(row_part)
        except ValueError:
            return None
        if not col_part or len(col_part) != 1:
            return None
        if row % 2 == 0:
            col_index = 25 - (ord(col_part) - ord('A'))
        else:
            col_index = ord(col_part) - ord('A')
        return (row - 1) * 26 + col_index
    
    def _compute_color(self, location_code):
        """Return (r,g,b): odd-letter → green, even-letter → blue."""
        if not location_code:
            return (0,0,0)
        letter = location_code[-1].upper()
        idx = ord(letter) - ord('A') + 1
        return (0,255,0) if (idx % 2) else (0,0,255)

    def set_led_on(self, location_code, red, green, blue):
        index = self.location_to_index(location_code)
        if index is None or self.ser is None:
            return
        cmd = f"SET {index} {red} {green} {blue}\n".encode('utf-8')
        self.ser.write(cmd)
        self.ser.flush()
        with self._lock:
            self.recent_leds.add(index)

    def turn_off_recent(self):
        """Turns off just the LEDs we've lit since the last clear."""
        if self.ser is None:
            return

        # snapshot to avoid "set changed size" errors
        with self._lock:
            leds = list(self.recent_leds)
            self.recent_leds.clear()

        for index in leds:
            cmd = f"SET {index} 0 0 0\n".encode('utf-8')
            self.ser.write(cmd)
            time.sleep(0.005)
        self.ser.flush()

    def turn_off_all(self):
        """Turns off every LED, with a tiny delay to ensure no commands get dropped."""
        if self.ser is None:
            return

        for i in range(self.num_leds):
            cmd = f"SET {i} 0 0 0\n".encode('utf-8')
            self.ser.write(cmd)
            time.sleep(0.05)    # staggered write
        self.ser.flush()
        with self._lock:
            self.recent_leds.clear()

    def turn_off_led(self, location_code):
        index = self.location_to_index(location_code)
        if index is None or self.ser is None:
            return
        cmd = f"SET {index} 0 0 0\n".encode('utf-8')
        self.ser.write(cmd)
        self.ser.flush()
        with self._lock:
            self.recent_leds.discard(index)

    def turn_off_bom_leds(self, bom_list, led_controller):
        locations = {row.get("location") for row in bom_list if row.get("found") and row.get("location")}
        for location in locations:
            time.sleep(0.05)
            led_controller.turn_off_led(location)

    def turn_off_all_assigned_leds(self, backend):
        assigned_locations = backend.get_assigned_locations()
        if self.ser is None:
            return
        for loc in assigned_locations:
            time.sleep(0.05)
            index = self.location_to_index(loc)
            if index is not None:
                self.ser.write(f"SET {index} 0 0 0\n".encode('utf-8'))
                self.recent_leds.discard(index)
        self.ser.flush()

    def highlight_location(self, location_code, delay_ms=50):
        """
        Immediately turn off previous LEDs, then after delay_ms,
        light this one—unless a newer request has arrived.
        """
        # bump request counter
        with self._req_lock:
            self._req_id += 1
            my_id = self._req_id

        # synchronous turn‑off
        self.turn_off_recent()

        def job():
            time.sleep(delay_ms / 1000.0)
            # only proceed if still latest request
            with self._req_lock:
                if my_id != self._req_id:
                    return
            r, g, b = self._compute_color(location_code)
            self.set_led_on(location_code, r, g, b)

        threading.Thread(target=job, daemon=True).start()

    def highlight_all(self, locations, stagger_ms=30):
        """
        Light all given locations in their odd/even color, staggered
        so the controller has time to process each.
        `locations` can be a list of location codes.
        """
        for i, loc in enumerate(locations):
            def job(loc=loc):
                time.sleep((stagger_ms * i) / 1000.0)
                r, g, b = self._compute_color(loc)
                self.set_led_on(loc, r, g, b)
            threading.Thread(target=job, daemon=True).start()