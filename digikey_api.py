import requests
import json
import os
from tkinter import messagebox

class Digikey_API_Call:
    def __init__(self):
        self.config_file = os.path.join(os.path.dirname(__file__), "config.json")
        self.load_config()

    def load_config(self):
        """Loads API configuration from config.json"""
        try:
            with open(self.config_file, "r") as file:
                config = json.load(file)
                self.GOOGLE_SCRIPT_URL = config["API"].get("GOOGLE_SCRIPT_URL", "")
                if not self.GOOGLE_SCRIPT_URL:
                    raise ValueError("GOOGLE_SCRIPT_URL is missing in config.json")
        except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
            messagebox.showerror("Configuration Error", f"Failed to load config.json:\n{e}")
            self.GOOGLE_SCRIPT_URL = None

    def fetch_part_details(self, part_number):
        """Fetches part details from the API"""
        if not self.GOOGLE_SCRIPT_URL:
            messagebox.showerror("API Error", "API URL is not configured properly.")
            return None

        params = {"partNumber": part_number.strip()}
        try:
            response = requests.post(self.GOOGLE_SCRIPT_URL, data=params)
            response.raise_for_status()  # Raise error for HTTP issues

            if response.text.lstrip().startswith("<!DOCTYPE html>"):
                return None

            result = response.json()
            if "error" in result:
                messagebox.showerror("API Error", f"Error: {result['error']}")
                return None

            return {
                "part_info": {
                    "part_number": result.get('partNumber', "N/A"),
                    "manufacturer_number": result.get('manufacturerPartNumber', "N/A"),
                    "location": result.get('location', "N/A"),
                    "count": result.get('count', 0),
                    "type": result.get('type', "N/A")
                },
                "metadata": {
                    "price": float(result.get('price', 0.0)),
                    "low_stock": "N/A",
                    "description": result.get('description', "N/A"),
                    "photo_url": result.get('photoUrl', "N/A"),
                    "datasheet_url": result.get('datasheetUrl', "N/A"),
                    "product_url": result.get('productUrl', "N/A")
                }
            }
        except requests.exceptions.RequestException as e:
            messagebox.showerror("API Request Failed", f"Error contacting API:\n{e}")
            return None

