"""Private Vercel Blob backups for the existing SQLite database.

The app continues to use one local SQLite file (placementpilot.db).
Backups are immutable timestamped snapshots stored in a private Blob store.
"""
from __future__ import annotations

import logging
import os
import sqlite3
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

BACKUP_PREFIX = "placementpilot/sqlite-backups/"
KEEP_BACKUPS = 20
_CLEANUP_EVERY_UPLOADS = 25
_backup_lock = threading.Lock()
_uploads_since_cleanup = 0


def get_blob_token() -> str:
    """Read the private Blob token from environment or Streamlit secrets."""
    token = os.getenv("BLOB_READ_WRITE_TOKEN") or os.getenv("VERCEL_BLOB_READ_WRITE_TOKEN")
    if token:
        return token.strip()
    try:
        import streamlit as st
        token = st.secrets.get("BLOB_READ_WRITE_TOKEN", "")
    except Exception:
        token = ""
    token = str(token).strip() if token else ""
    if token:
        # The official Python SDK resolves its read-write token from the process
        # environment. Streamlit Secrets are copied into memory, never to disk.
        os.environ["BLOB_READ_WRITE_TOKEN"] = token
    return token


def _blob_sdk():
    try:
        from vercel.blob import sync as blob
    except ImportError as exc:
        raise RuntimeError(
            "Vercel Blob SDK is missing. Install requirements.txt (vercel-blob>=0.5.0)."
        ) from exc
    return blob


def _list_backups(blob):
    return list(blob.query_blobs(prefix=BACKUP_PREFIX))


def _is_valid_sqlite_bytes(data: bytes) -> bool:
    if not data.startswith(b"SQLite format 3\x00"):
        return False
    fd, temp_name = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        Path(temp_name).write_bytes(data)
        con = sqlite3.connect(temp_name)
        try:
            result = con.execute("PRAGMA integrity_check").fetchone()
            return bool(result and result[0] == "ok")
        except sqlite3.DatabaseError:
            return False
        finally:
            con.close()
    finally:
        Path(temp_name).unlink(missing_ok=True)


def _snapshot_database(db_path: Path) -> bytes:
    """Use SQLite's online backup API so WAL data is included consistently."""
    db_path = Path(db_path)
    if not db_path.exists():
        raise FileNotFoundError(f"SQLite database not found: {db_path}")
    fd, target_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        source = sqlite3.connect(str(db_path), timeout=30)
        destination = sqlite3.connect(target_path)
        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()
        data = Path(target_path).read_bytes()
    finally:
        Path(target_path).unlink(missing_ok=True)
    if not _is_valid_sqlite_bytes(data):
        raise sqlite3.DatabaseError("Generated SQLite backup failed integrity validation.")
    return data


def backup_database(db_path: Path, token: Optional[str] = None) -> str:
    """Upload a validated point-in-time SQLite snapshot and prune old copies."""
    global _uploads_since_cleanup
    token = token or get_blob_token()
    if not token:
        return "disabled"
    os.environ["BLOB_READ_WRITE_TOKEN"] = token
    db_path = Path(db_path)
    snapshot = _snapshot_database(db_path)
    blob = _blob_sdk()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    pathname = f"{BACKUP_PREFIX}placementpilot-{stamp}.db"

    # Serialize uploads from concurrent Streamlit sessions in this process.
    with _backup_lock:
        uploaded = blob.put_blob(
            pathname,
            snapshot,
            access="private",
            content_type="application/vnd.sqlite3",
        )
        _uploads_since_cleanup += 1

        # Listing is an advanced Blob operation. Clean up periodically rather
        # than listing on every user write, to conserve the free-tier allowance.
        if _uploads_since_cleanup >= _CLEANUP_EVERY_UPLOADS:
            try:
                backups = _list_backups(blob)
                backups.sort(key=lambda item: item.uploaded_at, reverse=True)
                stale = [item.pathname for item in backups[KEEP_BACKUPS:]]
                if stale:
                    blob.delete_blob(stale)
                _uploads_since_cleanup = 0
            except Exception:
                logger.exception("Backup was uploaded, but old-backup cleanup failed.")

    return uploaded.pathname


def restore_latest_backup(db_path: Path, token: Optional[str] = None) -> Optional[str]:
    """Restore the newest valid private Blob snapshot atomically."""
    token = token or get_blob_token()
    if not token:
        return None
    blob = _blob_sdk()
    backups = _list_backups(blob, token)
    if not backups:
        return None

    backups.sort(key=lambda item: item.uploaded_at, reverse=True)
    last_error = None
    for item in backups:
        try:
            result = blob.get_blob(item.pathname, access="private", token=token)
            data = result.body
            if not _is_valid_sqlite_bytes(data):
                raise sqlite3.DatabaseError("Remote backup failed SQLite integrity validation.")

            db_path = Path(db_path)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                prefix="placementpilot-restore-", suffix=".db",
                dir=str(db_path.parent), delete=False
            ) as temp:
                temp.write(data)
                temp_path = Path(temp.name)

            # Validate the actual temporary file before replacing anything.
            with sqlite3.connect(str(temp_path)) as con:
                check = con.execute("PRAGMA integrity_check").fetchone()
            if not check or check[0] != "ok":
                temp_path.unlink(missing_ok=True)
                raise sqlite3.DatabaseError("Temporary restored database failed integrity validation.")

            # Preserve the current file locally before replacing it.
            if db_path.exists() and db_path.stat().st_size:
                safety_copy = db_path.with_suffix(db_path.suffix + ".before-restore")
                if not safety_copy.exists():
                    import shutil
                    shutil.copy2(db_path, safety_copy)
            os.replace(temp_path, db_path)
            return item.pathname
        except Exception as exc:
            last_error = exc
            logger.exception("Could not restore backup %s; trying the previous snapshot.", item.pathname)

    if last_error:
        raise RuntimeError(f"No valid Vercel Blob backup could be restored: {last_error}") from last_error
    return None


def seed_database_to_blob(db_path: Path, token: Optional[str] = None) -> str:
    """Upload an existing local database as the first cloud backup."""
    return backup_database(Path(db_path), token=token)


def bootstrap_database(db_path: Path) -> dict:
    """Run once at app startup, before database schema initialization."""
    token = get_blob_token()
    if not token:
        return {"configured": False, "restored": False, "backup": None}

    restored = restore_latest_backup(db_path, token=token)
    if restored:
        return {"configured": True, "restored": True, "backup": restored}

    # If this is the first deployment and a local DB was packaged, seed it.
    # If no DB exists yet, normal app writes will create the first backup.
    if Path(db_path).exists() and Path(db_path).stat().st_size:
        seeded = backup_database(db_path, token=token)
        return {"configured": True, "restored": False, "backup": seeded, "seeded": True}
    return {"configured": True, "restored": False, "backup": None}
