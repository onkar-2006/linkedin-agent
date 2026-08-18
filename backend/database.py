import sqlite3
import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

DATABASE_PATH = os.getenv("DATABASE_PATH", "database.db")

class DatabaseManager:
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        # Ensure database directory exists
        db_dir = os.path.dirname(os.path.abspath(self.db_path))
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Table for stored posts (drafts, scheduled, published)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS linkedin_posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    image_url TEXT,
                    status TEXT DEFAULT 'draft', -- 'draft', 'scheduled', 'published', 'failed'
                    scheduled_time TEXT,        -- ISO timestamp
                    linkedin_urn TEXT,          -- Real URN from LinkedIn post
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    user_urn TEXT
                )
            """)

            # 2. Table for chat messages (conversations history)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_conversations (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    user_urn TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,         -- 'user', 'assistant'
                    content TEXT NOT NULL,
                    thinking TEXT,              -- agent thinking process metadata
                    image_url TEXT,             -- option generated image if any
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (conversation_id) REFERENCES chat_conversations(id) ON DELETE CASCADE
                )
            """)

            # 3. Table for LinkedIn Auth credentials
            try:
                cursor.execute("PRAGMA table_info(linkedin_credentials)")
                cols = [row['name'] for row in cursor.fetchall()]
                if 'id' in cols or not cols:
                    cursor.execute("DROP TABLE IF EXISTS linkedin_credentials")
            except Exception:
                pass

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS linkedin_credentials (
                    member_urn TEXT PRIMARY KEY,
                    access_token TEXT NOT NULL,
                    expires_at INTEGER NOT NULL, -- Unix epoch
                    first_name TEXT,
                    last_name TEXT,
                    profile_picture TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Migrations for existing SQLite files
            try:
                cursor.execute("PRAGMA table_info(linkedin_posts)")
                cols = [row['name'] for row in cursor.fetchall()]
                if 'user_urn' not in cols:
                    cursor.execute("ALTER TABLE linkedin_posts ADD COLUMN user_urn TEXT")
            except Exception:
                pass

            try:
                cursor.execute("PRAGMA table_info(chat_conversations)")
                cols = [row['name'] for row in cursor.fetchall()]
                if 'user_urn' not in cols:
                    cursor.execute("ALTER TABLE chat_conversations ADD COLUMN user_urn TEXT")
            except Exception:
                pass
            
            conn.commit()

    # --- LinkedIn Posts Operations ---
    def create_post(self, content: str, image_url: Optional[str] = None, status: str = 'draft', scheduled_time: Optional[str] = None, linkedin_urn: Optional[str] = None, user_urn: Optional[str] = None) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO linkedin_posts (content, image_url, status, scheduled_time, linkedin_urn, user_urn, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (content, image_url, status, scheduled_time, linkedin_urn, user_urn, datetime.utcnow().isoformat())
            )
            conn.commit()
            return cursor.lastrowid

    def get_posts(self, user_urn: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if user_urn:
                cursor.execute("SELECT * FROM linkedin_posts WHERE user_urn = ? ORDER BY created_at DESC", (user_urn,))
            else:
                cursor.execute("SELECT * FROM linkedin_posts ORDER BY created_at DESC")
            return [dict(row) for row in cursor.fetchall()]

    def get_post(self, post_id: int) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM linkedin_posts WHERE id = ?", (post_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_post(self, post_id: int, **kwargs) -> bool:
        if not kwargs:
            return False
        kwargs['updated_at'] = datetime.utcnow().isoformat()
        fields = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values()) + [post_id]
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE linkedin_posts SET {fields} WHERE id = ?", values)
            conn.commit()
            return cursor.rowcount > 0

    def delete_post(self, post_id: int) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM linkedin_posts WHERE id = ?", (post_id,))
            conn.commit()
            return cursor.rowcount > 0

    # --- LinkedIn Credentials Operations ---
    def save_credentials(self, access_token: str, expires_at: int, member_urn: str, first_name: Optional[str] = None, last_name: Optional[str] = None, profile_picture: Optional[str] = None):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO linkedin_credentials (member_urn, access_token, expires_at, first_name, last_name, profile_picture, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (member_urn, access_token, expires_at, first_name, last_name, profile_picture, datetime.utcnow().isoformat())
            )
            conn.commit()

    def get_credentials(self, user_urn: Optional[str] = None) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if user_urn:
                cursor.execute("SELECT * FROM linkedin_credentials WHERE member_urn = ?", (user_urn,))
            else:
                cursor.execute("SELECT * FROM linkedin_credentials ORDER BY updated_at DESC LIMIT 1")
            row = cursor.fetchone()
            return dict(row) if row else None

    def clear_credentials(self, user_urn: Optional[str] = None):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if user_urn:
                cursor.execute("DELETE FROM linkedin_credentials WHERE member_urn = ?", (user_urn,))
            else:
                cursor.execute("DELETE FROM linkedin_credentials")
            conn.commit()

    # --- Conversations Operations ---
    def get_conversations(self, user_urn: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if user_urn:
                cursor.execute("SELECT * FROM chat_conversations WHERE user_urn = ? ORDER BY created_at DESC", (user_urn,))
            else:
                cursor.execute("SELECT * FROM chat_conversations ORDER BY created_at DESC")
            return [dict(row) for row in cursor.fetchall()]

    def create_conversation(self, conversation_id: str, title: str, user_urn: Optional[str] = None) -> str:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO chat_conversations (id, title, user_urn) VALUES (?, ?, ?)",
                (conversation_id, title, user_urn)
            )
            conn.commit()
            return conversation_id

    def get_messages(self, conversation_id: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM chat_messages WHERE conversation_id = ? ORDER BY created_at ASC",
                (conversation_id,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def add_message(self, conversation_id: str, role: str, content: str, thinking: Optional[str] = None, image_url: Optional[str] = None, user_urn: Optional[str] = None):
        # Proactively ensure the conversation exists
        self.create_conversation(conversation_id, content[:40] + "...", user_urn)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO chat_messages (conversation_id, role, content, thinking, image_url) VALUES (?, ?, ?, ?, ?)",
                (conversation_id, role, content, thinking, image_url)
            )
            conn.commit()
            
    def delete_conversation(self, conversation_id: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM chat_messages WHERE conversation_id = ?", (conversation_id,))
            cursor.execute("DELETE FROM chat_conversations WHERE id = ?", (conversation_id,))
            conn.commit()
            return cursor.rowcount > 0
