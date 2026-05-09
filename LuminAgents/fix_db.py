import sqlite3

conn = sqlite3.connect('db/luminagents.db')
conn.execute('PRAGMA journal_mode=WAL')

# milestones
existing = [r[1] for r in conn.execute('PRAGMA table_info(milestones)').fetchall()]
print('milestones columns:', existing)
for col, default in [('lesson_ids', '[]'), ('snapshot', '')]:
    if col not in existing:
        conn.execute(f"ALTER TABLE milestones ADD COLUMN {col} TEXT DEFAULT '{default}'")
        print(f'Added milestones.{col}')

# daily_tasks
existing = [r[1] for r in conn.execute('PRAGMA table_info(daily_tasks)').fetchall()]
print('daily_tasks columns:', existing)
for col, typedef in [
    ('week', 'INTEGER DEFAULT 1'),
    ('lesson_id', 'TEXT DEFAULT ""'),
    ('hours', 'REAL DEFAULT 1.0'),
    ('completed', 'INTEGER DEFAULT 0'),
]:
    if col not in existing:
        conn.execute(f'ALTER TABLE daily_tasks ADD COLUMN {col} {typedef}')
        print(f'Added daily_tasks.{col}')

# agent_log — create if not exists
conn.execute("""
    CREATE TABLE IF NOT EXISTS agent_log (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id      TEXT NOT NULL,
        ts           TEXT DEFAULT (datetime('now','localtime')),
        agent        TEXT NOT NULL,
        action       TEXT NOT NULL,
        route        TEXT,
        detail       TEXT,
        tokens_est   INTEGER DEFAULT 0,
        duration_ms  INTEGER DEFAULT 0
    )
""")
print('agent_log table ready')

# security_audit — create if not exists (v6.0 Lite)
conn.execute("""
    CREATE TABLE IF NOT EXISTS security_audit (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        ts           TEXT    DEFAULT (datetime('now','localtime')),
        input_hash   TEXT    NOT NULL,
        route        TEXT    DEFAULT '',
        model        TEXT    DEFAULT '',
        tokens_in    INTEGER DEFAULT 0,
        tokens_out   INTEGER DEFAULT 0,
        duration_ms  INTEGER DEFAULT 0,
        status       TEXT    DEFAULT 'ok'
    )
""")
print('security_audit table ready')

conn.commit()
conn.close()
print('Done.')
