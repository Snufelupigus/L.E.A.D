import os
import sqlite3
import logging
import json
from dataclasses import dataclass
from file_initializer import FileInitializer

@dataclass
class ImageCacheEntry:
    dk_part_number: str | None
    image: bytes | None
    etag: str | None
    fetched_at: str | None

class ImageCache:
    def __init__(self):
        self.db_file = self._resolve_db_path()
        self.conn = sqlite3.connect(self.db_file)

    """
    Support context-manager usage, for example:
    with ImageCache() as cache:
        if not cache.already_exists("..."):
            cache.store_entry(entry)
    """

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

    def _resolve_db_path(self):
        script_dir = os.path.dirname(__file__)
        config_path = os.path.join(script_dir, "Databases", "config.json")
        configured_path = ""
        try:
            with open(config_path, "r") as file:
                config = json.load(file)
                configured_path = config.get("FILES", {}).get("IMAGE_CACHE", "")
        except (FileNotFoundError, json.JSONDecodeError):
            configured_path = ""

        relative_path = configured_path or FileInitializer.DEFAULT_PATHS["IMAGE_CACHE"]
        if os.path.isabs(relative_path):
            return relative_path
        return os.path.join(script_dir, relative_path)

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


# Backward-compatible alias while callers are migrated.
Image_Cache = ImageCache

