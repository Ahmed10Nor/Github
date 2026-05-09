# dashboard/streamlit_app.py
import streamlit as st
import sqlite3
import sys
import os
import time
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import get_connection, DB_PATH
from orchestrator import LuminAgentsOrchestrator

st.set_page_config(page_title="LuminAgents Dashboard", layout="wide", page_icon="🧠")

# ── Custom CSS ────────────────────────────────────────────────
st.markdown("""
<style>
.agent-row { padding: 6px 10px; border-radius: 6px; margin: 3px 0; font-family: monospace; font-size: 13px; }
.agent-orchestrator { background: #1e1b4b; color: #a5b4fc; }
.agent-coach        { background: #052e16; color: #86efac; }
.agent-planner      { background: #0c1a2e; color: #93c5fd; }
.agent-researcher   { background: #2d1b4e; color: #d8b4fe; }
.agent-fixer        { background: #2d0a0a; color: #fca5a5; }
.agent-onboarding   { background: #1a1a00; color: #fde047; }
.ts { color: #6b7280; font-size: 11px; margin-right: 8px; }
.route-badge { display: inline-block; padding: 1px 6px; border-radius: 10px; font-size: 11px; font-weight: bold; margin-right: 6px; }
.rb-daily_check      { background: #3b0764; color: #e9d5ff; }
.rb-content_question { background: #172554; color: #bfdbfe; }
.rb-plan_change      { background: #052e16; color: #bbf7d0; }
.rb-out_of_scope     { background: #450a0a; color: #fecaca; }
.rb-onboarding       { background: #422006; color: #fde68a; }
.rb-gap              { background: #431407; color: #fed7aa; }
</style>
""", unsafe_allow_html=True)

st.title("🧠 LuminAgents — Live Dashboard")

orc = LuminAgentsOrchestrator()

# ── Sidebar ────────────────────────────────────────────────────
st.sidebar.title("🎮 Demo Controls")
demo_user_id = st.sidebar.text_input("User ID", value="demo_001")

col_a, col_b = st.sidebar.columns(2)
with col_a:
    auto_refresh = st.checkbox("🔄 Auto", value=True)
with col_b:
    refresh_sec = st.selectbox("ثانية", [2, 3, 5], index=0, label_visibility="collapsed")

st.sidebar.divider()

if st.sidebar.button("⚡ Inject streak = 3"):
    conn = get_connection()
    conn.execute("UPDATE tasks SET failure_streak = 3 WHERE user_id = ?", (demo_user_id,))
    conn.commit(); conn.close()
    st.sidebar.success("✅ streak = 3")

if st.sidebar.button("🔄 Reset streak"):
    conn = get_connection()
    conn.execute("UPDATE tasks SET failure_streak = 0 WHERE user_id = ?", (demo_user_id,))
    conn.commit(); conn.close()
    st.sidebar.success("✅ Reset")

if st.sidebar.button("🗑️ Delete user"):
    conn = get_connection()
    for tbl in ["tasks", "milestones", "snapshots", "users", "daily_tasks", "agent_log"]:
        try:
            conn.execute(f"DELETE FROM {tbl} WHERE user_id = ?", (demo_user_id,))
        except Exception:
            pass
    conn.commit(); conn.close()
    st.sidebar.success("✅ Deleted")

if st.sidebar.button("🧹 Clear log"):
    conn = get_connection()
    conn.execute("DELETE FROM agent_log WHERE user_id = ?", (demo_user_id,))
    conn.commit(); conn.close()
    st.sidebar.success("✅ Log cleared")

# ── Tabs ──────────────────────────────────────────────────────
tab_live, tab_consensus, tab_profile, tab_test, tab_graph = st.tabs([
    "📡 Agent Activity", "🤝 Agent Consensus", "👤 Profile & Plan", "💬 Test Router", "🕸️ Dependency Graph"
])

