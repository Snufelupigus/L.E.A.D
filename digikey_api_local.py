from image_cache import ImageCache, ImageCacheEntry
from datetime import datetime, timezone
import requests
import logging
import json
import os
import time

logger = logging.getLogger(__name__)



class Digikey_API_Call:
    ACCESS_TOKEN: str
    def __init__(self, show_errors=True, error_reporter=None):
        self.config_file = os.path.join(os.path.dirname(__file__), "Databases", "config.json")
        self.image_cache = ImageCache()
        self.show_errors = show_errors
        self.error_reporter = error_reporter
        self.last_error = ""
        self.TOKEN_EXPIRES = 0
        self.load_config()

    def _report_error(self, title, message):
        self.last_error = message
        logger.error("%s: %s", title, message)
        if self.show_errors and self.error_reporter:
            self.error_reporter(title, message)

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
            self._report_error("Configuration Error", f"Failed to load config.json:\n{e}")
            self.CLIENT_ID = None
            self.CLIENT_SECRET = None

    def refresh_access_token(self):
        #Check if we have a client id and secret.
        if not self.CLIENT_ID or not self.CLIENT_SECRET:
            self._report_error("API Error", "Missing Digikey client ID or secret!")
            return None
        

        digiKeyAuth = {
            'client_id': self.CLIENT_ID ,
            'client_secret': self.CLIENT_SECRET,
            'grant_type':'client_credentials'
        }
        
        try:
            tokenRequest = requests.post("https://api.digikey.com/v1/oauth2/token", data=digiKeyAuth)
            tokenRequest.raise_for_status()
        except requests.exceptions.HTTPError as http_error:
            #Should return as a 401 error, I think it's safe to assume that the credentials are invalid.
            self._report_error("Bad Credentials", "Credentials entered in config.json are not valid.")
            return None


        self.ACCESS_TOKEN = tokenRequest.json()["access_token"]
        self.TOKEN_EXPIRES = time.time() + tokenRequest.json()["expires_in"]
        self.last_error = ""

    def _handle_digikey_error(self, http_error):
        match http_error.response.status_code:
            case 400:
                self._report_error("Bad Request", "Input model is invalid or malformed.")
            case 401:
                self._report_error("Unauthorized", "Access token is missing, expired, or invalid.")
            case 403:
                self._report_error("Forbidden", "Access is denied. Check Client ID and subscription settings. This may also be an error with Digikeys servers.")
            case 404:
                self._report_error("Not Found", "The requested resource or part number was not found.")
            case 405:
                self._report_error("Method Not Allowed", "The HTTP method used is not supported by this endpoint.")
            case 408:
                self._report_error("Request Timeout", "The request timed out. Please try again.")
            case 429:
                self._report_error("Rate Limit Exceeded", "Too many requests. Please slow down.")
            case 500:
                self._report_error("Server Error", "An internal server error occurred. Try again later.")
            case 502:
                self._report_error("Bad Gateway", "Digi-Key's server received an invalid response from upstream.")
            case 503:
                self._report_error("Service Unavailable", "The service is temporarily unavailable. Try again later.")
            case 504:
                self._report_error("Gateway Timeout", "The server did not receive a timely response.")
            case _:
                self._report_error("HTTP Error", f"Unexpected error {http_error.response.status_code}: {http_error.response.text}")

    def _show_error_and_return_none(self, msg: str, code: int):
        self._report_error("Failed to Fetch Image", f"{msg}.\nHTTP ERROR: {code}")
        return None

    def fetch_image_data(self, photo_url: str, part_number: str):
        cache_entry = self.image_cache.request_entry(part_number=part_number.strip())
        if cache_entry:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
                    "(KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
                "If-None-Match": cache_entry.etag
            }
        else:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
                    "(KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
            }

        response = requests.get(photo_url, headers=headers, timeout=5)
        if response.status_code == 304: # the etag matches so just return the cached entry
            return cache_entry
        elif response.status_code == 200: 
            if cache_entry: # entry exists but not same etag so update and return
                cache_entry.image = response.content
                cache_entry.etag = response.headers.get('ETag')
                cache_entry.fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                return cache_entry
            else: # doesnt exist so build entry object and return
                return ImageCacheEntry(
                    dk_part_number=part_number,
                    image=response.content,
                    etag=response.headers.get('ETag'),
                    fetched_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                )
        # For non-200/304 responses, fall back to the cached image when available.
        else:
            return cache_entry if cache_entry else self._show_error_and_return_none("Failed to load image.", 
                                                                                    response.status_code)


    def fetch_part_details(self, part_number: str):
        """Fetches part details from the API"""
        self.last_error = ""
        # Check that we have a token and that it is not expired.
        if not self.ACCESS_TOKEN or time.time() > self.TOKEN_EXPIRES:
            self.refresh_access_token()
        if not self.ACCESS_TOKEN:
            return None
        

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
            logger.debug("Requesting the data model from digikey.")
            response = requests.post('https://api.digikey.com/products/v4/search/keyword', 
                                     data=json.dumps(searchParams), 
                                     headers=searchHeaders, 
                                     timeout=5)
            
            response.raise_for_status()  # Raise error for HTTP issues

            # shouldn't need to check this because if response is error, then 
            # status code would reflect that and be caught by the exception
            # if response.text.lstrip().startswith("<!DOCTYPE html>"):
            #     return None

            products = response.json().get("Products", [])
            if not products:
                return None
            result = products[0]

            # this would happen if there is some error on DIGIKEY side,
            # they accepted our token and they're returning a success code
            # but the body could be incorrect so we check
            if "error" in result:
                self._report_error("API Error", f"Error: {result['error']}")
                return None

            price_val = result.get('UnitPrice', 0.0)
            try:
                price = float(price_val)
            except ValueError:
                price = 0.0  # or you could use None if that fits your logic

            logger.debug("Product variations: %s", result.get("ProductVariations"))

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
            self._report_error("Connection Error", f"A network error happened: \n{str(req_error)}")

