from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from models.schemas import RoleProfile, User, UserCreate


class MySQLClient:
    """Storage client that supports SQLite and MySQL behind one interface."""

    def __init__(self, settings, logger):
        self.settings = settings
        self.logger = logger
        self.backend = settings.db_backend.strip().lower()
        self.db_path: Path = settings.sqlite_path

    def _connect(self):
        if self.backend == "mysql":
            try:
                import pymysql
                from pymysql.cursors import DictCursor
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError("pymysql is required when DB_BACKEND=mysql.") from exc

            if not self.settings.mysql_database:
                raise RuntimeError("MYSQL_DATABASE is empty. Configure the target database first.")

            return pymysql.connect(
                host=self.settings.mysql_host,
                port=self.settings.mysql_port,
                user=self.settings.mysql_user,
                password=self.settings.mysql_password,
                database=self.settings.mysql_database,
                charset=self.settings.mysql_charset,
                cursorclass=DictCursor,
                autocommit=False,
            )

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self) -> None:
        with self._connect() as conn:
            if self.backend == "mysql":
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS users (
                            user_id VARCHAR(128) PRIMARY KEY,
                            name VARCHAR(255) NOT NULL,
                            profile TEXT NOT NULL,
                            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                        ) CHARACTER SET utf8mb4
                        """
                    )
                    cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS roles (
                            role_id VARCHAR(128) PRIMARY KEY,
                            name VARCHAR(255) NOT NULL,
                            domain VARCHAR(255) NOT NULL,
                            description TEXT NOT NULL,
                            personality TEXT NOT NULL,
                            tone VARCHAR(255) NOT NULL,
                            system_rules TEXT NOT NULL,
                            prompt_template TEXT NOT NULL,
                            metadata TEXT NOT NULL,
                            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                                ON UPDATE CURRENT_TIMESTAMP
                        ) CHARACTER SET utf8mb4
                        """
                    )
                conn.commit()
                self.logger.info(
                    "MySQL schema initialized at %s:%s/%s",
                    self.settings.mysql_host,
                    self.settings.mysql_port,
                    self.settings.mysql_database,
                )
                return

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    profile TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS roles (
                    role_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    description TEXT NOT NULL,
                    personality TEXT NOT NULL,
                    tone TEXT NOT NULL,
                    system_rules TEXT NOT NULL,
                    prompt_template TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()
        self.logger.info("SQLite schema initialized at %s", self.db_path)

    def create_user(self, payload: UserCreate) -> User:
        user = User(
            user_id=payload.user_id or f"user-{uuid.uuid4().hex[:8]}",
            name=payload.name,
            profile=payload.profile,
        )
        with self._connect() as conn:
            profile_json = json.dumps(user.profile, ensure_ascii=False)
            if self.backend == "mysql":
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO users (user_id, name, profile)
                        VALUES (%s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            name = VALUES(name),
                            profile = VALUES(profile)
                        """,
                        (user.user_id, user.name, profile_json),
                    )
            else:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO users (user_id, name, profile)
                    VALUES (?, ?, ?)
                    """,
                    (user.user_id, user.name, profile_json),
                )
            conn.commit()
        return user

    def get_user(self, user_id: str) -> User | None:
        with self._connect() as conn:
            if self.backend == "mysql":
                with conn.cursor() as cursor:
                    cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
                    row = cursor.fetchone()
            else:
                row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            return None
        return User(
            user_id=row["user_id"],
            name=row["name"],
            profile=self._load_json_field(row["profile"]),
        )

    def upsert_role(self, role: RoleProfile) -> None:
        with self._connect() as conn:
            params = (
                role.role_id,
                role.name,
                role.domain,
                role.description,
                role.personality,
                role.tone,
                json.dumps(role.system_rules, ensure_ascii=False),
                role.prompt_template,
                json.dumps(role.metadata, ensure_ascii=False),
            )
            if self.backend == "mysql":
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO roles (
                            role_id, name, domain, description, personality, tone,
                            system_rules, prompt_template, metadata
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            name = VALUES(name),
                            domain = VALUES(domain),
                            description = VALUES(description),
                            personality = VALUES(personality),
                            tone = VALUES(tone),
                            system_rules = VALUES(system_rules),
                            prompt_template = VALUES(prompt_template),
                            metadata = VALUES(metadata),
                            updated_at = CURRENT_TIMESTAMP
                        """,
                        params,
                    )
            else:
                conn.execute(
                    """
                    INSERT INTO roles (
                        role_id, name, domain, description, personality, tone,
                        system_rules, prompt_template, metadata
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(role_id) DO UPDATE SET
                        name = excluded.name,
                        domain = excluded.domain,
                        description = excluded.description,
                        personality = excluded.personality,
                        tone = excluded.tone,
                        system_rules = excluded.system_rules,
                        prompt_template = excluded.prompt_template,
                        metadata = excluded.metadata,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    params,
                )
            conn.commit()

    def get_role(self, role_id: str) -> RoleProfile | None:
        with self._connect() as conn:
            if self.backend == "mysql":
                with conn.cursor() as cursor:
                    cursor.execute("SELECT * FROM roles WHERE role_id = %s", (role_id,))
                    row = cursor.fetchone()
            else:
                row = conn.execute("SELECT * FROM roles WHERE role_id = ?", (role_id,)).fetchone()
        return self._row_to_role(row) if row else None

    def list_roles(self) -> list[RoleProfile]:
        with self._connect() as conn:
            if self.backend == "mysql":
                with conn.cursor() as cursor:
                    cursor.execute("SELECT * FROM roles ORDER BY role_id")
                    rows = cursor.fetchall()
            else:
                rows = conn.execute("SELECT * FROM roles ORDER BY role_id").fetchall()
        return [self._row_to_role(row) for row in rows]

    def role_exists(self, role_id: str) -> bool:
        return self.get_role(role_id) is not None

    @staticmethod
    def _row_to_role(row: Any) -> RoleProfile:
        return RoleProfile(
            role_id=row["role_id"],
            name=row["name"],
            domain=row["domain"],
            description=row["description"],
            personality=row["personality"],
            tone=row["tone"],
            system_rules=MySQLClient._load_json_field(row["system_rules"]),
            prompt_template=row["prompt_template"],
            metadata=MySQLClient._load_json_field(row["metadata"]),
        )

    @staticmethod
    def _load_json_field(value: Any) -> Any:
        if isinstance(value, (dict, list)):
            return value
        if value in (None, ""):
            return {}
        return json.loads(value)
