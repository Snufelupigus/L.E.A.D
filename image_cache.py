import os
import sqlite3
import logging
from dataclasses import dataclass
from datetime import datetime

@dataclass
class ImageCacheEntry:
    dk_part_number: str | None
    image: bytes | None
    etag: str | None
    fetched_at: str | None

class Image_Cache:
    def __init__(self):
        # guaranteed to be created
        self.db_file = os.path.join(os.path.dirname(__file__), "Databases", "image_cache.db") 
        self.conn = sqlite3.connect(self.db_file)

    '''
    # enter and exit are for use in with blocks, e.g.
    with Image_Cache() as cache:
        if not cache.already_exists("...."):
            cache.store_entry(entry)
    '''

    def __enter__(self): 
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()

    def __del__(self):
        try:
            if self.conn:
                self.conn.close()
        except Exception:
            pass # avoid crash

    def print_entry(self, part_number: str | None):
        cursor = self.conn.cursor()
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
                       entry.dk_part_number, entry.etag, entry.fetched_at)
        return None

    def already_exists(self, part_number: str | None):
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT 1
            FROM image_cache 
            WHERE part_number = ?
        """, (part_number,)) # single comma to make it a tuple
        found = cursor.fetchone() is not None
        cursor.close()
        return found

    def request_entry(self, part_number: str | None):
        if not part_number:
            return None

        cursor = self.conn.cursor()
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
                etag=row[2],
                fetched_at=row[3] # since already stored in the %Y-%m-%d %H:%M:%S
            )
        return None

    def store_entry(self, entry: ImageCacheEntry | None):
        if not entry:
            logging.debug('Passed entry was None.')
            return None
        cursor = self.conn.cursor()
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

