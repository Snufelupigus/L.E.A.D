import requests
import json
import os
import time
from tkinter import messagebox



class Digikey_API_Call:
    ACCESS_TOKEN: str
    def __init__(self):
        self.config_file = os.path.join(os.path.dirname(__file__), "Databases", "config.json")
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

    def refresh_access_token(self):

        #Check if we have a client id and secret.
        if not self.CLIENT_ID or not self.CLIENT_SECRET:
            messagebox.showerror("API Error", "Missing Digikey client ID or secret!")
            return None
        

        digiKeyAuth = {'client_id': self.CLIENT_ID ,
               'client_secret': self.CLIENT_SECRET,
               'grant_type':'client_credentials'}
        
        try:
            tokenRequest = requests.post("https://api.digikey.com/v1/oauth2/token", data=digiKeyAuth)
            tokenRequest.raise_for_status()
        except requests.exceptions.HTTPError as http_error:
            #Should return as a 401 error, I think it's safe to assume that the credentials are invalid.
            messagebox.showerror("Bad Credentials", "Credentials entered in config.json are not vaild.")
            return None


        self.ACCESS_TOKEN = tokenRequest.json()["access_token"]
        self.TOKEN_EXPIRES = time.time() + tokenRequest.json()["expires_in"]

    def _handle_digikey_error(self, http_error):
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

    def fetch_media(self, part_number):
        """Uses Digikey API to fetch media"""
        
        # Check that we have a token and that it is not expired.
        if not self.ACCESS_TOKEN or time.time() > self.TOKEN_EXPIRES:
            self.refresh_access_token()

        mediaHeaders = {
            'Authorization': 'Bearer ' + self.ACCESS_TOKEN,
            'X-DIGIKEY-Client-Id': self.CLIENT_ID,
            'X-DIGIKEY-Locale-Site': 'US',
            'X-DIGIKEY-Locale-Language': 'en', 
            'X-DIGIKEY-Locale-Currency': 'USD',
            'Accept': 'application/json'
        }

        mediaParams = {
            'partNumber': part_number.strip(),
            'recordCount': 10,
            'mediaType': 'Image'
        }

        try:
            response = requests.get(url='https://api.digikey.com/products/v4/productsearch/media', headers=mediaHeaders, data=mediaParams)
            response.raise_for_status()
            print (json.dumps(response.json(), indent=2))

        except requests.exceptions.HTTPError as http_error:
            self._handle_digikey_error(http_error)

            

        except requests.exceptions.RequestException as req_error:
            messagebox.showerror("Connection Error", f"A network error happened: \n{str(req_error)}")




    def fetch_part_details(self, part_number):
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
            response = requests.post('https://api.digikey.com/products/v4/search/keyword', data=json.dumps(searchParams), headers=searchHeaders)
            
            response.raise_for_status()  # Raise error for HTTP issues

            if response.text.lstrip().startswith("<!DOCTYPE html>"):
                return None

            result = response.json()["Products"][0]
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

