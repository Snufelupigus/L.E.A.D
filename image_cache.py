import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime

@dataclass
class ImageCacheEntry:
    part_number: str
    image: bytes
    etag: str
    fetched_at: datetime

class Image_Cache:
    def __init__(self):
        # guaranteed to be created
        self.db_file = os.path.join(os.path.dirname(__file__), "Databases", "image_cache.db") 

    def already_exists(self, part_number):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        cursor.execute("SELECT 1 FROM image_cache WHERE part_number = ?", (part_number,))
        found = cursor.fetchone() is not None
        conn.close()
        return found
        

    def store_blob(self, entry: ImageCacheEntry):
        if self.already_exists(entry.part_number):
            cursor.execute("""
               UPDATE image_cache
               SET image = ?, etag = ?, fetched_at = CURRENT_TIMESTAMP
               WHERE part_number = ?
            """, (entry.image, entry.etag, entry.fetched_at, entry.part_number))
