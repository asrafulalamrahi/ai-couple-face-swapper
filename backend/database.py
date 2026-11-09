"""
Antigravity AI - Metadata & Generation History Database
SQLite-backed persistent store for user images, Drive file mappings, and generation history.
Includes automatic re-indexing from Google Drive metadata across ephemeral container restarts.
"""

import os
import json
import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

logger = logging.getLogger("antigravity.database")

DB_DIR = Path(__file__).resolve().parent / "antigravity_storage"
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DB_DIR / "antigravity_metadata.db"


def get_db_connection() -> sqlite3.Connection:
    """Returns a thread-safe sqlite3 connection with Row factory."""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initializes tables for images, jobs, and user associations."""
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    job_id TEXT,
                    image_role TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    drive_file_id TEXT,
                    drive_folder TEXT,
                    mime_type TEXT DEFAULT 'image/jpeg',
                    file_size INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    deleted INTEGER DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    husband_drive_id TEXT,
                    wife_drive_id TEXT,
                    target_drive_id TEXT,
                    output_drive_id TEXT,
                    output_filename TEXT,
                    metadata_json TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_images_user ON images(user_id, deleted)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_images_filename ON images(filename)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_images_drive_id ON images(drive_file_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_jobs_user ON jobs(user_id)
            """)
        logger.info(f"Database initialized at {DB_PATH}")
    finally:
        conn.close()


def record_image(
    user_id: str,
    image_role: str,
    filename: str,
    drive_file_id: Optional[str] = None,
    drive_folder: Optional[str] = None,
    job_id: Optional[str] = None,
    mime_type: str = "image/jpeg",
    file_size: int = 0,
) -> int:
    """Inserts a new image record and returns its ID."""
    conn = get_db_connection()
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        with conn:
            cursor = conn.execute(
                """
                INSERT INTO images (
                    user_id, job_id, image_role, filename,
                    drive_file_id, drive_folder, mime_type, file_size, created_at, deleted
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    user_id,
                    job_id,
                    image_role,
                    filename,
                    drive_file_id,
                    drive_folder,
                    mime_type,
                    file_size,
                    now_iso,
                ),
            )
            return cursor.lastrowid
    finally:
        conn.close()


def update_image_drive_id(filename: str, drive_file_id: str, drive_folder: Optional[str] = None):
    """Updates the Drive file ID for a stored filename."""
    conn = get_db_connection()
    try:
        with conn:
            conn.execute(
                """
                UPDATE images
                SET drive_file_id = ?, drive_folder = COALESCE(?, drive_folder)
                WHERE filename = ? AND deleted = 0
                """,
                (drive_file_id, drive_folder, filename),
            )
    finally:
        conn.close()


def record_job(
    job_id: str,
    user_id: str,
    status: str,
    output_filename: str,
    husband_drive_id: Optional[str] = None,
    wife_drive_id: Optional[str] = None,
    target_drive_id: Optional[str] = None,
    output_drive_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
):
    """Records a complete face swap job execution."""
    conn = get_db_connection()
    now_iso = datetime.now(timezone.utc).isoformat()
    metadata_json = json.dumps(metadata or {})
    try:
        with conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO jobs (
                    job_id, user_id, status, husband_drive_id, wife_drive_id,
                    target_drive_id, output_drive_id, output_filename, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    user_id,
                    status,
                    husband_drive_id,
                    wife_drive_id,
                    target_drive_id,
                    output_drive_id,
                    output_filename,
                    metadata_json,
                    now_iso,
                ),
            )
    finally:
        conn.close()


def get_image_by_filename(filename: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieves an active image record by filename, optionally filtered by user_id."""
    conn = get_db_connection()
    try:
        if user_id:
            cur = conn.execute(
                "SELECT * FROM images WHERE filename = ? AND user_id = ? AND deleted = 0 ORDER BY id DESC LIMIT 1",
                (filename, user_id),
            )
        else:
            cur = conn.execute(
                "SELECT * FROM images WHERE filename = ? AND deleted = 0 ORDER BY id DESC LIMIT 1",
                (filename,),
            )
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_image_by_drive_id(drive_file_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieves an active image record by Drive file ID."""
    conn = get_db_connection()
    try:
        if user_id:
            cur = conn.execute(
                "SELECT * FROM images WHERE drive_file_id = ? AND user_id = ? AND deleted = 0 LIMIT 1",
                (drive_file_id, user_id),
            )
        else:
            cur = conn.execute(
                "SELECT * FROM images WHERE drive_file_id = ? AND deleted = 0 LIMIT 1",
                (drive_file_id,),
            )
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_gallery_images(user_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Lists generated images for gallery view, sorted newest first."""
    conn = get_db_connection()
    try:
        if user_id:
            cur = conn.execute(
                """
                SELECT filename, drive_file_id, mime_type, file_size, created_at, job_id
                FROM images
                WHERE user_id = ? AND image_role IN ('generated_output', 'refined_output') AND deleted = 0
                ORDER BY id DESC
                LIMIT ?
                """,
                (user_id, limit),
            )
        else:
            cur = conn.execute(
                """
                SELECT filename, drive_file_id, mime_type, file_size, created_at, job_id, user_id
                FROM images
                WHERE image_role IN ('generated_output', 'refined_output') AND deleted = 0
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def mark_image_deleted(identifier: str, user_id: Optional[str] = None) -> bool:
    """Marks an image as deleted by drive_file_id or filename."""
    conn = get_db_connection()
    try:
        with conn:
            if user_id:
                cur = conn.execute(
                    """
                    UPDATE images
                    SET deleted = 1
                    WHERE (drive_file_id = ? OR filename = ?) AND user_id = ?
                    """,
                    (identifier, identifier, user_id),
                )
            else:
                cur = conn.execute(
                    """
                    UPDATE images
                    SET deleted = 1
                    WHERE drive_file_id = ? OR filename = ?
                    """,
                    (identifier, identifier),
                )
            return cur.rowcount > 0
    finally:
        conn.close()


def sync_drive_file_metadata(
    drive_file_id: str,
    filename: str,
    folder_name: str,
    user_id: str = "anonymous",
    job_id: Optional[str] = None,
    image_role: str = "generated_output",
    file_size: int = 0,
):
    """
    Idempotently syncs a file discovered from Google Drive into SQLite.
    Allows cold container restarts to rebuild metadata from Drive automatically.
    """
    conn = get_db_connection()
    try:
        with conn:
            cur = conn.execute(
                "SELECT id FROM images WHERE drive_file_id = ?",
                (drive_file_id,),
            )
            row = cur.fetchone()
            if not row:
                now_iso = datetime.now(timezone.utc).isoformat()
                conn.execute(
                    """
                    INSERT INTO images (
                        user_id, job_id, image_role, filename,
                        drive_file_id, drive_folder, mime_type, file_size, created_at, deleted
                    ) VALUES (?, ?, ?, ?, ?, ?, 'image/jpeg', ?, ?, 0)
                    """,
                    (user_id, job_id, image_role, filename, drive_file_id, folder_name, file_size, now_iso),
                )
    finally:
        conn.close()

