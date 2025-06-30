import os
import json
import sqlite3
from tkinter import messagebox

class FileInitializer:
    def __init__(self, database_folder="Databases"):
        self.database_folder = os.path.join(os.path.dirname(__file__), database_folder)
        self.catalogue_path = os.path.join(self.database_folder, "component_catalogue.json")
        self.config_path = os.path.join(self.database_folder, "config.json")
        self.image_cache_path = os.path.join(self.database_folder, "image_cache.db")

    def initialize_files(self):
        self.ensure_folder()
        created_config = self.ensure_config()
        self.ensure_catalogue()
        self.ensure_image_cache()

        # If config was just created, prompt user
        if created_config:
            messagebox.showinfo("Setup Required", 
                                f"A new config.json was created at {self.config_path}.\n\n"
                                "Please fill in the required information before using the system.")
            # Optionally open the config file automatically
            os.startfile(self.config_path)

    def ensure_folder(self):
        if not os.path.exists(self.database_folder):
            os.makedirs(self.database_folder)
            print(f"Created folder: {self.database_folder}")

    def ensure_catalogue(self):
        if not os.path.exists(self.catalogue_path):
            print(f"Creating new component_catalogue.json at {self.catalogue_path}")
            with open(self.catalogue_path, "w") as f:
                json.dump([], f, indent=4)

    def ensure_config(self):
        if not os.path.exists(self.config_path):
            print(f"Creating new config.json at {self.config_path}")
            default_config = {
                "API": {
                    "DIGIKEY_CLIENT_ID": "YOUR CLIENT ID",
                    "DIGIKEY_CLIENT_SECRET": "YOUR CLIENT SECRET"
                },
                "SERIAL": {
                    "PORT": "COM3",
                    "BAUDRATE": 9600,
                    "TIMEOUT": 1
                },
                "FILES": {
                    "COMPONENT_CATALOGUE": "Databases/component_catalogue.json",
                    "CHANGELOG": "Databases/changelog.txt",
                    "IMAGE_CACHE": "Databases/image_cache.db"
                }
            }
            with open(self.config_path, "w") as f:
                json.dump(default_config, f, indent=4)
            return True  # config was created
        return False  # config already existed

    def ensure_image_cache(self):
        if not os.path.exists(self.image_cache_path):
            print(f"Creating new image_cache.db at {self.image_cache_path}")
            conn = sqlite3.connect(self.image_cache_path)
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS image_cache (
                part_number TEXT PRIMARY KEY,
                image BLOB NOT NULL,
                etag TEXT,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            conn.commit()
            conn.close()
