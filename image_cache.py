import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime

@dataclass
class ImageCacheEntry:
    part_number: str | None
    image: bytes | None
    etag: str | None
    fetched_at: datetime | None

class Image_Cache:
    def __init__(self):
        # guaranteed to be created
        self.db_file = os.path.join(os.path.dirname(__file__), "Databases", "image_cache.db") 

    def already_exists(self, part_number: str | None):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        cursor.execute("SELECT 1 FROM image_cache WHERE part_number = ?", (part_number,)) # single comma to make it a tuple
        found = cursor.fetchone() is not None
        conn.close()
        return found

    def request_cache(self, part_number: str | None):
        if not part_number:
            return None

        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        cursor.execute("SELECT 1 FROM image_cache WHERE part_number = ?", (part_number,)) # single comma to make it a tuple
        row = cursor.fetchone()
        conn.close()

        if row:
            return ImageCacheEntry(
                part_number=row[0],
                image=row[1],
                etag=row[2],
                fetched_at=datetime.fromisoformat(row[4])
            )
        return None


        

    def store_blob(self, entry: ImageCacheEntry):
        if self.already_exists(entry.part_number):
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute("""
               UPDATE image_cache
               SET image = ?, etag = ?, fetched_at = CURRENT_TIMESTAMP
               WHERE part_number = ?
            """, (entry.image, entry.etag, entry.part_number))
