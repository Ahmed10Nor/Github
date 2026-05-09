# db/database.py
# LuminAgents — Database Layer (Architecture v5.4)
# WAL Mode + aiosqlite for full async support
import sqlite3
import aiosqlite
import os
from pathlib import Path

DB_PATH = Path(__file__).parent / "luminagents.db"


# SYNC
def get_connection(db_path: str = str(DB_PATH)) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


# ASYNC
async def get_async_connection(db_path: str = str(DB_PATH)) -> aiosqlite.Connection:
    conn = await aiosqlite.connect(db_path)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA synchronous=NORMAL")
    await conn.execute("PRAGMA foreign_keys=ON")
    return conn


# SCHEMA
def init_db(db_path: str = None):
    if db_path is None:
        db_path = str(DB_PATH)
    conn = get_connection(db_path)

    _TABLES = [
        """CREATE TABLE IF NOT EXISTS users (
            user_id              TEXT PRIMARY KEY,
            name                 TEXT NOT NULL,
            goal                 TEXT NOT NULL,
            category             TEXT NOT NULL,
            level                TEXT NOT NULL,
            hours_per_day        REAL NOT NULL DEFAULT 1.0,
            days_per_week        INTEGER NOT NULL DEFAULT 5,
            estimated_weeks      INTEGER NOT NULL DEFAULT 0,
            start_date           TEXT NOT NULL,
            language             TEXT DEFAULT 'ar',
            onboarding_complete  INTEGER DEFAULT 0,
            onboarding_step      TEXT DEFAULT 'awaiting_goal',
            partial_profile      TEXT,
            age                  INTEGER,
            weight               REAL,
            height               REAL,
            agent_name           TEXT DEFAULT 'The Sentinel',
            agent_vibe           TEXT DEFAULT 'motivational',
            created_at           TEXT DEFAULT (datetime('now'))
        )""",
        """CREATE TABLE IF NOT EXISTS milestones (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     TEXT NOT NULL,
            title       TEXT NOT NULL,
            week_start  INTEGER NOT NULL,
            week_end    INTEGER NOT NULL,
            lesson_ids  TEXT DEFAULT '[]',
            completed   INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )""",
        """CREATE TABLE IF NOT EXISTS daily_tasks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     TEXT NOT NULL,
            day         INTEGER NOT NULL,
            week        INTEGER NOT NULL,
            lesson_id   TEXT NOT NULL,
            description TEXT NOT NULL,
            hours       REAL NOT NULL,
            completed   INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )""",
        """CREATE TABLE IF NOT EXISTS snapshots (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         TEXT NOT NULL,
            milestone_index INTEGER NOT NULL,
            snapshot        TEXT NOT NULL,
            created_at      TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )""",
        """CREATE TABLE IF NOT EXISTS context_frames (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     TEXT NOT NULL,
            skill       TEXT NOT NULL,
            frame_json  TEXT NOT NULL,
            created_at  TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )""",
        """CREATE TABLE IF NOT EXISTS failure_log (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id        TEXT NOT NULL,
            day            INTEGER NOT NULL,
            failure_streak INTEGER DEFAULT 0,
            gap_days       INTEGER DEFAULT 0,
            last_active    TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )""",
        """CREATE TABLE IF NOT EXISTS tasks (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         TEXT NOT NULL,
            date            TEXT NOT NULL,
            description     TEXT NOT NULL,
            completed       INTEGER DEFAULT 0,
            failure_streak  INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )""",
        """CREATE TABLE IF NOT EXISTS sources (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     TEXT NOT NULL,
            source_type TEXT NOT NULL,
            content     TEXT NOT NULL,
            added_at    TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )""",
        """CREATE TABLE IF NOT EXISTS agent_log (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      TEXT NOT NULL,
            ts           TEXT DEFAULT (datetime('now','localtime')),
            agent        TEXT NOT NULL,
            action       TEXT NOT NULL,
            route        TEXT,
            detail       TEXT,
            tokens_est   INTEGER DEFAULT 0,
            duration_ms  INTEGER DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS security_audit (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            ts           TEXT    DEFAULT (datetime('now','localtime')),
            input_hash   TEXT    NOT NULL,
            route        TEXT    DEFAULT '',
            model        TEXT    DEFAULT '',
            tokens_in    INTEGER DEFAULT 0,
            tokens_out   INTEGER DEFAULT 0,
            duration_ms  INTEGER DEFAULT 0,
            status       TEXT    DEFAULT 'ok'
        )""",
        """CREATE TABLE IF NOT EXISTS archived_skills (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id           TEXT NOT NULL,
            goal              TEXT NOT NULL,
            category          TEXT NOT NULL,
            level             TEXT NOT NULL,
            milestone_reached INTEGER DEFAULT 0,
            total_milestones  INTEGER DEFAULT 0,
            success_rate      REAL    DEFAULT 0.0,
            strengths         TEXT    DEFAULT '',
            weaknesses        TEXT    DEFAULT '',
            snapshot_text     TEXT    DEFAULT '',
            archived_at       TEXT    DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )""",
    ]

    for stmt in _TABLES:
        conn.execute(stmt)
    conn.commit()

    # Migration: add v5.4 columns to existing DBs
    for _sql in (
        "ALTER TABLE users ADD COLUMN agent_name TEXT DEFAULT 'The Sentinel'",
        "ALTER TABLE users ADD COLUMN agent_vibe TEXT DEFAULT 'motivational'",
    ):
        try:
            conn.execute(_sql)
            conn.commit()
        except Exception:
            pass

    conn.close()


# AGENT LOGGER
def log_agent(
    user_id: str,
    agent: str,
    action: str,
    detail: str = "",
    route: str = "",
    tokens_est: int = 0,
    duration_ms: int = 0,
    db_path: str = None,
) -> None:
    try:
        path = db_path or str(DB_PATH)
        conn = sqlite3.connect(path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            "INSERT INTO agent_log (user_id, agent, action, route, detail, tokens_est, duration_ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, agent, action, route, detail, tokens_est, duration_ms),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


# SECURITY AUDIT LOGGER
def log_audit(
    input_hash: str,
    route: str = "",
    model: str = "",
    tokens_in: int = 0,
    tokens_out: int = 0,
    duration_ms: int = 0,
    status: str = "ok",
    db_path: str = None,
) -> None:
    """Fire-and-forget — never raises, never blocks the caller."""
    try:
        path = db_path or str(DB_PATH)
        conn = sqlite3.connect(path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            "INSERT INTO security_audit "
            "(input_hash, route, model, tokens_in, tokens_out, duration_ms, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (input_hash, route, model, tokens_in, tokens_out, duration_ms, status),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


if __name__ == "__main__":
    init_db()
    print("DB initialized v5.4 -- WAL mode, archived_skills, agent identity, security_audit")
