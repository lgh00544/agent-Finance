"""Import the legacy single-user SQLite history into an isolated multi-user DB.

The source is only read through SQLite's online backup API. The target is
replaced only after schema upgrade, ownership backfill, and row-count checks
succeed. Both the source snapshot and the pre-import target are retained.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys


PRIVATE_TABLES = (
    "position_plan", "holding", "trade_record", "alert_log", "review_result",
    "agent_preference", "sys_trade_profile", "private_knowledge", "sell_decision",
    "account_baseline", "account_pnl_snapshot", "agent_suggestion", "rule_change",
    "agent_chat_message", "ai_reasoning_trace", "ai_reasoning_trace_history",
    "paper_account", "paper_position", "paper_execution",
    "paper_review", "paper_quote_snapshot", "paper_context", "paper_web_evidence",
    "paper_alert",
)


def _backup(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination.unlink()
    src = sqlite3.connect(f"{source.resolve().as_uri()}?mode=ro", uri=True)
    dst = sqlite3.connect(destination)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def _table_counts(path: Path) -> dict[str, int]:
    db = sqlite3.connect(path)
    try:
        tables = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'experience_fts%'"
        ).fetchall()
        return {name: db.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
                for (name,) in tables}
    finally:
        db.close()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bootstrap_schema(worktree: Path, staged: Path, username: str, password: str) -> None:
    env = os.environ.copy()
    env.update({
        "APP_ENV": "dev",
        "DB_BACKEND": "sqlite",
        "SQLITE_PATH": str(staged),
        "MULTI_USER_ENABLED": "false",
        "AUTH_DEFAULT_USERNAME": username,
        "AUTH_DEFAULT_PASSWORD": password,
        "PYTEST_CURRENT_TEST": "",
    })
    subprocess.run(
        [sys.executable, "-c", "from app.db.session import init_db; init_db()"],
        cwd=worktree / "backend", env=env, check=True,
    )


def _verify(staged: Path, source_counts: dict[str, int], username: str) -> dict[str, int]:
    target_counts = _table_counts(staged)
    mismatches = {
        table: {"source": count, "target": target_counts.get(table)}
        for table, count in source_counts.items()
        if target_counts.get(table) != count
    }
    if mismatches:
        raise RuntimeError(f"row-count verification failed: {mismatches}")
    db = sqlite3.connect(staged)
    try:
        user = db.execute(
            "SELECT id, username, role FROM app_user WHERE id = 1"
        ).fetchone()
        if user != (1, username, "admin"):
            raise RuntimeError(f"legacy owner bootstrap failed: {user!r}")
        owned: dict[str, int] = {}
        for table in PRIVATE_TABLES:
            columns = {row[1] for row in db.execute(f'PRAGMA table_info("{table}")')}
            if "user_id" not in columns:
                raise RuntimeError(f"missing user_id on private table: {table}")
            count = db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            wrong = db.execute(
                f'SELECT COUNT(*) FROM "{table}" WHERE user_id IS NULL OR user_id != 1'
            ).fetchone()[0]
            if wrong:
                raise RuntimeError(f"ownership backfill failed: {table} has {wrong} invalid rows")
            owned[table] = count
        return owned
    finally:
        db.close()


def _record_import(staged: Path, manifest: dict) -> None:
    db = sqlite3.connect(staged)
    try:
        db.execute(
            "CREATE TABLE IF NOT EXISTS legacy_import_log ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, imported_at TEXT NOT NULL, "
            "owner_username TEXT NOT NULL, source_snapshot_sha256 TEXT NOT NULL, "
            "manifest_json TEXT NOT NULL)"
        )
        db.execute(
            "INSERT INTO legacy_import_log (imported_at, owner_username, "
            "source_snapshot_sha256, manifest_json) VALUES (?, ?, ?, ?)",
            (manifest["imported_at"], manifest["owner_username"],
             manifest["source_snapshot_sha256"], json.dumps(manifest, ensure_ascii=False)),
        )
        db.commit()
        db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--username", default="lugenghua")
    parser.add_argument("--initial-password", required=True)
    parser.add_argument("--worktree", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    source, target, worktree = args.source.resolve(), args.target.resolve(), args.worktree.resolve()
    if not source.is_file():
        raise SystemExit(f"source database not found: {source}")
    if source == target:
        raise SystemExit("source and target must be different databases")

    source_fingerprint = {
        "size_bytes": source.stat().st_size,
        "sha256": _sha256(source),
    }

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = target.parent / "backups"
    source_snapshot = backup_dir / f"legacy-source-{stamp}.db"
    staged = target.with_name(f"{target.stem}.importing-{stamp}{target.suffix}")
    target_backup = backup_dir / f"{target.stem}.before-import-{stamp}{target.suffix}"
    manifest_path = backup_dir / f"legacy-import-{stamp}.json"

    _backup(source, source_snapshot)
    source_after_backup = {
        "size_bytes": source.stat().st_size,
        "sha256": _sha256(source),
    }
    if source_after_backup != source_fingerprint:
        raise RuntimeError("source database changed during the read-only snapshot; import aborted")
    source_counts = _table_counts(source_snapshot)
    shutil.copy2(source_snapshot, staged)
    try:
        _bootstrap_schema(worktree, staged, args.username, args.initial_password)
        owned = _verify(staged, source_counts, args.username)
        manifest = {
            "imported_at": datetime.now(timezone.utc).isoformat(),
            "source": str(source),
            "source_fingerprint_before_snapshot": source_fingerprint,
            "source_fingerprint_after_snapshot": source_after_backup,
            "source_snapshot": str(source_snapshot),
            "source_snapshot_sha256": _sha256(source_snapshot),
            "target": str(target),
            "target_backup": str(target_backup) if target.exists() else None,
            "owner_username": args.username,
            "owner_user_id": 1,
            "source_table_counts": source_counts,
            "private_rows_assigned_to_owner": owned,
        }
        _record_import(staged, manifest)
        if target.exists():
            _backup(target, target_backup)
        for suffix in ("-wal", "-shm"):
            stale = Path(f"{target}{suffix}")
            if stale.exists():
                stale.unlink()
        os.replace(staged, target)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"status": "imported", "manifest": str(manifest_path), **manifest}, ensure_ascii=False))
        return 0
    finally:
        for suffix in ("", "-wal", "-shm"):
            leftover = Path(f"{staged}{suffix}")
            if leftover.exists():
                leftover.unlink()


if __name__ == "__main__":
    raise SystemExit(main())
