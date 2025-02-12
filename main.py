from backend import Backend
from frontend import Frontend
from digikey_api import Digikey_API_Call
from ledSerial import LedController

digikeyAPI = Digikey_API_Call()

ledControl = LedController()

backend = Backend()

Frontend(backend, digikeyAPI, ledControl) 