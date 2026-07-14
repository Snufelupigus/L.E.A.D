import os
import json
import sqlite3
import logging
import datetime


logger = logging.getLogger(__name__)

class FileInitializer:
    DEFAULT_CONFIG = {
        "API": {
            "DIGIKEY_CLIENT_ID": "",
            "DIGIKEY_CLIENT_SECRET": "",
        },
        "WEB_SYNC": {
            "ENABLED": False,
            "GITHUB_OWNER": "",
            "REPOSITORY": "",
            "BRANCH": "main",
            "TARGET_PATH": "component_catalogue.json",
            "ACCESS_TOKEN": "",
            "COMMIT_MESSAGE": "Update component catalogue from L.E.A.D. desktop app",
            "LAST_SYNC_STATUS": "",
            "LAST_SYNC_AT": "",
            "LAST_PUSH_ERROR": "",
            "LAST_PUSH_ERROR_PATH": "",
            "LAST_PUSH_ERROR_AT": "",
        },
        "SERIAL": {
            "PORT": "",
            "BAUDRATE": "",
            "TIMEOUT": "",
            "LED_COUNT": "",
        },
        "FILES": {
            "COMPONENT_CATALOGUE": "",
            "CHANGELOG": "",
            "IMAGE_CACHE": "",
        },
    }

    DEFAULT_PATHS = {
        "COMPONENT_CATALOGUE": "Databases/component_catalogue.json",
        "CHANGELOG": "Databases/changelog.txt",
        "IMAGE_CACHE": "Databases/image_cache.db",
    }

    def __init__(self, database_folder="Databases"):
        self.database_folder = os.path.join(os.path.dirname(__file__), database_folder)
        self.catalogue_path = os.path.join(self.database_folder, "component_catalogue.json")
        self.config_path = os.path.join(self.database_folder, "config.json")
        self.image_cache_path = os.path.join(self.database_folder, "image_cache.db")

    def initialize_files(self):
        self.ensure_folder()
        created_config = self.ensure_config()
        self.ensure_runtime_files()
        return created_config

    def ensure_folder(self):
        if not os.path.exists(self.database_folder):
            os.makedirs(self.database_folder)
            logger.info("Created folder: %s", self.database_folder)

    def ensure_catalogue(self):
        self.ensure_catalogue_at_path(self.catalogue_path)

    def ensure_config(self):
        if not os.path.exists(self.config_path):
            logger.info("Creating new config.json at %s", self.config_path)
            self.save_config(self.DEFAULT_CONFIG)
            return True  # config was created
        merged = self.load_config()
        self.save_config(merged)
        return False  # config already existed

    def ensure_image_cache(self):
        self.ensure_image_cache_at_path(self.image_cache_path)

    def load_config(self):
        config = {}
        try:
            with open(self.config_path, "r") as file:
                config = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            config = {}
        return self._normalize_config(self._merge_dicts(self.DEFAULT_CONFIG, config))

    def save_config(self, config):
        self.ensure_folder()
        normalized = self._normalize_config(self._merge_dicts(self.DEFAULT_CONFIG, config or {}))
        with open(self.config_path, "w") as file:
            json.dump(normalized, file, indent=4)

    def record_sync_error(self, message, export_path):
        config = self.load_config()
        sync_config = dict(config.get("WEB_SYNC", {}))
        sync_config["LAST_SYNC_STATUS"] = f"Failed: {str(message or '').strip()}"
        sync_config["LAST_SYNC_AT"] = datetime.datetime.now().isoformat(timespec="seconds")
        sync_config["LAST_PUSH_ERROR"] = str(message or "").strip()
        sync_config["LAST_PUSH_ERROR_PATH"] = str(export_path or "").strip()
        sync_config["LAST_PUSH_ERROR_AT"] = datetime.datetime.now().isoformat(timespec="seconds")
        config["WEB_SYNC"] = sync_config
        self.save_config(config)

    def record_sync_result(self, status_message):
        config = self.load_config()
        sync_config = dict(config.get("WEB_SYNC", {}))
        sync_config["LAST_SYNC_STATUS"] = str(status_message or "").strip()
        sync_config["LAST_SYNC_AT"] = datetime.datetime.now().isoformat(timespec="seconds")
        config["WEB_SYNC"] = sync_config
        self.save_config(config)

    def clear_sync_error(self):
        config = self.load_config()
        sync_config = dict(config.get("WEB_SYNC", {}))
        changed = False
        for key in ("LAST_PUSH_ERROR", "LAST_PUSH_ERROR_PATH", "LAST_PUSH_ERROR_AT"):
            if sync_config.get(key):
                sync_config[key] = ""
                changed = True
        if changed:
            config["WEB_SYNC"] = sync_config
            self.save_config(config)

    def ensure_runtime_files(self):
        config = self.load_config()
        catalogue_path = self.resolve_file_path(config["FILES"].get("COMPONENT_CATALOGUE", ""), "COMPONENT_CATALOGUE")
        changelog_path = self.resolve_file_path(config["FILES"].get("CHANGELOG", ""), "CHANGELOG")
        image_cache_path = self.resolve_file_path(config["FILES"].get("IMAGE_CACHE", ""), "IMAGE_CACHE")

        self.ensure_catalogue_at_path(catalogue_path)
        self.ensure_changelog_at_path(changelog_path)
        self.ensure_image_cache_at_path(image_cache_path)

    def resolve_file_path(self, configured_path, key):
        candidate = str(configured_path or "").strip()
        if not candidate:
            candidate = self.DEFAULT_PATHS[key]
        if os.path.isabs(candidate):
            return candidate
        return os.path.join(os.path.dirname(__file__), candidate)

    def ensure_catalogue_at_path(self, path):
        self._ensure_parent_folder(path)
        if not os.path.exists(path):
            logger.info("Creating new component_catalogue.json at %s", path)
            with open(path, "w") as file:
                json.dump([], file, indent=4)

    def ensure_changelog_at_path(self, path):
        self._ensure_parent_folder(path)
        if not os.path.exists(path):
            logger.info("Creating new changelog.txt at %s", path)
            with open(path, "w") as file:
                file.write("")

    def ensure_image_cache_at_path(self, path):
        self._ensure_parent_folder(path)
        if not os.path.exists(path):
            logger.info("Creating new image_cache.db at %s", path)
        conn = sqlite3.connect(path)
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

    def _ensure_parent_folder(self, path):
        folder = os.path.dirname(path)
        if folder and not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)

    def _merge_dicts(self, base, override):
        merged = {}
        for key, value in base.items():
            if isinstance(value, dict):
                merged[key] = self._merge_dicts(value, (override or {}).get(key, {}))
            else:
                merged[key] = (override or {}).get(key, value)
        for key, value in (override or {}).items():
            if key not in merged:
                merged[key] = value
        return merged

    def _normalize_config(self, config):
        normalized = dict(config or {})
        api_config = dict(normalized.get("API", {}))
        api_config.pop("GOOGLE_SCRIPT_URL", None)
        normalized["API"] = api_config
        return normalized
