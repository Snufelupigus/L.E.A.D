import serial
import time
from tkinter import messagebox

class LedController:
    def __init__(self):
        self.num_leds = 104
        self.recent_leds = set()  # Keep track of LEDs that were turned on.
        try:
            self.ser = serial.Serial(port="COM7", baudrate=9600, timeout=1)
            time.sleep(1)  # Allow time for the Arduino to initialize
            self.turn_off_all()  # Optionally turn off all LEDs at startup.
        except Exception as e:
            print(f"Error opening serial port: {e}")
            messagebox.showerror("LED System Error", f"LED Controller Failed To Load")
            self.ser = None

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
        
        if row%2==0:
            # odd row: alphabetical order forward (A=0, B=1, ...)
            col_index = 25 - (ord(col_part) - ord('A'))
        else:
            # even row: alphabetical order reversed (A=25, B=24, ..., Z=0)
            col_index = ord(col_part) - ord('A')
        
        index = (row - 1) * 26 + col_index
        return index

    def set_led_on(self, location_code, red, green, blue):
        index = self.location_to_index(location_code)
        if index is None or self.ser is None:
            return
        command = f"SET {index} {red} {green} {blue}\n"
        self.ser.write(command.encode('utf-8'))
        # Record this LED index as recently referenced.
        self.recent_leds.add(index)

    def turn_off_recent(self):
        if self.ser is None:
            return
        for index in self.recent_leds:
            command = f"SET {index} 0 0 0\n"
            self.ser.write(command.encode('utf-8'))
        self.ser.flush()
        # Clear the collection after turning them off.
        self.recent_leds.clear()

    def turn_off_all(self):
        if self.ser is None:
            return
        for i in range(self.num_leds):
            command = f"SET {i} 0 0 0\n"
            self.ser.write(command.encode('utf-8'))
        self.ser.flush()
        # Optionally, clear recent_leds as well.

    def turn_off_led(self, location_code):
        index = self.location_to_index(location_code)
        if index is None or self.ser is None:
            return
        command = f"SET {index} 0 0 0\n"
        self.ser.write(command.encode('utf-8'))
        self.ser.flush()
        # Remove this LED index from the recent_leds set if it was recorded.
        if index in self.recent_leds:
            self.recent_leds.remove(index)

    def turn_off_bom_leds(self, bom_list, led_controller):
        """
        Turns off only the LEDs whose locations are present in the BOM list.
        
        Parameters:
        - bom_list: A list of dictionaries for BOM rows, each expected to contain a key "location".
        - led_controller: An instance of LedController used to send commands to the LEDs.
        """
        # Collect unique locations from BOM rows that are marked as found and have a valid location.
        locations = {row.get("location") for row in bom_list if row.get("found") and row.get("location")}
        for location in locations:
            led_controller.turn_off_led(location)
