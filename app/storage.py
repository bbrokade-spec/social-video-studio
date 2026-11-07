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
                    audio_json TEXT NOT NULL DEFAULT '{}',
                    subtitles_json TEXT NOT NULL DEFAULT '{}',
                    transition_json TEXT NOT NULL DEFAULT '{"type":"cut","duration_seconds":0.5}',
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
            if "audio_json" not in columns:
                db.execute("ALTER TABLE export_jobs ADD COLUMN audio_json TEXT NOT NULL DEFAULT '{}'")
            if "subtitles_json" not in columns:
                db.execute("ALTER TABLE export_jobs ADD COLUMN subtitles_json TEXT NOT NULL DEFAULT '{}'")
            if "transition_json" not in columns:
                db.execute("ALTER TABLE export_jobs ADD COLUMN transition_json TEXT NOT NULL DEFAULT '{\"type\":\"cut\",\"duration_seconds\":0.5}'")
            db.execute(
                "CREATE INDEX IF NOT EXISTS idx_export_jobs_status ON export_jobs(status, created_at)"
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS script_plans (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    full_script TEXT NOT NULL,
                    output_profile TEXT NOT NULL CHECK(output_profile IN ('vertical', 'landscape')),
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
                )"""
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS script_scenes (
                    id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL REFERENCES script_plans(id) ON DELETE CASCADE,
                    position INTEGER NOT NULL CHECK(position >= 0),
                    narration_text TEXT NOT NULL,
                    visual_prompt TEXT NOT NULL,
                    negative_prompt TEXT NOT NULL DEFAULT '',
                    duration_seconds REAL NOT NULL CHECK(duration_seconds BETWEEN 0.5 AND 30),
                    generation_status TEXT NOT NULL DEFAULT 'not_started',
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                    UNIQUE(plan_id, position)
                )"""
            )
            db.execute("CREATE INDEX IF NOT EXISTS idx_script_plans_project ON script_plans(project_id, updated_at)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_script_scenes_plan ON script_scenes(plan_id, position)")


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
                (id, project_id, asset_ids_json, clip_trims_json, audio_json, subtitles_json, transition_json, profile, fps, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'queued')""",
                (job["id"], job["project_id"], json.dumps(job["asset_ids"]), json.dumps(job.get("clip_trims") or []), json.dumps(job.get("audio") or {}), json.dumps(job.get("subtitles") or {}), json.dumps(job.get("transition") or {"type": "cut", "duration_seconds": 0.5}), job["profile"], job["fps"]),
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
        result["audio"] = json.loads(result.pop("audio_json", "{}"))
        result["subtitles"] = json.loads(result.pop("subtitles_json", "{}"))
        result["transition"] = json.loads(result.pop("transition_json", '{"type":"cut","duration_seconds":0.5}'))
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


    def create_script_plan(self, plan: dict[str, Any]) -> dict[str, Any]:
        import json
        with self._connect() as db:
            if not db.execute("SELECT 1 FROM projects WHERE id = ?", (plan["project_id"],)).fetchone():
                raise StorageError("Project does not exist.")
            db.execute(
                "INSERT INTO script_plans (id, project_id, title, full_script, output_profile) VALUES (?, ?, ?, ?, ?)",
                (plan["id"], plan["project_id"], plan["title"], plan["full_script"], plan["output_profile"]),
            )
            for scene in plan["scenes"]:
                db.execute(
                    """INSERT INTO script_scenes
                    (id, plan_id, position, narration_text, visual_prompt, negative_prompt, duration_seconds)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (scene["id"], plan["id"], scene["position"], scene["narration_text"],
                     scene["visual_prompt"], scene.get("negative_prompt", ""), scene["duration_seconds"]),
                )
            db.execute("UPDATE projects SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id = ?", (plan["project_id"],))
        return self.get_script_plan(plan["id"])

    def list_script_plans(self, project_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM script_plans WHERE project_id = ? ORDER BY updated_at DESC", (project_id,)).fetchall()
        return [self.get_script_plan(row["id"]) for row in rows]

    def get_script_plan(self, plan_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM script_plans WHERE id = ?", (plan_id,)).fetchone()
            if row is None:
                return None
            plan = dict(row)
            scenes = db.execute("SELECT * FROM script_scenes WHERE plan_id = ? ORDER BY position", (plan_id,)).fetchall()
        plan["scenes"] = [dict(scene) for scene in scenes]
        return plan

    def update_script_plan(self, plan_id: str, plan: dict[str, Any]) -> dict[str, Any] | None:
        with self._connect() as db:
            existing = db.execute("SELECT project_id FROM script_plans WHERE id = ?", (plan_id,)).fetchone()
            if existing is None:
                return None
            db.execute(
                """UPDATE script_plans SET title = ?, full_script = ?, output_profile = ?,
                updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id = ?""",
                (plan["title"], plan["full_script"], plan["output_profile"], plan_id),
            )
            db.execute("DELETE FROM script_scenes WHERE plan_id = ?", (plan_id,))
            for scene in plan["scenes"]:
                db.execute(
                    """INSERT INTO script_scenes
                    (id, plan_id, position, narration_text, visual_prompt, negative_prompt, duration_seconds)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (scene["id"], plan_id, scene["position"], scene["narration_text"],
                     scene["visual_prompt"], scene.get("negative_prompt", ""), scene["duration_seconds"]),
                )
            db.execute("UPDATE projects SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id = ?", (existing["project_id"],))
        return self.get_script_plan(plan_id)

    def delete_script_plan(self, plan_id: str) -> bool:
        with self._connect() as db:
            cursor = db.execute("DELETE FROM script_plans WHERE id = ?", (plan_id,))
        return cursor.rowcount > 0
