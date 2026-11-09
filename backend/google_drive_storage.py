"""
Antigravity AI - Google Drive v3 Storage Engine
Provides persistent, authenticated cloud storage for user uploads and AI-generated outputs.

Features:
- OAuth 2.0 automatic token refresh (GOOGLE_DRIVE_CLIENT_ID, GOOGLE_DRIVE_CLIENT_SECRET, GOOGLE_DRIVE_REFRESH_TOKEN)
- Service Account fallback support (GOOGLE_SERVICE_ACCOUNT_JSON)
- Dedicated folder hierarchy:
    AI-Couple-Face-Swapper/
      ├── Original-Uploads/
      ├── Generated-Images/
      ├── User-Images/
      └── Backups/
- Resumable and multipart upload support with retry & exponential backoff
- Secure authenticated media streaming (files stay private in Drive)
- AppProperties metadata tagging for state reconstruction after Render restarts
- Deletion handling and graceful fallback to local storage when unconfigured
"""

import os
import io
import time
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Generator, Tuple, List

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger("antigravity.gdrive")

# Token refresh endpoint
GOOGLE_OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
DRIVE_API_BASE = "https://www.googleapis.com/drive/v3"
DRIVE_UPLOAD_BASE = "https://www.googleapis.com/upload/drive/v3"

REQUIRED_SUBFOLDERS = [
    "Original-Uploads",
    "Generated-Images",
    "User-Images",
    "Backups",
]


