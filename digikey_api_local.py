from image_cache import ImageCacheEntry, ImageCache
from datetime import datetime, timezone
from PIL import Image
from io import BytesIO
import requests
import logging
logging.basicConfig(level=logging.DEBUG)
import json
import os
import time
from tkinter import messagebox
from typing import Optional, Dict, Any, Union



class Digikey_API_Call:
    """
    DigiKey API client for fetching part details and images.
    
    Handles OAuth2 authentication, part searches, and image caching.
    Automatically manages access tokens and provides error handling
    for common DigiKey API issues.
    
    Attributes:
        ACCESS_TOKEN: Current OAuth2 access token
        TOKEN_EXPIRES: Unix timestamp when current token expires
        CLIENT_ID: DigiKey API client identifier
        CLIENT_SECRET: DigiKey API client secret
    """
    ACCESS_TOKEN: Optional[str]
    TOKEN_EXPIRES: float
    CLIENT_ID: Optional[str]
    CLIENT_SECRET: Optional[str]
    
    def __init__(self) -> None:
        """
        Initialize DigiKey API client.
        
        Loads configuration from config.json and initializes image cache.
        Does not authenticate immediately - authentication happens on first API call.
        
        Raises:
            Configuration errors are shown via messagebox, not raised as exceptions.
        """
        self.config_file: str = os.path.join(os.path.dirname(__file__), "Databases", "config.json")
        self.image_cache: ImageCache = ImageCache()
        self.ACCESS_TOKEN = None
        self.TOKEN_EXPIRES = 0.0
        self.load_config()

    def load_config(self) -> None:
        """
        Load DigiKey API configuration from config.json.
        
        Reads CLIENT_ID and CLIENT_SECRET from the API section of config.json.
        Sets credentials to None and shows error dialog if loading fails.
        
        Expected config structure:
            {
                "API": {
                    "DIGIKEY_CLIENT_ID": "your_client_id",
                    "DIGIKEY_CLIENT_SECRET": "your_client_secret"
                }
            }
            
        Raises:
            Shows messagebox error instead of raising exceptions.
        """
        self.ACCESS_TOKEN = None
        try:
            with open(self.config_file, "r") as file:
                config: Dict[str, Any] = json.load(file)

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

    def refresh_access_token(self) -> Optional[str]:
        """
        Refresh the OAuth2 access token using client credentials flow.
        
        Makes a POST request to DigiKey's OAuth2 endpoint to obtain a new
        access token. Updates internal token and expiration time on success.
        
        Returns:
            New access token string if successful, None if failed
            
        Side Effects:
            - Updates self.ACCESS_TOKEN and self.TOKEN_EXPIRES on success
            - Shows error messagebox on failure (credentials or network issues)
            
        Note:
            Uses client credentials grant type which is appropriate for
            server-to-server API access without user interaction.
        """
        # Check if we have a client id and secret.
        if not self.CLIENT_ID or not self.CLIENT_SECRET:
            messagebox.showerror("API Error", "Missing Digikey client ID or secret!")
            return None
        
        digiKeyAuth: Dict[str, str] = {
            'client_id': self.CLIENT_ID,
            'client_secret': self.CLIENT_SECRET,
            'grant_type': 'client_credentials'
        }
        
        try:
            tokenRequest: requests.Response = requests.post("https://api.digikey.com/v1/oauth2/token", data=digiKeyAuth)
            tokenRequest.raise_for_status()
        except requests.exceptions.HTTPError as http_error:
            # Should return as a 401 error, I think it's safe to assume that the credentials are invalid.
            messagebox.showerror("Bad Credentials", "Credentials entered in config.json are not valid.")
            return None

        token_response: Dict[str, Any] = tokenRequest.json()
        self.ACCESS_TOKEN = token_response["access_token"]
        self.TOKEN_EXPIRES = time.time() + token_response["expires_in"]
        return self.ACCESS_TOKEN

    @staticmethod
    def _handle_digikey_error(http_error: requests.exceptions.HTTPError) -> None:
        """
        Handle DigiKey API HTTP errors with user-friendly messages.
        
        Args:
            http_error: HTTP error from DigiKey API request
            
        Shows appropriate messagebox error dialog based on HTTP status code.
        Covers common DigiKey API error conditions with specific guidance.
        """
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
    def _show_error_and_return_none(msg: Union[str, Exception], code: Optional[int]) -> None:
        """
        Show generic image fetch error and return None.
        
        Args:
            msg: Error message or exception to display
            code: HTTP status code if available
            
        Returns:
            Always returns None (for consistent error handling)
            
        Helper method for image fetching error cases.
        """
        messagebox.showerror("Failed to Fetch Image", f"{msg}.\nHTTP ERROR: {code}")
        return None

    def fetch_image_data(self, photo_url: str, part_number: str) -> Optional[ImageCacheEntry]:
        """
        Fetch component image from DigiKey with intelligent caching and immediate cache return.
        
        Args:
            photo_url: HTTP URL to component image
            part_number: DigiKey part number for cache key
            
        Returns:
            ImageCacheEntry with image data if successful, None on error
            
        Behavior:
            1. Checks cache first using part number as key
            2. If cached image data exists, returns immediately (no network request!)
            3. If cache miss or no image data, makes HTTP request with appropriate headers
            4. On 304 response, returns cached entry (not modified)
            5. On 200 response, updates cache and returns new data
            6. Creates new cache entry for completely new images
            
        Performance:
            - Cache hits are instant (no network delay)
            - Only cache misses require network requests
            - Network requests still block calling thread (use async wrapper for UI)
            
        Note:
            DigiKey appears to not properly honor If-None-Match headers,
            so this method includes additional ETag comparison logic.
            Network requests have 5-second timeout.
        """
        cache_entry: Optional[ImageCacheEntry] = self.image_cache.request_entry(part_number=part_number.strip())
        
        headers: Dict[str, str]
        if cache_entry and cache_entry.image:
            return cache_entry

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
                "(KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
            "If-None-Match": cache_entry.etag if cache_entry else ""
        }

        try:
            response: requests.Response = requests.get(photo_url, headers=headers, timeout=5)

            if not response:
                logging.debug("No response from DigiKey.")
                return None

            if response.status_code == 304:  # the etag matches so just return the cached entry
                return cache_entry

            elif response.status_code == 200: 
                if cache_entry:  # entry exists but not same etag so update and return
                    if cache_entry.etag == response.headers.get("ETag"):  
                    # shouldn't have to check, but DigiKey doesn't seem to honour If-None-Match
                        logging.debug("Etags matched, returning cached entry.")
                        return cache_entry
                    cache_entry.image = response.content
                    cache_entry.etag = response.headers.get('ETag', "")
                    cache_entry.fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                    logging.debug(f"Etags did not match. Updating entry: {cache_entry.dk_part_number}")
                    self.image_cache.store_entry(cache_entry)
                    return cache_entry

                new_cache = ImageCacheEntry(
                    dk_part_number=part_number,
                    image=response.content,
                    etag=response.headers.get('ETag', ""),
                    fetched_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                )
                self.image_cache.store_entry(new_cache)
                return new_cache

            response.raise_for_status()
        except requests.exceptions.HTTPError as err:
            code: Optional[int] = err.response.status_code if err.response else None
            return self._show_error_and_return_none(msg=err, code=code)
        except requests.exceptions.RequestException as err:
            code: Optional[int] = err.response.status_code if err.response else None
            return self._show_error_and_return_none(msg=err, code=code)

    def fetch_part_details(self, part_number: str) -> Optional[Dict[str, Any]]:
        """
        Fetch detailed component information from DigiKey API.
        
        Args:
            part_number: DigiKey or manufacturer part number to search
            
        Returns:
            Dictionary with part_info and metadata sections if found, None on error
            
        Return Structure:
            {
                "part_info": {
                    "part_number": DigiKey part number,
                    "manufacturer_number": Manufacturer's part number,
                    "location": "N/A" (set by caller),
                    "count": 0 (set by caller),
                    "type": Component category name
                },
                "metadata": {
                    "price": Unit price as float,
                    "low_stock": "N/A" (set by caller),
                    "description": Product description,
                    "photo_url": URL to component image,
                    "datasheet_url": URL to datasheet PDF,
                    "product_url": DigiKey product page URL,
                    "in_use": "Available"
                }
            }
            
        Behavior:
            - Automatically refreshes access token if expired
            - Searches for exact keyword match (limit 1 result)
            - Uses first product from search results
            - Shows error dialogs for API errors instead of raising exceptions
            
        Note:
            Network requests have 5-second timeout. 
            Returns None on any error condition.
        """
        # Check that we have a token and that it is not expired.
        if not self.ACCESS_TOKEN or time.time() > self.TOKEN_EXPIRES:
            self.refresh_access_token()
        
        searchHeaders: Dict[str, str] = {
            'Authorization': 'Bearer ' + (self.ACCESS_TOKEN or ""),
            'X-DIGIKEY-Client-Id': self.CLIENT_ID or "",
            'Content-Type': 'application/json',
            'X-DIGIKEY-Locale-Site': 'US', 
            'X-DIGIKEY-Locale-Language': 'en', 
            'X-DIGIKEY-Locale-Currency': 'USD'
        }

        searchParams: Dict[str, Any] = {
            'Keywords': part_number.strip(),
            'Limit': 1,
            'Offset': 0,
            'FilterOptionsRequest': {}  # Optional filters
        }

        try:
            logging.debug("Requesting the data model from digikey.")
            response: requests.Response = requests.post('https://api.digikey.com/products/v4/search/keyword', 
                                     data=json.dumps(searchParams), 
                                     headers=searchHeaders, 
                                     timeout=5)
            
            response.raise_for_status()  # Raise error for HTTP issues

            response_data: Dict[str, Any] = response.json()
            result: Dict[str, Any] = response_data["Products"][0]

            # this would happen if there is some error on DIGIKEY side,
            # they accepted our token and they're returning a success code
            # but the body could be incorrect so we check
            if "error" in result:
                messagebox.showerror("API Error", f"Error: {result['error']}")
                return None

            price_val: Any = result.get('UnitPrice', 0.0)
            try:
                price: float = float(price_val)
            except (ValueError, TypeError):
                price = 0.0

            print(result.get("ProductVariations"))

            return {
                "part_info": {
                    "part_number": result["ProductVariations"][0].get("DigiKeyProductNumber", "N/A"),
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
            return None

        except requests.exceptions.RequestException as req_error:
            messagebox.showerror("Connection Error", f"A network error happened: \n{str(req_error)}")
            return None

