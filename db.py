"""geo-monitor 数据库层 — SQLite CRUD"""

import sqlite3
import os
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent / "data" / "geo_monitor.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_db() -> sqlite3.Connection:
    """获取数据库连接（WAL 模式，外键）"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """初始化数据库（幂等）"""
    conn = get_db()
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    conn.executescript(schema)
    conn.commit()
    conn.close()


# ── 平台 ──

def sync_platforms(platforms: list[dict]):
    """同步平台配置到数据库（插入新平台，更新已有）"""
    conn = get_db()
    for p in platforms:
        conn.execute("""
            INSERT INTO platforms (name, display_name, base_url, profile_dir, enabled)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                display_name=excluded.display_name,
                base_url=excluded.base_url,
                profile_dir=excluded.profile_dir,
                enabled=excluded.enabled
        """, (p["id"], p["name"], p["base_url"], p["profile_dir"], p.get("enabled", 1)))
    conn.commit()
    conn.close()


def get_enabled_platforms() -> list[dict]:
    """获取所有启用的平台"""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM platforms WHERE enabled=1 ORDER BY id"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── 问题 ──

def sync_questions(questions: list[dict]):
    """同步问题到数据库（去重）"""
    conn = get_db()
    for q in questions:
        conn.execute("""
            INSERT OR IGNORE INTO questions (group_name, text, created_by)
            VALUES (?, ?, ?)
        """, (q.get("group", "default"), q["text"], q.get("created_by", "manual")))
    conn.commit()
    conn.close()


def add_question(text: str, group: str = "default", created_by: str = "manual") -> int:
    """Agent 写入接口：添加单个问题，返回 id"""
    conn = get_db()
    try:
        cursor = conn.execute("""
            INSERT INTO questions (group_name, text, created_by)
            VALUES (?, ?, ?)
        """, (group, text, created_by))
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        # 已存在，返回已有 id
        row = conn.execute(
            "SELECT id FROM questions WHERE text=?", (text,)
        ).fetchone()
        return row["id"] if row else -1
    finally:
        conn.close()


def get_enabled_questions() -> list[dict]:
    """获取所有启用的问题"""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM questions WHERE enabled=1 ORDER BY group_name, id"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── 查询运行 ──

def create_run(question_id: int, platform_id: int) -> int:
    """创建一条 pending 查询记录，返回 run_id"""
    conn = get_db()
    cursor = conn.execute("""
        INSERT INTO query_runs (question_id, platform_id, status)
        VALUES (?, ?, 'pending')
    """, (question_id, platform_id))
    conn.commit()
    run_id = cursor.lastrowid
    conn.close()
    return run_id


def mark_run_running(run_id: int):
    conn = get_db()
    conn.execute("UPDATE query_runs SET status='running' WHERE id=?", (run_id,))
    conn.commit()
    conn.close()


def mark_run_done(run_id: int, answer_text: str, model_name: str, duration_ms: int):
    conn = get_db()
    conn.execute("""
        UPDATE query_runs SET status='done', answer_text=?, model_name=?,
        duration_ms=?, query_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (answer_text, model_name, duration_ms, run_id))
    conn.commit()
    conn.close()


def mark_run_failed(run_id: int, error_message: str):
    conn = get_db()
    conn.execute("""
        UPDATE query_runs SET status='failed', error_message=?, query_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (error_message, run_id))
    conn.commit()
    conn.close()


def save_citations(run_id: int, citations: list[dict]):
    """批量保存引用"""
    conn = get_db()
    for i, c in enumerate(citations):
        conn.execute("""
            INSERT INTO citations (run_id, url, title, domain, position, snippet)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (run_id, c.get("url"), c.get("title"), c.get("domain"), i, c.get("snippet")))
    conn.commit()
    conn.close()


# ── 查询 ──

def get_latest_runs(limit: int = 20) -> list[dict]:
    """获取最近的查询记录（含平台名、问题文本）"""
    conn = get_db()
    rows = conn.execute("""
        SELECT r.*, p.display_name as platform_name, q.text as question_text, q.group_name
        FROM query_runs r
        JOIN platforms p ON r.platform_id = p.id
        JOIN questions q ON r.question_id = q.id
        ORDER BY r.query_at DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_run_detail(run_id: int) -> dict | None:
    """获取单条查询详情（含引用列表）"""
    conn = get_db()
    row = conn.execute("""
        SELECT r.*, p.display_name as platform_name, q.text as question_text, q.group_name
        FROM query_runs r
        JOIN platforms p ON r.platform_id = p.id
        JOIN questions q ON r.question_id = q.id
        WHERE r.id=?
    """, (run_id,)).fetchone()
    if not row:
        conn.close()
        return None
    result = dict(row)
    citations = conn.execute(
        "SELECT * FROM citations WHERE run_id=? ORDER BY position", (run_id,)
    ).fetchall()
    result["citations"] = [dict(c) for c in citations]
    conn.close()
    return result


def get_question_history(question_id: int, limit: int = 10) -> list[dict]:
    """查看某个问题的历史回答"""
    conn = get_db()
    rows = conn.execute("""
        SELECT r.*, p.display_name as platform_name
        FROM query_runs r
        JOIN platforms p ON r.platform_id = p.id
        WHERE r.question_id=? AND r.status='done'
        ORDER BY r.query_at DESC
        LIMIT ?
    """, (question_id, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