class GoogleDriveStorage:
    """Manages Google Drive API v3 operations for the Couple Face Refacer."""

    def __init__(self):
        self.client_id = os.environ.get("GOOGLE_DRIVE_CLIENT_ID", "").strip()
        self.client_secret = os.environ.get("GOOGLE_DRIVE_CLIENT_SECRET", "").strip()
        self.refresh_token = os.environ.get("GOOGLE_DRIVE_REFRESH_TOKEN", "").strip()
        self.root_folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "").strip()
        self.service_account_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()

        self._access_token: Optional[str] = None
        self._token_expiry_timestamp: float = 0.0
        self._folder_cache: Dict[str, str] = {}  # folder_name -> folder_id

        # Robust requests session with retry logic
        self.session = requests.Session()
        retries = Retry(
            total=4,
            backoff_factor=1.5,
            status_forcelist=[429, 500, 502, 503, 504],
            raise_on_status=False,
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retries))

    def is_configured(self) -> bool:
        """Checks if valid credentials are present in the environment."""
        has_oauth = bool(self.client_id and self.client_secret and self.refresh_token)
        has_service_account = bool(self.service_account_json)
        return has_oauth or has_service_account

    # ──────────────────────────────────────────────
    # Authentication & Token Management
    # ──────────────────────────────────────────────

    def _get_access_token(self) -> str:
        """Retrieves or refreshes OAuth 2.0 access token."""
        now = time.time()
        # Refresh 5 minutes before expiry
        if self._access_token and (now < self._token_expiry_timestamp - 300):
            return self._access_token

        if self.service_account_json:
            return self._get_service_account_token()

        if not (self.client_id and self.client_secret and self.refresh_token):
            raise RuntimeError("Google Drive credentials not configured.")

        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token",
        }

        resp = self.session.post(GOOGLE_OAUTH_TOKEN_URL, data=payload, timeout=20)
        if resp.status_code != 200:
            logger.error(f"Failed to refresh Google OAuth token: {resp.text}")
            resp.raise_for_status()

        data = resp.json()
        self._access_token = data["access_token"]
        expires_in = data.get("expires_in", 3600)
        self._token_expiry_timestamp = now + expires_in
        logger.info("Google Drive OAuth access token refreshed successfully.")
        return self._access_token

    def _get_service_account_token(self) -> str:
        """Handles service account authentication if provided."""
        try:
            from google.oauth2 import service_account
            import google.auth.transport.requests

            if os.path.exists(self.service_account_json):
                creds = service_account.Credentials.from_service_account_file(
                    self.service_account_json,
                    scopes=["https://www.googleapis.com/auth/drive"],
                )
            else:
                info = json.loads(self.service_account_json)
                creds = service_account.Credentials.from_service_account_info(
                    info,
                    scopes=["https://www.googleapis.com/auth/drive"],
                )
            req = google.auth.transport.requests.Request()
            creds.refresh(req)
            self._access_token = creds.token
            self._token_expiry_timestamp = creds.expiry.timestamp() if creds.expiry else time.time() + 3600
            return self._access_token
        except Exception as e:
            logger.error(f"Service account token refresh failed: {e}")
            raise

    def _auth_headers(self) -> Dict[str, str]:
        token = self._get_access_token()
        return {"Authorization": f"Bearer {token}"}

    # ──────────────────────────────────────────────
    # Folder Structure Management
    # ──────────────────────────────────────────────

    def ensure_folder_structure(self) -> Dict[str, str]:
        """
        Ensures the root and all 4 required subfolders exist:
        AI-Couple-Face-Swapper/
          ├── Original-Uploads/
          ├── Generated-Images/
          ├── User-Images/
          └── Backups/
        """
        if not self.is_configured():
            return {}

        headers = self._auth_headers()

        # 1. Resolve Root Folder
        root_id = self.root_folder_id
        if not root_id:
            root_id = self._find_or_create_folder("AI-Couple-Face-Swapper", parent_id=None, headers=headers)
            self.root_folder_id = root_id

        self._folder_cache["root"] = root_id

        # 2. Resolve Subfolders
        for sub in REQUIRED_SUBFOLDERS:
            sub_id = self._find_or_create_folder(sub, parent_id=root_id, headers=headers)
            self._folder_cache[sub] = sub_id

        logger.info(f"Google Drive folder hierarchy verified: {self._folder_cache}")
        return self._folder_cache

    def _find_or_create_folder(self, name: str, parent_id: Optional[str], headers: Dict[str, str]) -> str:
        """Finds existing folder or creates it under parent."""
        # Query existing
        query = f"name = '{name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        if parent_id:
            query += f" and '{parent_id}' in parents"

        url = f"{DRIVE_API_BASE}/files"
        params = {"q": query, "fields": "files(id, name)", "pageSize": 1}
        resp = self.session.get(url, headers=headers, params=params, timeout=20)
        if resp.status_code == 200:
            files = resp.json().get("files", [])
            if files:
                return files[0]["id"]

        # Create folder
        meta: Dict[str, Any] = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        if parent_id:
            meta["parents"] = [parent_id]

        create_resp = self.session.post(
            f"{DRIVE_API_BASE}/files",
            headers={"Content-Type": "application/json", **headers},
            json=meta,
            timeout=20,
        )
        create_resp.raise_for_status()
        new_id = create_resp.json()["id"]
        logger.info(f"Created Google Drive folder: '{name}' (ID: {new_id})")
        return new_id

    def get_folder_id(self, folder_name: str) -> Optional[str]:
        """Gets cached folder ID or resolves hierarchy."""
        if folder_name in self._folder_cache:
            return self._folder_cache[folder_name]
        self.ensure_folder_structure()
        return self._folder_cache.get(folder_name)

    # ──────────────────────────────────────────────
    # File Uploads (Multipart & Resumable)
    # ──────────────────────────────────────────────

    def upload_file(
        self,
        file_path_or_bytes: Any,
        filename: str,
        folder_name: str = "Generated-Images",
        user_id: str = "anonymous",
        job_id: Optional[str] = None,
        image_role: str = "generated_output",
        mime_type: str = "image/jpeg",
    ) -> Dict[str, Any]:
        """
        Uploads file or bytes to the designated subfolder in Google Drive.
        Attaches appProperties for cloud metadata recovery.
        """
        if not self.is_configured():
            logger.warning("Google Drive storage not configured. Skipping cloud upload.")
            return {"file_id": None, "status": "unconfigured"}

        folder_id = self.get_folder_id(folder_name)
        if not folder_id:
            raise RuntimeError(f"Target Google Drive folder '{folder_name}' not resolved.")

        # Prepare payload bytes
        if isinstance(file_path_or_bytes, (str, Path)):
            with open(file_path_or_bytes, "rb") as f:
                data = f.read()
        elif isinstance(file_path_or_bytes, bytes):
            data = file_path_or_bytes
        else:
            data = file_path_or_bytes.read()

        file_size = len(data)
        metadata = {
            "name": filename,
            "parents": [folder_id],
            "appProperties": {
                "user_id": str(user_id),
                "job_id": str(job_id or ""),
                "image_role": str(image_role),
                "original_filename": str(filename),
            },
        }

        # Use Resumable Upload for files >= 5MB
        if file_size >= 5 * 1024 * 1024:
            return self._resumable_upload(data, metadata, mime_type)
        else:
            return self._multipart_upload(data, metadata, mime_type)

    def _multipart_upload(self, data: bytes, metadata: dict, mime_type: str) -> Dict[str, Any]:
        """Executes multipart upload for fast upload of images <5MB."""
        headers = self._auth_headers()
        url = f"{DRIVE_UPLOAD_BASE}/files?uploadType=multipart&fields=id,name,size,mimeType"

        files = {
            "data": ("metadata", json.dumps(metadata), "application/json; charset=UTF-8"),
            "file": (metadata["name"], io.BytesIO(data), mime_type),
        }

        resp = self.session.post(url, headers=headers, files=files, timeout=45)
        resp.raise_for_status()
        res_data = resp.json()
        logger.info(f"Uploaded to Google Drive (multipart): {res_data.get('name')} (ID: {res_data.get('id')})")
        return {
            "file_id": res_data.get("id"),
            "name": res_data.get("name"),
            "size": int(res_data.get("size", len(data))),
            "mime_type": res_data.get("mimeType", mime_type),
            "status": "success",
        }

    def _resumable_upload(self, data: bytes, metadata: dict, mime_type: str) -> Dict[str, Any]:
        """Executes chunked resumable upload for larger images."""
        headers = {
            **self._auth_headers(),
            "X-Upload-Content-Type": mime_type,
            "X-Upload-Content-Length": str(len(data)),
            "Content-Type": "application/json; charset=UTF-8",
        }
        init_url = f"{DRIVE_UPLOAD_BASE}/files?uploadType=resumable&fields=id,name,size,mimeType"
        init_resp = self.session.post(init_url, headers=headers, json=metadata, timeout=30)
        init_resp.raise_for_status()

        upload_session_url = init_resp.headers.get("Location")
        if not upload_session_url:
            raise RuntimeError("Failed to obtain resumable upload location from Drive API.")

        # Upload binary in chunks
        chunk_size = 256 * 1024 * 4  # 1MB chunks
        total_size = len(data)
        offset = 0

        while offset < total_size:
            end = min(offset + chunk_size, total_size)
            chunk = data[offset:end]
            chunk_headers = {
                "Content-Length": str(len(chunk)),
                "Content-Range": f"bytes {offset}-{end - 1}/{total_size}",
            }
            c_resp = self.session.put(upload_session_url, headers=chunk_headers, data=chunk, timeout=60)
            if c_resp.status_code in (200, 201):
                res_data = c_resp.json()
                logger.info(f"Resumable upload complete: {res_data.get('name')} (ID: {res_data.get('id')})")
                return {
                    "file_id": res_data.get("id"),
                    "name": res_data.get("name"),
                    "size": int(res_data.get("size", total_size)),
                    "mime_type": res_data.get("mimeType", mime_type),
                    "status": "success",
                }
            elif c_resp.status_code == 308:
                offset = end
            else:
                c_resp.raise_for_status()

        raise RuntimeError("Resumable upload terminated unexpectedly.")

    # ──────────────────────────────────────────────
    # Secure Image Retrieval & Streaming
    # ──────────────────────────────────────────────

    def get_file_metadata(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves file metadata without public exposure."""
        if not self.is_configured():
            return None
        headers = self._auth_headers()
        url = f"{DRIVE_API_BASE}/files/{file_id}"
        params = {"fields": "id, name, size, mimeType, appProperties, trashed"}
        resp = self.session.get(url, headers=headers, params=params, timeout=20)
        if resp.status_code == 200:
            return resp.json()
        return None

    def stream_file_content(self, file_id: str, chunk_size: int = 64 * 1024) -> Generator[bytes, None, None]:
        """Streams file bytes directly from Drive using authenticated backend credentials."""
        headers = self._auth_headers()
        url = f"{DRIVE_API_BASE}/files/{file_id}?alt=media"
        with self.session.get(url, headers=headers, stream=True, timeout=45) as resp:
            resp.raise_for_status()
            for chunk in resp.iter_content(chunk_size=chunk_size):
                if chunk:
                    yield chunk

    def download_bytes(self, file_id: str) -> bytes:
        """Downloads full file into bytes buffer."""
        headers = self._auth_headers()
        url = f"{DRIVE_API_BASE}/files/{file_id}?alt=media"
        resp = self.session.get(url, headers=headers, timeout=45)
        resp.raise_for_status()
        return resp.content

    # ──────────────────────────────────────────────
    # Deletion & Sync Operations
    # ──────────────────────────────────────────────

    def delete_file(self, file_id: str) -> bool:
        """Deletes file permanently from Google Drive."""
        if not self.is_configured():
            return False
        headers = self._auth_headers()
        url = f"{DRIVE_API_BASE}/files/{file_id}"
        resp = self.session.delete(url, headers=headers, timeout=20)
        if resp.status_code in (200, 204):
            logger.info(f"Deleted file {file_id} from Google Drive.")
            return True
        logger.warning(f"Delete file {file_id} failed: {resp.status_code} {resp.text}")
        return False

    def list_files_in_folder(self, folder_name: str) -> List[Dict[str, Any]]:
        """Lists files inside a named folder with their appProperties for cold-restart syncing."""
        if not self.is_configured():
            return []
        folder_id = self.get_folder_id(folder_name)
        if not folder_id:
            return []

        headers = self._auth_headers()
        url = f"{DRIVE_API_BASE}/files"
        query = f"'{folder_id}' in parents and trashed = false"
        params = {
            "q": query,
            "fields": "files(id, name, size, mimeType, createdTime, appProperties)",
            "pageSize": 100,
            "orderBy": "createdTime desc",
        }
        resp = self.session.get(url, headers=headers, params=params, timeout=25)
        if resp.status_code == 200:
            return resp.json().get("files", [])
        return []


# Global singleton instance
drive_storage = GoogleDriveStorage()
