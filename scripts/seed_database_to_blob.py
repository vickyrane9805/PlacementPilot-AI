"""Seed a private Vercel Blob store with an existing PlacementPilot SQLite DB.

Windows PowerShell:
  $env:BLOB_READ_WRITE_TOKEN="vercel_read_write_token"
  python scripts/seed_database_to_blob.py --db data/placementpilot.db
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.blob_backup import seed_database_to_blob

def main():
    parser = argparse.ArgumentParser(description="Upload an existing PlacementPilot SQLite database to private Vercel Blob.")
    parser.add_argument("--db", default=str(ROOT / "data" / "placementpilot.db"), help="Path to existing placementpilot.db")
    args = parser.parse_args()
    token = os.getenv("BLOB_READ_WRITE_TOKEN") or os.getenv("VERCEL_BLOB_READ_WRITE_TOKEN")
    if not token:
        raise SystemExit("Set BLOB_READ_WRITE_TOKEN in your terminal before running this script.")
    db_path = Path(args.db).expanduser().resolve()
    if not db_path.is_file():
        raise SystemExit(f"Database file not found: {db_path}")
    uploaded = seed_database_to_blob(db_path, token=token)
    print(f"Database backup uploaded successfully: {uploaded}")

if __name__ == "__main__":
    main()