# ════════════════════════════════════════════════════
# TAB 1 — AGENT ACTIVITY LOG
# ════════════════════════════════════════════════════
with tab_live:
    st.subheader("📡 Agent Activity Log — Live")

    conn = get_connection()
    logs = conn.execute(
        "SELECT * FROM agent_log WHERE user_id = ? ORDER BY id DESC LIMIT 60",
        (demo_user_id,)
    ).fetchall()
    conn.close()

    total_tokens = sum(r["tokens_est"] for r in logs) if logs else 0
    total_llm    = sum(1 for r in logs if r["tokens_est"] > 0) if logs else 0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("📨 Events", len(logs))
    m2.metric("🔤 Tokens Est.", total_tokens)
    m3.metric("🤖 LLM Calls", total_llm)
    m4.metric("⚙️ Agents", len(set(r["agent"] for r in logs)) if logs else 0)

    st.divider()

    if not logs:
        st.info("لا يوجد نشاط بعد — ابعث رسالة للبوت أو استخدم Test Router")
    else:
        ICONS = {
            "orchestrator": "⚙️", "coach": "🎓", "planner": "📋",
            "researcher": "🔍", "fixer": "🔧", "onboarding": "🆕",
        }
        for row in logs:
            agent  = row["agent"]
            action = row["action"]
            detail = row["detail"] or ""
            route  = row["route"] or ""
            tokens = row["tokens_est"]
            dur    = row["duration_ms"]
            ts     = (row["ts"] or "")[-8:]
            icon   = ICONS.get(agent, "•")

            route_html  = f'<span class="route-badge rb-{route}">{route}</span>' if route else ""
            token_html  = f' <span style="color:#6b7280;font-size:11px;">~{tokens}t</span>' if tokens > 0 else ""
            dur_html    = f' <span style="color:#6b7280;font-size:11px;">{dur}ms</span>' if dur > 0 else ""
            detail_html = f'  <span style="opacity:0.8">{detail}</span>' if detail else ""

            st.markdown(
                f'<div class="agent-row agent-{agent}">'
                f'<span class="ts">{ts}</span>'
                f'{route_html}'
                f'<b>{icon} {agent}</b> → <i>{action}</i>'
                f'{detail_html}{token_html}{dur_html}'
                f'</div>',
                unsafe_allow_html=True,
            )

    if auto_refresh:
        time.sleep(refresh_sec)
        st.rerun()

# ════════════════════════════════════════════════════
# TAB 2 — AGENT CONSENSUS (v5.1)
# ════════════════════════════════════════════════════
with tab_consensus:
    st.subheader("🤝 Internal Agent Consensus — جدال الوكلاء الداخلي")
    st.caption(
        "يُفعَّل تلقائياً عند: plan_change أو failure_streak ≥ 2 | "
        "Coach (تقدم) يجادل Fixer (استقرار) → Orchestrator يحكم"
    )

    conn = get_connection()
    debate_rows = conn.execute(
        """
        SELECT * FROM agent_log
        WHERE user_id = ?
          AND action IN ('consensus_perspective', 'consensus_decision', 'consensus_triggered')
        ORDER BY id DESC LIMIT 60
        """,
        (demo_user_id,),
    ).fetchall()
    conn.close()

    if not debate_rows:
        st.info(
            "لا يوجد جدال بعد — أرسل رسالة تطلب تغيير الخطة، أو ارفع streak إلى 2 من الـ Sidebar."
        )
    else:
        # Group every 3 debate rows (triggered → coach+fixer perspectives → decision)
        # We display them grouped: newest debate first
        entries = list(debate_rows)
        # Separate by type for display
        debates: list[dict] = []
        buffer: dict = {}

        for row in reversed(entries):  # oldest-first for grouping
            action = row["action"]
            ts     = (row["ts"] or "")[-8:]
            route  = row["route"] or ""
            detail = row["detail"] or ""
            agent  = row["agent"]

            if action == "consensus_triggered":
                # Start a new debate group
                if buffer:
                    debates.append(buffer)
                buffer = {"ts": ts, "route": route, "trigger": detail,
                          "coach": "", "fixer": "", "decision": ""}

            elif action == "consensus_perspective":
                if not buffer:
                    buffer = {"ts": ts, "route": route, "trigger": "",
                              "coach": "", "fixer": "", "decision": ""}
                if agent == "coach":
                    buffer["coach"] = detail
                elif agent == "fixer":
                    buffer["fixer"] = detail

            elif action == "consensus_decision":
                if not buffer:
                    buffer = {"ts": ts, "route": route, "trigger": "",
                              "coach": "", "fixer": "", "decision": ""}
                buffer["decision"] = detail
                debates.append(buffer)
                buffer = {}

        if buffer:  # flush any incomplete group
            debates.append(buffer)

        # Display newest first
        for i, debate in enumerate(reversed(debates)):
            route_label = debate.get("route", "")
            ts_label    = debate.get("ts", "")
            with st.expander(
                f"⚡ جدال #{len(debates) - i}  |  route: {route_label}  |  {ts_label}",
                expanded=(i == 0),
            ):
                col_coach, col_fixer = st.columns(2)

                with col_coach:
                    st.markdown(
                        '<div style="background:#052e16;color:#86efac;padding:12px;'
                        'border-radius:8px;border-left:4px solid #22c55e;">'
                        '<b>🎓 Coach — التقدم أولاً</b><br/>'
                        f'<span style="font-size:13px">{debate.get("coach") or "—"}</span>'
                        "</div>",
                        unsafe_allow_html=True,
                    )

                with col_fixer:
                    st.markdown(
                        '<div style="background:#2d0a0a;color:#fca5a5;padding:12px;'
                        'border-radius:8px;border-left:4px solid #ef4444;">'
                        '<b>🔧 Fixer — الاستقرار أولاً</b><br/>'
                        f'<span style="font-size:13px">{debate.get("fixer") or "—"}</span>'
                        "</div>",
                        unsafe_allow_html=True,
                    )

                st.markdown("<br/>", unsafe_allow_html=True)
                decision_text = debate.get("decision") or ""
                action_key    = ""
                for key in ("rebuild", "simplify", "proceed_adjusted", "proceed"):
                    if key in decision_text:
                        action_key = key
                        break
                action_colors = {
                    "rebuild":          ("#450a0a", "#fecaca", "🔴"),
                    "simplify":         ("#422006", "#fde68a", "🟡"),
                    "proceed_adjusted": ("#0c1a2e", "#93c5fd", "🔵"),
                    "proceed":          ("#052e16", "#bbf7d0", "🟢"),
                }
                bg, fg, emoji = action_colors.get(action_key, ("#1e1b4b", "#a5b4fc", "⚪"))
                st.markdown(
                    f'<div style="background:{bg};color:{fg};padding:12px;'
                    f'border-radius:8px;border:1px solid {fg}40;">'
                    f'<b>⚙️ Orchestrator — القرار النهائي {emoji}</b><br/>'
                    f'<span style="font-size:13px">{decision_text or "—"}</span>'
                    f"</div>",
                    unsafe_allow_html=True,
                )

