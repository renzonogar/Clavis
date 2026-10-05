"""
Clavis Database Layer
SQLite in-memory encrypted session management with full credential CRUD,
history tracking, soft delete, and serialization.
"""

from dataclasses import dataclass
import io
import sqlite3
import time
import uuid
from typing import List, Optional, Dict, Any


@dataclass
class Credential:
    id: str
    title: str
    username: str
    password: str
    url: str
    notes: str
    created_at: int
    updated_at: int
    is_deleted: bool
    deleted_at: Optional[int] = None


@dataclass
class PasswordHistoryEntry:
    id: str
    credential_id: str
    old_password: str
    changed_at: int


class VaultDatabase:
    """
    Manages the transient in-memory SQLite database for Clavis.
    Data lives in RAM during an unlocked session and is serialized
    only for encrypted writes to the storage medium.
    """
    SCHEMA = """
    PRAGMA foreign_keys = ON;

    CREATE TABLE IF NOT EXISTS credentials (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        username TEXT NOT NULL,
        password TEXT NOT NULL,
        url TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL,
        is_deleted INTEGER NOT NULL DEFAULT 0,
        deleted_at INTEGER
    );

    CREATE TABLE IF NOT EXISTS password_history (
        id TEXT PRIMARY KEY,
        credential_id TEXT NOT NULL,
        old_password TEXT NOT NULL,
        changed_at INTEGER NOT NULL,
        FOREIGN KEY(credential_id) REFERENCES credentials(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS vault_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_credentials_deleted ON credentials(is_deleted);
    CREATE INDEX IF NOT EXISTS idx_credentials_title ON credentials(title);
    CREATE INDEX IF NOT EXISTS idx_history_cred_id ON password_history(credential_id);
    """

    def __init__(self):
        self._conn: Optional[sqlite3.Connection] = None
        self._init_memory_db()

    def _init_memory_db(self) -> None:
        self._conn = sqlite3.connect(":memory:", check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._conn:
            self._conn.executescript(self.SCHEMA)

    @property
    def connection(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("Database connection is closed or not initialized.")
        return self._conn

    def close(self) -> None:
        """Closes the in-memory database and drops reference to help garbage collection."""
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def serialize(self) -> bytes:
        """
        Serializes the entire in-memory database to binary bytes for encrypted storage.
        Uses connection.serialize() (available in Python 3.10+ sqlite3) or sqlite3 backup.
        """
        conn = self.connection
        if hasattr(conn, "serialize"):
            try:
                return conn.serialize()
            except Exception:
                pass

        # Fallback using SQLite backup to an in-memory byte buffer
        script = "".join(conn.iterdump())
        return script.encode("utf-8")

    def deserialize(self, data: bytes) -> None:
        """
        Reconstructs in-memory SQLite database from binary bytes.
        """
        self.close()
        self._conn = sqlite3.connect(":memory:", check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

        if hasattr(self._conn, "deserialize"):
            try:
                self._conn.deserialize(data)
                # Verify table exists
                with self._conn:
                    self._conn.executescript(self.SCHEMA)
                return
            except Exception:
                pass

        # Fallback if raw binary deserialize isn't supported or data was script
        try:
            script_str = data.decode("utf-8")
            with self._conn:
                self._conn.executescript(script_str)
        except Exception:
            # If data was a binary SQLite file, load via temp memory backup
            temp_conn = sqlite3.connect(":memory:", check_same_thread=False)
            try:
                if hasattr(temp_conn, "deserialize"):
                    temp_conn.deserialize(data)
                    temp_conn.backup(self._conn)
                else:
                    raise
            finally:
                temp_conn.close()

        with self._conn:
            self._conn.executescript(self.SCHEMA)

    def add_credential(
        self,
        title: str,
        username: str,
        password: str,
        url: str = "",
        notes: str = ""
    ) -> str:
        cred_id = str(uuid.uuid4())
        now = int(time.time())
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO credentials (id, title, username, password, url, notes, created_at, updated_at, is_deleted, deleted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, NULL)
                """,
                (cred_id, title.strip(), username.strip(), password, url.strip(), notes.strip(), now, now)
            )
        return cred_id

    def update_credential(
        self,
        cred_id: str,
        title: str,
        username: str,
        password: str,
        url: str = "",
        notes: str = ""
    ) -> bool:
        cur_cred = self.get_credential(cred_id)
        if not cur_cred:
            return False

        now = int(time.time())
        with self.connection:
            # Record password change in history if modified
            if cur_cred["password"] != password:
                self.connection.execute(
                    """
                    INSERT INTO password_history (id, credential_id, old_password, changed_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (str(uuid.uuid4()), cred_id, cur_cred["password"], now)
                )

            self.connection.execute(
                """
                UPDATE credentials
                SET title = ?, username = ?, password = ?, url = ?, notes = ?, updated_at = ?
                WHERE id = ?
                """,
                (title.strip(), username.strip(), password, url.strip(), notes.strip(), now, cred_id)
            )
        return True

    def soft_delete_credential(self, cred_id: str) -> bool:
        now = int(time.time())
        with self.connection:
            cursor = self.connection.execute(
                "UPDATE credentials SET is_deleted = 1, deleted_at = ? WHERE id = ?",
                (now, cred_id)
            )
            return cursor.rowcount > 0

    def restore_credential(self, cred_id: str) -> bool:
        with self.connection:
            cursor = self.connection.execute(
                "UPDATE credentials SET is_deleted = 0, deleted_at = NULL WHERE id = ?",
                (cred_id,)
            )
            return cursor.rowcount > 0

    def permanently_delete_credential(self, cred_id: str) -> bool:
        with self.connection:
            # Password history cascaded via schema
            self.connection.execute("DELETE FROM password_history WHERE credential_id = ?", (cred_id,))
            cursor = self.connection.execute("DELETE FROM credentials WHERE id = ?", (cred_id,))
            return cursor.rowcount > 0

    def empty_trash(self) -> int:
        with self.connection:
            # Get list of deleted IDs
            rows = self.connection.execute("SELECT id FROM credentials WHERE is_deleted = 1").fetchall()
            for r in rows:
                self.connection.execute("DELETE FROM password_history WHERE credential_id = ?", (r["id"],))
            cursor = self.connection.execute("DELETE FROM credentials WHERE is_deleted = 1")
            return cursor.rowcount

    def get_credential(self, cred_id: str) -> Optional[Dict[str, Any]]:
        cursor = self.connection.execute("SELECT * FROM credentials WHERE id = ?", (cred_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

    def list_credentials(
        self,
        include_deleted: bool = False,
        search_query: str = "",
        sort_by: str = "title"
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM credentials WHERE "
        params = []
        if include_deleted:
            query += "is_deleted = 1"
        else:
            query += "is_deleted = 0"

        if search_query:
            query += " AND (title LIKE ? OR username LIKE ? OR url LIKE ? OR notes LIKE ?)"
            term = f"%{search_query.strip()}%"
            params.extend([term, term, term, term])

        valid_sorts = {
            "title": "title COLLATE NOCASE ASC",
            "title_desc": "title COLLATE NOCASE DESC",
            "updated_at": "updated_at DESC",
            "created_at": "created_at DESC"
        }
        order = valid_sorts.get(sort_by, "title COLLATE NOCASE ASC")
        query += f" ORDER BY {order}"

        cursor = self.connection.execute(query, params)
        return [dict(r) for r in cursor.fetchall()]

    def get_password_history(self, cred_id: str) -> List[Dict[str, Any]]:
        cursor = self.connection.execute(
            "SELECT * FROM password_history WHERE credential_id = ? ORDER BY changed_at DESC, rowid DESC",
            (cred_id,)
        )
        return [dict(r) for r in cursor.fetchall()]

    def clear_password_history(self, cred_id: Optional[str] = None) -> int:
        with self.connection:
            if cred_id:
                cur = self.connection.execute("DELETE FROM password_history WHERE credential_id = ?", (cred_id,))
            else:
                cur = self.connection.execute("DELETE FROM password_history")
            return cur.rowcount

    def get_setting(self, key: str, default: str = "") -> str:
        cursor = self.connection.execute("SELECT value FROM vault_settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT OR REPLACE INTO vault_settings (key, value) VALUES (?, ?)",
                (key, str(value))
            )
