"""
PAMS - Database layer (DAO)
Author: Yunus Sert (24015097) and Tahmid Ahmed. (240180955)

Handles all SQLite operations. Uses parameterised queries (SQL-injection safe)
and a single connection per app session.

"""
import sqlite3
import os
from pathlib import Path


class DatabaseManager:
    """Singleton-style DB manager. One connection per app run."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, db_path: str = "pams.db"):
        if getattr(self, "_initialised", False):
            return
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._initialised = True

    
    # Schema / seed
    def initialise_schema(self, schema_path: str):
        """Run the schema.sql file."""
        with open(schema_path, "r", encoding="utf-8") as f:
            self.conn.executescript(f.read())
        self.conn.commit()

    def seed_if_empty(self, seed_func):
        """Call seed_func(db) only if there are no users yet."""
        cur = self.conn.execute("SELECT COUNT(*) AS c FROM users")
        if cur.fetchone()["c"] == 0:
            seed_func(self)


    # Generic helpers - parameterised to prevent SQL injection
    def execute(self, sql: str, params: tuple = ()):
        cur = self.conn.execute(sql, params)
        self.conn.commit()
        return cur

    def query_all(self, sql: str, params: tuple = ()):
        return self.conn.execute(sql, params).fetchall()

    def query_one(self, sql: str, params: tuple = ()):
        return self.conn.execute(sql, params).fetchone()

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
            type(self)._instance = None


def get_db(db_path: str = None) -> DatabaseManager:
    if db_path is None:
        db_path = os.environ.get("PAMS_DB", "pams.db")
    return DatabaseManager(db_path)
