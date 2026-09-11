"""经验/审核归属迁移的最小 SQLite 回归覆盖。"""

from sqlalchemy import create_engine, text

from app.db.session import _ensure_experience_audit_user_scope


def _legacy_db():
    eng = create_engine("sqlite://")
    with eng.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE pending_experience ("
            "id INTEGER PRIMARY KEY, task_id VARCHAR(64), stage VARCHAR(8), "
            "created_at DATETIME, summary TEXT, artifacts_ref TEXT, "
            "status VARCHAR(12), error TEXT)"
        )
        conn.exec_driver_sql(
            "CREATE TABLE experience ("
            "id INTEGER PRIMARY KEY, title VARCHAR(128), body TEXT, stage VARCHAR(8), "
            "tags TEXT, impact VARCHAR(8), confidence FLOAT, auto_merged INTEGER, "
            "source_pending_id INTEGER, status VARCHAR(16), created_at DATETIME, "
            "last_reviewed_at DATETIME, hit_count INTEGER, last_used_at DATETIME, "
            "expires_at DATETIME, curator_note TEXT)"
        )
        conn.exec_driver_sql(
            "CREATE TABLE review_log ("
            "id INTEGER PRIMARY KEY, experience_id INTEGER, action VARCHAR(32), "
            "reviewer VARCHAR(16), at DATETIME, note TEXT)"
        )
        conn.exec_driver_sql(
            "CREATE TABLE worker_run ("
            "id INTEGER PRIMARY KEY, started_at DATETIME, ended_at DATETIME, "
            "processed_count INTEGER, status VARCHAR(12), error TEXT)"
        )
        conn.exec_driver_sql(
            "CREATE TABLE audit_log ("
            "id INTEGER PRIMARY KEY, target_type VARCHAR(24), target_id INTEGER, "
            "round INTEGER, verdict VARCHAR(8), confidence INTEGER, support_view TEXT, "
            "dissent_view TEXT, boundary_cases TEXT, evidence_refs TEXT, "
            "audit_model VARCHAR(32), reasoning TEXT, duration_ms INTEGER, created_at DATETIME)"
        )
        for table in ("agent_suggestion", "rule_change", "review_result"):
            conn.exec_driver_sql(
                f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, user_id INTEGER)"
            )
        conn.exec_driver_sql(
            "INSERT INTO pending_experience (id, stage, status) VALUES (10, '选股', 'pending')"
        )
        conn.exec_driver_sql(
            "INSERT INTO experience (id, title, body, stage, status, source_pending_id) "
            "VALUES (20, '旧经验', '正文', '选股', 'active', 10)"
        )
        conn.exec_driver_sql(
            "INSERT INTO review_log (id, experience_id, action, reviewer) "
            "VALUES (30, 20, 'approve', 'sir')"
        )
        conn.exec_driver_sql(
            "INSERT INTO review_log (id, experience_id, action, reviewer) "
            "VALUES (31, NULL, 'strictness_freeze', 'auto')"
        )
        conn.exec_driver_sql(
            "INSERT INTO worker_run (id, status) VALUES (40, 'success')"
        )
        conn.exec_driver_sql(
            "INSERT INTO agent_suggestion (id, user_id) VALUES (50, 1)"
        )
        conn.exec_driver_sql(
            "INSERT INTO audit_log (id, target_type, target_id, verdict) "
            "VALUES (60, 'agent_suggestion', 50, 'pass')"
        )
        conn.exec_driver_sql(
            "INSERT INTO audit_log (id, target_type, target_id, verdict) "
            "VALUES (61, 'system_event', 999, 'pass')"
        )
    return eng


def test_experience_audit_scope_backfills_and_is_idempotent():
    eng = _legacy_db()
    first = _ensure_experience_audit_user_scope(eng, default_user_id=1)
    second = _ensure_experience_audit_user_scope(eng, default_user_id=1)

    assert all(result["added"] == ["user_id"] for result in first["columns"].values())
    assert all(result["added"] == [] for result in second["columns"].values())
    with eng.connect() as conn:
        assert conn.execute(text(
            "SELECT user_id FROM pending_experience WHERE id=10")).scalar_one() == 1
        assert conn.execute(text(
            "SELECT user_id FROM experience WHERE id=20")).scalar_one() == 1
        assert conn.execute(text(
            "SELECT user_id FROM worker_run WHERE id=40")).scalar_one() == 1
        assert conn.execute(text(
            "SELECT user_id FROM review_log WHERE id=30")).scalar_one() == 1
        assert conn.execute(text(
            "SELECT user_id FROM review_log WHERE id=31")).scalar_one() is None
        assert conn.execute(text(
            "SELECT user_id FROM audit_log WHERE id=60")).scalar_one() == 1
        assert conn.execute(text(
            "SELECT user_id FROM audit_log WHERE id=61")).scalar_one() is None

        indexes = {
            row[1] for row in conn.exec_driver_sql("PRAGMA index_list(experience)")
        }
        assert "ix_experience_user_status_stage" in indexes
        assert "ix_experience_user_stage_id" in indexes

