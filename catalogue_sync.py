import base64
import datetime
import json
import logging
import os
import re
from urllib import error, parse, request


logger = logging.getLogger(__name__)


class CatalogueSyncError(Exception):
    pass


class GitHubCatalogueSync:
    API_BASE = "https://api.github.com"

    def __init__(self, initializer):
        self.initializer = initializer

    def sync_if_enabled(self):
        config = self.initializer.load_config()
        sync_config = dict(config.get("WEB_SYNC", {}))
        if not self._is_enabled(sync_config):
            return {"attempted": False, "updated": False, "reason": "disabled"}

        catalogue_path = self.initializer.resolve_file_path(
            config.get("FILES", {}).get("COMPONENT_CATALOGUE", ""),
            "COMPONENT_CATALOGUE",
        )
        return self.sync_catalogue(catalogue_path, sync_config)

    def sync_catalogue(self, catalogue_path, sync_config):
        self._validate_config(sync_config)
        local_text = self._read_catalogue_text(catalogue_path)
        remote_info = self._fetch_remote_metadata(sync_config)
        remote_text = remote_info.get("text", "")
        if local_text == remote_text:
            self.initializer.clear_sync_error()
            return {"attempted": True, "updated": False, "reason": "unchanged"}

        commit_message = (
            sync_config.get("COMMIT_MESSAGE", "").strip()
            or "Update component catalogue from L.E.A.D. desktop app"
        )
        self._upload_catalogue(local_text, remote_info.get("sha"), sync_config, commit_message)
        self.initializer.clear_sync_error()
        return {"attempted": True, "updated": True, "reason": "uploaded"}

    def save_failed_export(self, source_path):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        export_folder = os.path.join(self.initializer.database_folder, "pending_catalogue_exports")
        os.makedirs(export_folder, exist_ok=True)
        export_path = os.path.join(export_folder, f"component_catalogue_{timestamp}.json")
        with open(source_path, "rb") as source_file, open(export_path, "wb") as export_file:
            export_file.write(source_file.read())
        return export_path

    def _is_enabled(self, sync_config):
        value = sync_config.get("ENABLED", False)
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def _validate_config(self, sync_config):
        required = {
            "REPOSITORY": "Repository name",
            "BRANCH": "Branch",
            "TARGET_PATH": "Repository file path",
            "ACCESS_TOKEN": "GitHub access token",
        }
        missing = [label for key, label in required.items() if not str(sync_config.get(key, "")).strip()]
        if missing:
            raise CatalogueSyncError(f"Website sync is enabled but missing: {', '.join(missing)}.")
        self._resolve_repo_target(sync_config)

    def _read_catalogue_text(self, catalogue_path):
        try:
            with open(catalogue_path, "r", encoding="utf-8") as file:
                return file.read()
        except OSError as exc:
            raise CatalogueSyncError(f"Could not read catalogue file: {catalogue_path}") from exc

    def _build_contents_url(self, sync_config):
        owner_name, repo_name = self._resolve_repo_target(sync_config)
        owner = parse.quote(owner_name)
        repo = parse.quote(repo_name)
        target_path = parse.quote(str(sync_config.get("TARGET_PATH", "")).strip().lstrip("/"), safe="/")
        branch = parse.quote(str(sync_config.get("BRANCH", "")).strip())
        return f"{self.API_BASE}/repos/{owner}/{repo}/contents/{target_path}?ref={branch}"

    def _headers(self, sync_config):
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {str(sync_config.get('ACCESS_TOKEN', '')).strip()}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "LEAD-Inventory-App",
        }

    def _fetch_remote_metadata(self, sync_config):
        req = request.Request(self._build_contents_url(sync_config), headers=self._headers(sync_config), method="GET")
        try:
            with request.urlopen(req, timeout=15) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            if exc.code == 404:
                return {"sha": None, "text": ""}
            details = self._read_http_error(exc)
            raise CatalogueSyncError(f"GitHub catalogue lookup failed: {details}") from exc
        except error.URLError as exc:
            raise CatalogueSyncError(f"GitHub catalogue lookup failed: {exc.reason}") from exc

        encoded = str(payload.get("content", "")).replace("\n", "")
        remote_text = ""
        if encoded:
            try:
                remote_text = base64.b64decode(encoded).decode("utf-8")
            except Exception as exc:
                raise CatalogueSyncError("GitHub returned an unreadable catalogue file.") from exc
        return {"sha": payload.get("sha"), "text": remote_text}

    def _upload_catalogue(self, local_text, current_sha, sync_config, commit_message):
        payload = {
            "message": commit_message,
            "content": base64.b64encode(local_text.encode("utf-8")).decode("ascii"),
            "branch": str(sync_config.get("BRANCH", "")).strip(),
        }
        if current_sha:
            payload["sha"] = current_sha

        target_path = parse.quote(str(sync_config.get("TARGET_PATH", "")).strip().lstrip("/"), safe="/")
        owner_name, repo_name = self._resolve_repo_target(sync_config)
        owner = parse.quote(owner_name)
        repo = parse.quote(repo_name)
        url = f"{self.API_BASE}/repos/{owner}/{repo}/contents/{target_path}"
        body = json.dumps(payload).encode("utf-8")
        headers = dict(self._headers(sync_config))
        headers["Content-Type"] = "application/json"
        req = request.Request(url, data=body, headers=headers, method="PUT")
        try:
            with request.urlopen(req, timeout=20):
                return
        except error.HTTPError as exc:
            details = self._read_http_error(exc)
            raise CatalogueSyncError(f"GitHub upload failed: {details}") from exc
        except error.URLError as exc:
            raise CatalogueSyncError(f"GitHub upload failed: {exc.reason}") from exc

    def _read_http_error(self, exc):
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        if body:
            try:
                payload = json.loads(body)
                if isinstance(payload, dict):
                    return payload.get("message") or body
            except json.JSONDecodeError:
                return body
        return f"HTTP {exc.code}"

    def _resolve_repo_target(self, sync_config):
        owner = str(sync_config.get("GITHUB_OWNER", "")).strip()
        repository = str(sync_config.get("REPOSITORY", "")).strip()
        if not repository:
            raise CatalogueSyncError("Website sync is enabled but missing: Repository name.")

        normalized = repository.rstrip("/")
        url_match = re.match(r"^https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", normalized, flags=re.IGNORECASE)
        if url_match:
            return url_match.group(1), url_match.group(2)

        slug_match = re.match(r"^([^/]+)/([^/]+)$", normalized)
        if slug_match:
            return slug_match.group(1), slug_match.group(2)

        if not owner:
            raise CatalogueSyncError(
                "Enter either a GitHub Username plus Repository Name, or put OWNER/REPO in the Repository Name field."
            )
        return owner, normalized
