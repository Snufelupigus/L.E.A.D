import serial
import threading
import time
import json
import os
import logging
from threading import Lock

logger = logging.getLogger(__name__)

class LedController:
    def __init__(self, show_errors=True, error_reporter=None):
        self.show_errors = show_errors
        self.error_reporter = error_reporter
        self.num_leds = 104
        self.recent_leds = set()
        self._req_id = 0
        self.ser = None
        self.port = None
        self.baudrate = 9600
        self.timeout = 1
        self.last_error = ""

        # Protect set mutations across threads
        self._req_lock = threading.Lock()   # for highlight request gating
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
                baudrate = serial_config.get("BAUDRATE", "")
                timeout = serial_config.get("TIMEOUT", "")
                self.baudrate = int(baudrate) if str(baudrate).strip() else 9600
                self.timeout = int(timeout) if str(timeout).strip() else 1
        except Exception as e:
            logger.exception("Error loading config file: %s", e)
            self._show_error("Config Error", "Failed to load serial settings from config.json")
            self.port = ""
            self.baudrate = 9600
            self.timeout = 1

    def connect_serial(self):
        """Establish serial connection with LED controller"""
        try:
            if self.ser is not None:
                try:
                    self.ser.close()
                except Exception:
                    pass
                self.ser = None
            if not self.port:
                raise ValueError("Serial port not defined in config.json")
            self.ser = serial.Serial(port=self.port, baudrate=self.baudrate, timeout=self.timeout)
            time.sleep(0.5)  # Let Arduino initialize
            self.turn_off_all()
            self.last_error = ""
        except Exception as e:
            logger.warning("Error opening serial port: %s", e)
            self.last_error = str(e)
            self._show_error("LED System Error", "LED Controller Failed To Load")
            self.ser = None

    def _show_error(self, title, message):
        if self.show_errors and self.error_reporter:
            self.error_reporter(title, message)

    def _handle_serial_error(self, error):
        self.last_error = str(error)
        try:
            if self.ser is not None:
                self.ser.close()
        except Exception:
            pass
        self.ser = None
        with self._lock:
            self.recent_leds.clear()

    def _write_command(self, command):
        if self.ser is None:
            return False
        try:
            self.ser.write(command)
            return True
        except Exception as error:
            logger.warning("LED controller write failed: %s", error)
            self._handle_serial_error(error)
            return False

    def _flush_serial(self):
        if self.ser is None:
            return False
        try:
            self.ser.flush()
            return True
        except Exception as error:
            logger.warning("LED controller flush failed: %s", error)
            self._handle_serial_error(error)
            return False

    def is_connected(self):
        return bool(self.ser is not None and getattr(self.ser, "is_open", True))

    def get_status(self):
        if self.is_connected():
            return {
                "connected": True,
                "label": "Connected",
                "details": f"LED controller connected on {self.port} at {self.baudrate} baud.",
            }

        if self.port:
            detail = f"LED controller is not connected. Configured port: {self.port}."
        else:
            detail = "LED controller is not connected. No serial port is configured."

        if self.last_error:
            detail = f"{detail} Last error: {self.last_error}"

        return {
            "connected": False,
            "label": "Disconnected",
            "details": detail,
        }

    def reconnect(self):
        logger.info("Attempting to reconnect to LED controller...")
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
        if not self._write_command(cmd):
            return
        if not self._flush_serial():
            return
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
            if not self._write_command(cmd):
                return
            time.sleep(0.005)
        self._flush_serial()

    def turn_off_all(self):
        """Turns off every LED, with a tiny delay to ensure no commands get dropped."""
        if self.ser is None:
            return

        for i in range(self.num_leds):
            cmd = f"SET {i} 0 0 0\n".encode('utf-8')
            if not self._write_command(cmd):
                return
            time.sleep(0.05)    # staggered write
        if not self._flush_serial():
            return
        with self._lock:
            self.recent_leds.clear()

    def turn_off_led(self, location_code):
        index = self.location_to_index(location_code)
        if index is None or self.ser is None:
            return
        cmd = f"SET {index} 0 0 0\n".encode('utf-8')
        if not self._write_command(cmd):
            return
        if not self._flush_serial():
            return
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
                if not self._write_command(f"SET {index} 0 0 0\n".encode('utf-8')):
                    return
                self.recent_leds.discard(index)
        self._flush_serial()

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
