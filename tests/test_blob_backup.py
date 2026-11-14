import sqlite3

from src import blob_backup, database


def test_sqlite_snapshot_is_valid_and_contains_committed_rows(tmp_path):
    db_file = tmp_path / "placementpilot.db"
    with sqlite3.connect(db_file) as con:
        con.execute("CREATE TABLE sample (value TEXT)")
        con.execute("INSERT INTO sample(value) VALUES ('saved')")
    snapshot = blob_backup._snapshot_database(db_file)
    assert blob_backup._is_valid_sqlite_bytes(snapshot)
    assert not blob_backup._is_valid_sqlite_bytes(b"not a database")
    with __import__("tempfile").NamedTemporaryFile(suffix=".db") as temp:
        temp.write(snapshot)
        temp.flush()
        with sqlite3.connect(temp.name) as con:
            assert con.execute("SELECT value FROM sample").fetchone()[0] == "saved"


def test_database_write_triggers_cloud_backup_when_configured(tmp_path, monkeypatch):
    db_file = tmp_path / "placementpilot.db"
    monkeypatch.setattr(database, "DB_PATH", db_file)
    calls = []
    monkeypatch.setattr(blob_backup, "get_blob_token", lambda: "test-token")
    monkeypatch.setattr(blob_backup, "backup_database", lambda path: calls.append(path) or "backup.db")
    database.init_db()
    database.add_application("Example Co", "AI Intern", "Pune", "2026-11-14", "Saved", "https://example.com", "")
    assert calls == [db_file]


def test_database_reads_do_not_trigger_cloud_backup(tmp_path, monkeypatch):
    db_file = tmp_path / "placementpilot.db"
    monkeypatch.setattr(database, "DB_PATH", db_file)
    calls = []
    monkeypatch.setattr(blob_backup, "get_blob_token", lambda: "test-token")
    monkeypatch.setattr(blob_backup, "backup_database", lambda path: calls.append(path) or "backup.db")
    database.init_db()
    calls.clear()
    database.get_applications()
    assert calls == []
