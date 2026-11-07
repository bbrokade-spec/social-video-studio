"""SQLite-backed local projects and asset metadata storage."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


class StorageError(RuntimeError):
    pass


class LocalStore:
    """Single-user local store. Database and media remain under one data directory."""

    def __init__(self, data_dir: str | Path):
        self.root = Path(data_dir).expanduser().resolve()
        self.asset_dir = self.root / "assets"
        self.root.mkdir(parents=True, exist_ok=True)
        self.asset_dir.mkdir(parents=True, exist_ok=True)
        self.database = self.root / "studio.sqlite3"
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
                )"""
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS assets (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    original_name TEXT NOT NULL,
                    stored_name TEXT NOT NULL UNIQUE,
                    media_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL CHECK(size_bytes > 0),
                    sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
                )"""
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS idx_assets_project ON assets(project_id, created_at)"
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS export_jobs (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    asset_ids_json TEXT NOT NULL,
                    clip_trims_json TEXT NOT NULL DEFAULT '[]',
                    profile TEXT NOT NULL CHECK(profile IN ('vertical', 'landscape')),
                    fps INTEGER NOT NULL CHECK(fps BETWEEN 1 AND 60),
                    status TEXT NOT NULL CHECK(status IN ('queued', 'running', 'completed', 'failed')),
                    progress INTEGER NOT NULL DEFAULT 0 CHECK(progress BETWEEN 0 AND 100),
                    result_asset_id TEXT REFERENCES assets(id),
                    error_message TEXT,
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
                )"""
            )
            columns = {row[1] for row in db.execute("PRAGMA table_info(export_jobs)")}
            if "clip_trims_json" not in columns:
                db.execute("ALTER TABLE export_jobs ADD COLUMN clip_trims_json TEXT NOT NULL DEFAULT '[]'")
            db.execute(
                "CREATE INDEX IF NOT EXISTS idx_export_jobs_status ON export_jobs(status, created_at)"
            )


    def create_project(self, project_id: str, title: str) -> dict[str, Any]:
        with self._connect() as db:
            db.execute(
                "INSERT INTO projects (id, title) VALUES (?, ?)", (project_id, title)
            )
            row = db.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return dict(row)

    def list_projects(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM projects ORDER BY updated_at DESC, created_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return dict(row) if row else None

    def register_asset(self, asset: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as db:
            exists = db.execute(
                "SELECT 1 FROM projects WHERE id = ?", (asset["project_id"],)
            ).fetchone()
            if not exists:
                raise StorageError("Project does not exist.")
            db.execute(
                """INSERT INTO assets
                (id, project_id, original_name, stored_name, media_type, size_bytes, sha256)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    asset["id"], asset["project_id"], asset["original_name"],
                    asset["stored_name"], asset["media_type"], asset["size_bytes"],
                    asset["sha256"],
                ),
            )
            row = db.execute("SELECT * FROM assets WHERE id = ?", (asset["id"],)).fetchone()
        return dict(row)

    def list_assets(self, project_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM assets WHERE project_id = ? ORDER BY created_at DESC",
                (project_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_asset(self, asset_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM assets WHERE id = ?", (asset_id,)).fetchone()
        return dict(row) if row else None

    def create_export_job(self, job: dict[str, Any]) -> dict[str, Any]:
        import json
        with self._connect() as db:
            db.execute(
                """INSERT INTO export_jobs
                (id, project_id, asset_ids_json, clip_trims_json, profile, fps, status)
                VALUES (?, ?, ?, ?, ?, ?, 'queued')""",
                (job["id"], job["project_id"], json.dumps(job["asset_ids"]), json.dumps(job.get("clip_trims") or []), job["profile"], job["fps"]),
            )
            row = db.execute("SELECT * FROM export_jobs WHERE id = ?", (job["id"],)).fetchone()
        return self._job_dict(row)

    @staticmethod
    def _job_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
        import json
        if row is None:
            return None
        result = dict(row)
        result["asset_ids"] = json.loads(result.pop("asset_ids_json"))
        result["clip_trims"] = json.loads(result.pop("clip_trims_json", "[]"))
        return result

    def get_export_job(self, job_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM export_jobs WHERE id = ?", (job_id,)).fetchone()
        return self._job_dict(row)

    def recover_interrupted_jobs(self) -> int:
        with self._connect() as db:
            cursor = db.execute(
                """UPDATE export_jobs SET status = 'queued', progress = 0,
                error_message = NULL,
                updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now')
                WHERE status = 'running'"""
            )
            return cursor.rowcount

    def claim_next_export_job(self) -> dict[str, Any] | None:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM export_jobs WHERE status = 'queued' ORDER BY created_at LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            db.execute(
                """UPDATE export_jobs SET status = 'running', progress = 5,
                updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id = ?""",
                (row["id"],),
            )
            claimed = db.execute("SELECT * FROM export_jobs WHERE id = ?", (row["id"],)).fetchone()
        return self._job_dict(claimed)

    def update_export_job(self, job_id: str, *, status: str, progress: int,
                          result_asset_id: str | None = None,
                          error_message: str | None = None) -> None:
        with self._connect() as db:
            db.execute(
                """UPDATE export_jobs SET status = ?, progress = ?,
                result_asset_id = ?, error_message = ?,
                updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now')
                WHERE id = ?""",
                (status, progress, result_asset_id, error_message, job_id),
            )