# ════════════════════════════════════════════════════
# TAB 3 — PROFILE & PLAN
# ════════════════════════════════════════════════════
with tab_profile:
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("👤 User Profile")
        conn = get_connection()
        user = conn.execute("SELECT * FROM users WHERE user_id = ?", (demo_user_id,)).fetchone()
        conn.close()
        if user:
            st.json({
                "name":            user["name"],
                "goal":            user["goal"],
                "level":           user["level"],
                "estimated_weeks": user["estimated_weeks"],
                "start_date":      user["start_date"],
                "onboarding":      "✅ complete" if user["onboarding_complete"] else f"⏳ {user['onboarding_step']}",
            })
        else:
            st.warning("المستخدم غير موجود")

    with col2:
        st.subheader("📊 Streak")
        conn = get_connection()
        task = conn.execute(
            "SELECT * FROM tasks WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (demo_user_id,)
        ).fetchone()
        conn.close()
        if task:
            streak = task["failure_streak"]
            color  = "🔴" if streak >= 3 else "🟡" if streak >= 1 else "🟢"
            st.metric("Failure Streak", f"{color} {streak}")
            st.metric("Last Task", task["description"][:80])
            st.metric("Completed", "✅" if task["completed"] else "❌")
        else:
            st.info("لا توجد مهام بعد")

    st.subheader("🗺️ Milestones")
    conn = get_connection()
    milestones = conn.execute(
        "SELECT * FROM milestones WHERE user_id = ? ORDER BY week_start",
        (demo_user_id,)
    ).fetchall()
    conn.close()
    if milestones:
        for m in milestones:
            st.write(f"{'✅' if m['completed'] else '⏳'} **{m['title']}** — Week {m['week_start']}→{m['week_end']}")
    else:
        st.info("لا توجد milestones بعد")

    st.subheader("🧠 Planner Snapshots")
    conn = get_connection()
    snaps = conn.execute(
        "SELECT * FROM snapshots WHERE user_id = ? ORDER BY id DESC LIMIT 3",
        (demo_user_id,)
    ).fetchall()
    conn.close()
    if snaps:
        for s in snaps:
            with st.expander(f"Milestone {s['milestone_index']} — {s['created_at']}"):
                st.code(s["snapshot"])
    else:
        st.info("لا توجد snapshots بعد")

# ════════════════════════════════════════════════════
# TAB 3 — TEST ROUTER
# ════════════════════════════════════════════════════
with tab_test:
    st.subheader("💬 Test Message Router")
    st.caption("اختبر رسالة مباشرة — النتيجة تظهر هنا والـ Activity Log يتحدث")

    test_msg = st.text_input("الرسالة:", placeholder='مثال: "كيف أتعلم Python؟" أو "خلصت الدرس"')
    if st.button("▶️ إرسال", type="primary") and test_msg:
        with st.spinner("الـ agents تعمل..."):
            reply = orc.handle_message(demo_user_id, test_msg)
        st.success("**الرد:**")
        st.write(reply)
        st.info("📡 راجع تبويب Agent Activity لترى تفاصيل القرارات")
