import serial
import time
import json
import os
from tkinter import messagebox

class LedController:
    def __init__(self):
        self.num_leds = 104
        self.recent_leds = set()
        self.ser = None
        self.port = None
        self.baudrate = 9600
        self.timeout = 1

        self.load_config()
        self.connect_serial()

    def load_config(self):
        """Load serial config from config.json"""
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
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

    def set_led_on(self, location_code, red, green, blue):
        index = self.location_to_index(location_code)
        if index is None or self.ser is None:
            return
        command = f"SET {index} {red} {green} {blue}\n"
        self.ser.write(command.encode('utf-8'))
        self.recent_leds.add(index)

    def turn_off_recent(self):
        if self.ser is None:
            return
        for index in self.recent_leds:
            self.ser.write(f"SET {index} 0 0 0\n".encode('utf-8'))
        self.ser.flush()
        self.recent_leds.clear()

    def turn_off_all(self):
        if self.ser is None:
            return
        for i in range(self.num_leds):
            self.ser.write(f"SET {i} 0 0 0\n".encode('utf-8'))
        self.ser.flush()

    def turn_off_led(self, location_code):
        index = self.location_to_index(location_code)
        if index is None or self.ser is None:
            return
        self.ser.write(f"SET {index} 0 0 0\n".encode('utf-8'))
        self.ser.flush()
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
