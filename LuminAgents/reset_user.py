"""
reset_user.py — حذف بيانات مستخدم من DB ليبدأ من جديد كمستخدم جديد.
الاستخدام:
    python reset_user.py <user_id>
    python reset_user.py 962258831
"""
import sys
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "db" / "luminagents.db"

TABLES = ["users", "milestones", "tasks", "agent_logs", "coach_logs"]


def reset_user(user_id: str) -> None:
    if not DB_PATH.exists():
        print(f"❌ DB not found: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")

    deleted = {}
    for table in TABLES:
        try:
            cur = conn.execute(f"DELETE FROM {table} WHERE user_id = ?", (user_id,))
            deleted[table] = cur.rowcount
        except sqlite3.OperationalError:
            deleted[table] = 0

    conn.commit()
    conn.close()

    print(f"\n✅ تم حذف بيانات المستخدم: {user_id}")
    for table, count in deleted.items():
        if count > 0:
            print(f"   {table}: حذف {count} صف")
    print("\nالبوت الآن سيعامله كمستخدم جديد تماماً.\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("الاستخدام: python reset_user.py <user_id>")
        print("مثال:     python reset_user.py 962258831")
        sys.exit(1)

    uid = sys.argv[1]
    confirm = input(f"هل تريد حذف جميع بيانات المستخدم '{uid}'؟ (yes/no): ").strip().lower()
    if confirm in ("yes", "y", "نعم"):
        reset_user(uid)
    else:
        print("تم الإلغاء.")
