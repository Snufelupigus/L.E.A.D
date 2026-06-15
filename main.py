import sys

from PyQt6.QtWidgets import QApplication

from backend import Backend
from digikey_api_local import Digikey_API_Call
from file_initializer import FileInitializer
from frontend import MainWindow

try:
    from ledSerial import LedController
except Exception:
    LedController = None


class NullLedController:
    def set_led_on(self, location_code, red, green, blue):
        return None

    def turn_off_recent(self):
        return None

    def turn_off_led(self, location_code):
        return None

    def turn_off_all(self):
        return None

    def highlight_location(self, location_code, delay_ms=50):
        return None

    def highlight_all(self, locations, stagger_ms=30):
        return None

    def is_connected(self):
        return False

    def get_status(self):
        return {
            "connected": False,
            "label": "Unavailable",
            "details": "LED controller is unavailable in this session.",
        }


def main():
    initializer = FileInitializer()
    created_config = initializer.initialize_files()

    app = QApplication(sys.argv)
    digikey_api = Digikey_API_Call(show_errors=False)
    led_controller = NullLedController()
    if LedController is not None:
        try:
            led_controller = LedController(show_errors=False)
        except Exception:
            led_controller = NullLedController()

    backend = Backend(led_controller)

    window = MainWindow(backend, digikey_api, initializer)
    window.show()
    if created_config:
        window.open_settings_dialog()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
