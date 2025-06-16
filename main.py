from file_initializer import FileInitializer
from backend import Backend
from frontend import Frontend
from digikey_api_local import Digikey_API_Call
from ledSerial import LedController


initializer = FileInitializer()
initializer.initialize_files()

if __name__ == "__main__":
    digikeyAPI = Digikey_API_Call()
    ledControl  = LedController()

    backend = Backend(ledControl)

    Frontend(backend, digikeyAPI, ledControl)