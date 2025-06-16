import requests
import json
import os
import time
from tkinter import messagebox



class Digikey_API_Call:
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
        digiKeyAuth = {'client_id': self.CLIENT_ID ,
               'client_secret': self.CLIENT_SECRET,
               'grant_type':'client_credentials'}
        tokenRequest = requests.post("https://api.digikey.com/v1/oauth2/token", data=digiKeyAuth)
        self.ACCESS_TOKEN = tokenRequest.json()["access_token"]
        self.TOKEN_EXPIRES = time.time() + tokenRequest.json()["expires_in"]

    def fetch_part_details(self, part_number):
        """Fetches part details from the API"""
        if not self.CLIENT_ID or not self.CLIENT_SECRET:
            messagebox.showerror("API Error", "Missing Digikey client ID or secret!")
            return None
        
        #Check that we have a token
        if not self.ACCESS_TOKEN:
            self.refresh_access_token()

        #Check if the token has expired
        if time.time() > self.TOKEN_EXPIRES:
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
        except requests.exceptions.RequestException as e:
            messagebox.showerror("API Request Failed", f"Error contacting API:\n{e}")
            return None

