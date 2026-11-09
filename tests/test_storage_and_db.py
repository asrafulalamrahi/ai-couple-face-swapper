"""
Unit and Integration Tests for Antigravity AI
Tests Google Drive storage manager, SQLite database, and API endpoints.
"""

import os
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile
import sqlite3

# Test database
from backend.database import (
    init_db,
    record_image,
    record_job,
    get_image_by_filename,
    get_image_by_drive_id,
    list_gallery_images,
    mark_image_deleted,
    sync_drive_file_metadata,
)
from backend.google_drive_storage import GoogleDriveStorage


class TestDatabaseAndStorage(unittest.TestCase):

    def setUp(self):
        init_db()

    def test_database_image_crud(self):
        """Test recording, retrieving, listing, and soft-deleting an image."""
        img_id = record_image(
            user_id="user_test_1",
            image_role="generated_output",
            filename="test_result_123.jpg",
            drive_file_id="drive_file_abc",
            drive_folder="Generated-Images",
            job_id="job_123",
            file_size=1024,
        )
        self.assertGreater(img_id, 0)

        # Retrieve by filename
        rec = get_image_by_filename("test_result_123.jpg")
        self.assertIsNotNone(rec)
        self.assertEqual(rec["drive_file_id"], "drive_file_abc")
        self.assertEqual(rec["user_id"], "user_test_1")

        # Retrieve by drive ID
        rec_drive = get_image_by_drive_id("drive_file_abc")
        self.assertIsNotNone(rec_drive)
        self.assertEqual(rec_drive["filename"], "test_result_123.jpg")

        # List in gallery
        gallery = list_gallery_images(user_id="user_test_1")
        self.assertTrue(any(item["filename"] == "test_result_123.jpg" for item in gallery))

        # Delete image
        deleted = mark_image_deleted("drive_file_abc", user_id="user_test_1")
        self.assertTrue(deleted)

        # Verify not returned in active search
        self.assertIsNone(get_image_by_filename("test_result_123.jpg"))

    def test_database_cold_restart_sync(self):
        """Test automatic re-indexing from Google Drive files after container restart."""
        sync_drive_file_metadata(
            drive_file_id="gdrive_synced_001",
            filename="antigravity_result_recovered.jpg",
            folder_name="Generated-Images",
            user_id="recovered_user",
            image_role="generated_output",
            file_size=2048,
        )
        rec = get_image_by_drive_id("gdrive_synced_001")
        self.assertIsNotNone(rec)
        self.assertEqual(rec["filename"], "antigravity_result_recovered.jpg")

    def test_gdrive_unconfigured_fallback(self):
        """Test that unconfigured storage returns graceful fallback."""
        storage = GoogleDriveStorage()
        storage.client_id = ""
        storage.client_secret = ""
        storage.refresh_token = ""
        storage.service_account_json = ""

        self.assertFalse(storage.is_configured())
        res = storage.upload_file(b"test data", "test.jpg")
        self.assertEqual(res.get("status"), "unconfigured")
        self.assertIsNone(res.get("file_id"))

    @patch("backend.google_drive_storage.requests.Session.post")
    def test_gdrive_oauth_refresh_token(self, mock_post):
        """Test token refresh logic using mock."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "access_token": "mock_access_token_xyz",
            "expires_in": 3600,
        }
        mock_post.return_value = mock_resp

        storage = GoogleDriveStorage()
        storage.client_id = "mock_client"
        storage.client_secret = "mock_secret"
        storage.refresh_token = "mock_refresh"

        token = storage._get_access_token()
        self.assertEqual(token, "mock_access_token_xyz")

    @patch("backend.google_drive_storage.requests.Session.post")
    def test_gdrive_multipart_upload(self, mock_post):
        """Test multipart upload with mock."""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "id": "new_drive_id_789",
            "name": "result.jpg",
            "size": "500",
            "mimeType": "image/jpeg",
        }

        storage = GoogleDriveStorage()
        storage._access_token = "valid_token"
        storage._token_expiry_timestamp = 9999999999.0

        res = storage._multipart_upload(
            data=b"imagebytes",
            metadata={"name": "result.jpg"},
            mime_type="image/jpeg",
        )
        self.assertEqual(res["file_id"], "new_drive_id_789")
        self.assertEqual(res["status"], "success")


if __name__ == "__main__":
    unittest.main()

