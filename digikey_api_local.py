from image_cache import ImageCacheEntry
from datetime import datetime, timezone
import requests
import logging
logging.basicConfig(level=logging.DEBUG)
import json
import os
import time
from tkinter import messagebox, simpledialog
from dataclasses import dataclass
import webbrowser

@dataclass
class DigiKeyPackItem:
    DigiKeyPartNumber: str
    Quantity: int

class Digikey_API_Call:
    ACCESS_TOKEN: str
    def __init__(self):
        self.config_file = os.path.join(os.path.dirname(__file__), "Databases", "config.json")
        self.refresh_token_file = os.path.join(os.path.dirname(__file__), "Databases", "REFRESH_TOKEN")
        self.load_config()

    def load_config(self):
        """Loads API configuration from config.json"""
        self.ACCESS_TOKEN = None
        try:
            with open(self.config_file, "r") as file:
                config = json.load(file)

                self.CLIENT_ID = config["API"].get("DIGIKEY_CLIENT_ID", "")
                if not self.CLIENT_ID:
                    raise ValueError("Digikey Client ID is missing in config.json")
                
                self.CLIENT_SECRET = config["API"].get("DIGIKEY_CLIENT_SECRET", "")
                if not self.CLIENT_SECRET:
                    raise ValueError("Digikey Client Secret is missing in config.json")
                
        except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
            messagebox.showerror("Configuration Error", f"Failed to load config.json:\n{e}")
            self.CLIENT_ID = None
            self.CLIENT_SECRET = None

        if os.path.isfile(self.refresh_token_file):
            with open(self.refresh_token_file) as textFile:
                self.REFRESH_TOKEN = textFile.read()
        else:
            self.get_refresh_token()


    def get_refresh_token(self):

        webbrowser.open("https://api.digikey.com/v1/oauth2/authorize?response_type=code&" \
        "client_id=%s&redirect_uri=https://localhost" % (self.CLIENT_ID))

        code = simpledialog.askstring("Enter Code", "Please enter code")

        print(code)

        digiKeyAuth = {
            'code' : code,
            'client_id': self.CLIENT_ID ,
            'client_secret': self.CLIENT_SECRET,
            'redirect_uri' : "https://localhost",
            'grant_type':'authorization_code'
        }
        
        try:
            refreshToken = requests.post("https://api.digikey.com/v1/oauth2/token", data=digiKeyAuth)
            refreshToken.raise_for_status()
        except requests.exceptions.HTTPError as http_error:
            messagebox.showerror("Bad Code", "Code entered is not vaild.")
            return None
        
        self.ACCESS_TOKEN = refreshToken.json()["access_token"]
        self.TOKEN_EXPIRES = time.time() + refreshToken.json()["expires_in"]
        self.REFRESH_TOKEN = refreshToken.json()["refresh_token"]

        with open(self.refresh_token_file, "w") as textFile:
            textFile.write(self.REFRESH_TOKEN)



    def refresh_access_token(self):
        #Check if we have a client id and secret.
        if not self.CLIENT_ID or not self.CLIENT_SECRET:
            messagebox.showerror("API Error", "Missing Digikey client ID or secret!")
            return None
        

        digiKeyAuth = {
            'client_id': self.CLIENT_ID ,
            'client_secret': self.CLIENT_SECRET,
            'refresh_token': self.REFRESH_TOKEN,
            'grant_type':'refresh_token'
        }
        
        try:
            tokenRequest = requests.post("https://api.digikey.com/v1/oauth2/token", data=digiKeyAuth)
            tokenRequest.raise_for_status()
        except requests.exceptions.HTTPError as http_error:
            #Should return as a 401 error, I think it's safe to assume that the credentials are invalid.
            messagebox.showerror("Bad Credentials", "Credentials entered in config.json are not vaild.")
            return None


        self.ACCESS_TOKEN = tokenRequest.json()["access_token"]
        self.TOKEN_EXPIRES = time.time() + tokenRequest.json()["expires_in"]
        self.REFRESH_TOKEN = tokenRequest.json()["refresh_token"]

        with open(self.refresh_token_file, "w") as textFile:
            textFile.write(self.REFRESH_TOKEN)

    @staticmethod
    def _handle_digikey_error(http_error):
        match http_error.response.status_code:
            case 400:
                messagebox.showerror("Bad Request", "Input model is invalid or malformed.")
            case 401:
                messagebox.showerror("Unauthorized", "Access token is missing, expired, or invalid.")
            case 403:
                messagebox.showerror("Forbidden", "Access is denied. Check Client ID and subscription settings. This may also be an error with Digikeys servers.")
            case 404:
                messagebox.showerror("Not Found", "The requested resource or part number was not found.")
            case 405:
                messagebox.showerror("Method Not Allowed", "The HTTP method used is not supported by this endpoint.")
            case 408:
                messagebox.showerror("Request Timeout", "The request timed out. Please try again.")
            case 429:
                messagebox.showerror("Rate Limit Exceeded", "Too many requests. Please slow down.")
            case 500:
                messagebox.showerror("Server Error", "An internal server error occurred. Try again later.")
            case 502:
                messagebox.showerror("Bad Gateway", "Digi-Key's server received an invalid response from upstream.")
            case 503:
                messagebox.showerror("Service Unavailable", "The service is temporarily unavailable. Try again later.")
            case 504:
                messagebox.showerror("Gateway Timeout", "The server did not receive a timely response.")
            case _:
                messagebox.showerror("HTTP Error", f"Unexpected error {http_error.response.status_code}: {http_error.response.text}")

    @staticmethod
    def _show_error_and_return_none(msg: str, code: int):
        messagebox.showerror("Failed to Fetch Image", f"{msg}.\nHTTP ERROR: {code}")
        return None

    def fetch_image_data(self, digikey_part_number: str):
        '''
        Request the part image from the Digikey api, using the Digikey part number.
        '''
        # Yes, we probably could use the photo_url from the metadata (when that gets implemented)
        # but this returns the most up-to-date image. ()

        if not self.ACCESS_TOKEN or time.time() > self.TOKEN_EXPIRES:
            self.refresh_access_token()
        

        defaultHeaders = {
            'Authorization': 'Bearer ' + self.ACCESS_TOKEN,
            'X-DIGIKEY-Client-Id': self.CLIENT_ID,
            'Content-Type': 'application/json',
            'X-DIGIKEY-Locale-Site': 'US', 
            'X-DIGIKEY-Locale-Language': 'en', 
            'X-DIGIKEY-Locale-Currency': 'USD'
        }
        
        
        try:
            response = requests.get("https://api.digikey.com/products/v4/search/%s/media" % (digikey_part_number), headers=defaultHeaders, timeout=5)

            response.raise_for_status()

            # Returns all the media on the product page, including datasheets.
            mediaLinks = json.loads(response.content)['MediaLinks']

            imageURL = None

            for i in mediaLinks:
                if i["MediaType"] == "Product Photos":
                    imageURL = i["Url"]
                    pass

            # Apparently they only EXCLUDE curl/wget or whatever python uses,
            # sending NOTHING works fine.
            imageHeaders = {
                "User-Agent": ""
            }
                
            if imageURL is not None:
                imageData = requests.get(imageURL, headers=imageHeaders)
                # This should probably have it's own try/except, since it's not techincally
                # part of the Digikey API, so far i've only seen it return 403 on user-agent error though.
                imageData.raise_for_status()
            
            return ImageCacheEntry(
                dk_part_number=digikey_part_number,
                image=imageData.content,
                etag=response.headers.get('ETag'), #What is this, i've only ever seen it return 
                fetched_at=datetime.now(timezone.utc).timestamp()
            )
        
        except requests.exceptions.HTTPError as http_error:
            self._handle_digikey_error(http_error)

        except requests.exceptions.RequestException as req_error:
            messagebox.showerror("Connection Error", f"A network error happened: \n{str(req_error)}")
        


    def fetch_part_details(self, part_number: str):
        """Fetches part details from the API"""
        # Check that we have a token and that it is not expired.
        if not self.ACCESS_TOKEN or time.time() > self.TOKEN_EXPIRES:
            self.refresh_access_token()
        

        searchHeaders = {
            'Authorization': 'Bearer ' + self.ACCESS_TOKEN,
            'X-DIGIKEY-Client-Id': self.CLIENT_ID,
            'Content-Type': 'application/json',
            'X-DIGIKEY-Locale-Site': 'US', 
            'X-DIGIKEY-Locale-Language': 'en', 
            'X-DIGIKEY-Locale-Currency': 'USD'
        }

        searchParams = {
            'Keywords': part_number.strip(),
            'Limit': 1,
            'Offset': 0,
            'FilterOptionsRequest': {} # Optional filters
        }

        try:
            logging.debug("Requesting the data model from digikey.")
            response = requests.post('https://api.digikey.com/products/v4/search/keyword', 
                                     data=json.dumps(searchParams), 
                                     headers=searchHeaders, 
                                     timeout=5)
            
            response.raise_for_status()  # Raise error for HTTP issues

            # shouldn't need to check this because if response is error, then 
            # status code would reflect that and be caught by the exception
            # if response.text.lstrip().startswith("<!DOCTYPE html>"):
            #     return None

            result = response.json()["Products"][0]

            # this would happen if there is some error on DIGIKEY side,
            # they accepted our token and they're returning a success code
            # but the body could be incorrect so we check
            if "error" in result:
                messagebox.showerror("API Error", f"Error: {result['error']}")
                return None

            price_val = result.get('UnitPrice', 0.0)
            try:
                price = float(price_val)
            except ValueError:
                price = 0.0  # or you could use None if that fits your logic

            print(result.get("ProductVariations"))

            return {
                "part_info": {
                    "part_number": result["ProductVariations"][0].get("DigiKeyProductNumber","N/A"),
                    "manufacturer_number": result.get('ManufacturerProductNumber', "N/A"),
                    "location": "N/A",
                    "count": result.get('count', 0),
                    "type": result["Category"].get('Name', "N/A")
                },
                "metadata": {
                    "price": price,
                    "low_stock": "N/A",
                    "description": result["Description"].get('ProductDescription', "N/A"),
                    "photo_url": result.get('PhotoUrl', "N/A"),
                    "datasheet_url": result.get('DatasheetUrl', "N/A"),
                    "product_url": result.get('ProductUrl', "N/A"),
                    "in_use": "Available"
                }
            }
        except requests.exceptions.HTTPError as http_error:
            self._handle_digikey_error(http_error)

        except requests.exceptions.RequestException as req_error:
            messagebox.showerror("Connection Error", f"A network error happened: \n{str(req_error)}")



    def get_package_list_from_barcode(self, barcode):
        
        if not self.ACCESS_TOKEN or time.time() > self.TOKEN_EXPIRES:
            self.refresh_access_token()

        defaultHeaders = {
            'Authorization': 'Bearer ' + self.ACCESS_TOKEN,
            'X-DIGIKEY-Client-Id': self.CLIENT_ID,
            'Content-Type': 'application/json',
            'X-DIGIKEY-Locale-Site': 'US', 
            'X-DIGIKEY-Locale-Language': 'en', 
            'X-DIGIKEY-Locale-Currency': 'USD'
        }

        try:
            response = requests.get("api.digikey.com/Barcoding/v3/PackListBarcodes/%s" % (barcode), headers=defaultHeaders, timeout=5)

            response.raise_for_status()

            

            partList = tuple(json.loads(response.content["PackListDetails"]))

            return partList

        except requests.exceptions.HTTPError as http_error:
            self._handle_digikey_error(http_error)

        except requests.exceptions.RequestException as req_error:
            messagebox.showerror("Connection Error", f"A network error happened: \n{str(req_error)}")




