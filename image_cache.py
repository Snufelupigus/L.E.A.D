import os
import sqlite3
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Union
from types import TracebackType

@dataclass
class ImageCacheEntry:
    """
    Represents a cached image entry from DigiKey API.
    
    Attributes:
        dk_part_number: DigiKey part number (required)
        image: Binary image data, None if not yet loaded
        etag: HTTP ETag for cache validation, empty string if none
        fetched_at: ISO timestamp string of when image was fetched
    """
    dk_part_number: str  # Required field, no default
    image: Optional[bytes] = None  # None vs b"" is semantically different
    etag: str = ""  # Empty string is valid "no etag"
    fetched_at: str = ""  # Empty string is valid "never fetched"

class ImageCache:
    """
    SQLite-based image cache for DigiKey component images.
    
    Provides persistent storage and retrieval of component images with ETag
    support for efficient HTTP caching. Thread-safe for single-threaded use.
    """
    
    def __init__(self) -> None:
        """
        Initialize the image cache with SQLite database connection.
        
        Creates database file in Databases/image_cache.db if it doesn't exist.
        """
        self.db_file: str = os.path.join(os.path.dirname(__file__), "Databases", "image_cache.db") 
        self.conn: sqlite3.Connection = sqlite3.connect(self.db_file)

    def __enter__(self) -> 'Image_Cache':
        """
        Context manager entry point.
        
        Returns:
            Self for use in with statements.
            
        Example:
            with Image_Cache() as cache:
                if not cache.already_exists("part_number"):
                    cache.store_entry(entry)
        """
        return self

    def __exit__(self, exc_type: Optional[type], exc_val: Optional[Exception], exc_tb: Optional[TracebackType]) -> None:
        """
        Context manager exit point.
        
        Args:
            exc_type: Exception type if an exception occurred
            exc_val: Exception instance if an exception occurred  
            exc_tb: Exception traceback if an exception occurred
            
        Ensures database connection is properly closed.
        """
        if self.conn:
            self.conn.close()

    def __del__(self) -> None:
        """
        Destructor to ensure database connection cleanup.
        
        Safely closes the database connection, ignoring any exceptions
        to prevent crashes during garbage collection.
        """
        try:
            if self.conn:
                self.conn.close()
        except Exception:
            pass # avoid crash during garbage collection

    def print_entry(self, part_number: Optional[str]) -> None:
        """
        Print cache entry details to debug log.
        
        Args:
            part_number: DigiKey part number to look up
            
        Logs the part number, ETag, and fetch timestamp if found,
        otherwise logs that entry was not found.
        """
        cursor: sqlite3.Cursor = self.conn.cursor()
        cursor.execute("""
            SELECT part_number, image, etag, fetched_at 
            FROM image_cache 
            WHERE part_number = ?
            """, (part_number,)) # single comma to make it a tuple
        entry = cursor.fetchone()
        if not entry:
            logging.debug("Entry not found, can't print.")
            return None
        logging.debug("Entry:\nPart Number: {0}\nETag: {1}\nFetched at: {2}", 
                       entry[0], entry[2], entry[3])  # Fixed to use tuple indices
        return None

    def already_exists(self, part_number: Optional[str]) -> bool:
        """
        Check if a cache entry exists for the given part number.
        
        Args:
            part_number: DigiKey part number to check
            
        Returns:
            True if entry exists in cache, False otherwise
            
        Note:
            This only checks for existence, not whether the cached
            image data is valid or up-to-date.
        """
        cursor: sqlite3.Cursor = self.conn.cursor()
        cursor.execute("""
            SELECT 1
            FROM image_cache 
            WHERE part_number = ?
        """, (part_number,)) # single comma to make it a tuple
        found: bool = cursor.fetchone() is not None
        cursor.close()
        return found

    def request_entry(self, part_number: Optional[str]) -> Optional[ImageCacheEntry]:
        """
        Retrieve a cached image entry by part number.
        
        Args:
            part_number: DigiKey part number to retrieve
            
        Returns:
            ImageCacheEntry with cached data if found, None otherwise
            
        Note:
            Returns complete entry including image data, ETag, and timestamp.
            Use this when you need the actual cached image data.
        """
        if not part_number:
            return None

        cursor: sqlite3.Cursor = self.conn.cursor()
        cursor.execute("""
            SELECT part_number, image, etag, fetched_at
            FROM image_cache 
            WHERE part_number = ?
        """, (part_number,)) # single comma to make it a tuple
        row = cursor.fetchone()
        cursor.close()

        if row:
            return ImageCacheEntry(
                dk_part_number=row[0],
                image=row[1],
                etag=row[2] if row[2] else "",
                fetched_at=row[3] if row[3] else ""
            )
        return None

    def store_entry(self, entry: Optional[ImageCacheEntry]) -> None:
        """
        Store or update a cache entry in the database.
        
        Args:
            entry: ImageCacheEntry to store, ignored if None
            
        Behavior:
            - If entry already exists, updates image data and ETag
            - If entry is new, inserts with provided timestamp
            - Updates fetch timestamp to current time on update
            - Commits transaction automatically
            
        Note:
            No-op if entry is None. Logs debug message for None entries.
        """
        if not entry:
            logging.debug('Passed entry was None.')
            return None
        cursor: sqlite3.Cursor = self.conn.cursor()
        if self.already_exists(entry.dk_part_number):
            cursor.execute("""
               UPDATE image_cache
               SET image = ?, etag = ?, fetched_at = CURRENT_TIMESTAMP
               WHERE part_number = ?
            """, (entry.image, entry.etag, entry.dk_part_number))
        else:
            cursor.execute("""
                INSERT INTO image_cache (part_number, image, etag, fetched_at)
                VALUES (?, ?, ?, ?)
            """, (entry.dk_part_number, entry.image, entry.etag, entry.fetched_at))
        self.conn.commit()
        cursor.close()

