from backend import Backend
from frontend import Frontend
from digikey_api import Digikey_API_Call
from ledSerial import LedController

if __name__ == "__main__":
    digikeyAPI = Digikey_API_Call()
    ledControl  = LedController()

    backend = Backend(ledControl)

    Frontend(backend, digikeyAPI, ledControl)