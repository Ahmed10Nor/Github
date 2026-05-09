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
/* ── Agent log rows ── */
.agent-row {
    padding: 7px 12px; border-radius: 8px; margin: 4px 0;
    font-family: 'JetBrains Mono', 'Fira Code', monospace; font-size: 12.5px;
    border-left: 3px solid transparent; transition: opacity 0.2s;
}
.agent-orchestrator { background: #1e1b4b; color: #a5b4fc; border-left-color: #6366f1; }
.agent-coach        { background: #052e16; color: #86efac; border-left-color: #22c55e; }
.agent-planner      { background: #0c1a2e; color: #93c5fd; border-left-color: #3b82f6; }
.agent-researcher   { background: #2d1b4e; color: #d8b4fe; border-left-color: #a855f7; }
.agent-fixer        { background: #2d0a0a; color: #fca5a5; border-left-color: #ef4444; }
.agent-onboarding   { background: #1a1a00; color: #fde047; border-left-color: #eab308; }

/* ── Timestamps & metadata ── */
.ts   { color: #4b5563; font-size: 10.5px; margin-right: 10px; letter-spacing: 0.3px; }
.meta { color: #6b7280; font-size: 10.5px; }

/* ── Route badges ── */
.route-badge {
    display: inline-block; padding: 2px 7px; border-radius: 12px;
    font-size: 10.5px; font-weight: 700; margin-right: 6px; letter-spacing: 0.2px;
}
.rb-daily_check      { background: #3b0764; color: #e9d5ff; }
.rb-content_question { background: #172554; color: #bfdbfe; }
.rb-plan_change      { background: #052e16; color: #bbf7d0; }
.rb-out_of_scope     { background: #450a0a; color: #fecaca; }
.rb-onboarding       { background: #422006; color: #fde68a; }
.rb-gap              { background: #431407; color: #fed7aa; }
.rb-goal_reset       { background: #1a0030; color: #d8b4fe; }
.rb-greeting_checkin { background: #0a2010; color: #86efac; }

/* ── Status pill ── */
.status-pill {
    display: inline-flex; align-items: center; gap: 5px;
    padding: 3px 10px; border-radius: 20px; font-size: 11.5px; font-weight: 600;
}
.pill-ok  { background: #052e16; color: #4ade80; border: 1px solid #166534; }
.pill-off { background: #1c1c1c; color: #6b7280; border: 1px solid #374151; }
.pill-err { background: #2d0a0a; color: #f87171; border: 1px solid #7f1d1d; }

/* ── Metric card ── */
.kpi-card {
    background: #111827; border: 1px solid #1f2937; border-radius: 10px;
    padding: 14px 18px; text-align: center;
}
.kpi-val  { font-size: 28px; font-weight: 700; color: #f3f4f6; line-height: 1.1; }
.kpi-lbl  { font-size: 11px; color: #6b7280; margin-top: 4px; letter-spacing: 0.5px; text-transform: uppercase; }

/* ── Milestone bar ── */
.ms-row { display: flex; align-items: center; gap: 10px; padding: 6px 0; }
.ms-bar-bg  { flex: 1; background: #1f2937; border-radius: 4px; height: 6px; }
.ms-bar-fill { height: 6px; border-radius: 4px; background: #22c55e; }
.ms-bar-fill.pending { background: #374151; }
</style>
""", unsafe_allow_html=True)

st.markdown(
    '<div style="display:flex;align-items:baseline;gap:12px;margin-bottom:2px;">'
    '<span style="font-size:28px;font-weight:800;color:#f1f5f9;letter-spacing:-0.5px;">🧠 LuminAgents</span>'
    '<span style="font-size:13px;color:#64748b;font-style:italic;">Multi-Agent Skill Coaching System</span>'
    '<span style="margin-left:auto;background:#1e3a8a;color:#93c5fd;font-size:11px;'
    'font-weight:700;padding:3px 10px;border-radius:12px;border:1px solid #1d4ed8;">v7.5</span>'
    '</div>'
    '<div style="height:1px;background:linear-gradient(90deg,#3b82f6,#8b5cf6,transparent);margin-bottom:10px;"></div>',
    unsafe_allow_html=True,
)

# ── System health bar ─────────────────────────────────────────
_db_ok, _orc_ok = False, False
try:
    _hc = get_connection(); _hc.execute("SELECT 1"); _hc.close(); _db_ok = True
except Exception:
    pass

orc = LuminAgentsOrchestrator()
_orc_ok = orc is not None

def _pill(label, ok, err=False):
    cls = "pill-err" if err else ("pill-ok" if ok else "pill-off")
    dot = "🔴" if err else ("🟢" if ok else "⚫")
    return f'<span class="status-pill {cls}">{dot} {label}</span>'

st.markdown(
    '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:6px;">'
    + _pill("Database", _db_ok)
    + _pill("Orchestrator", _orc_ok)
    + _pill("Security Audit", True)
    + _pill("Web-First (Tavily)", True)
    + '</div>',
    unsafe_allow_html=True,
)

# ── Sidebar ────────────────────────────────────────────────────
st.sidebar.markdown(
    '<div style="text-align:center;padding:8px 0 4px;">'
    '<span style="font-size:20px;font-weight:800;color:#f1f5f9;">🎮 Demo Controls</span>'
    '</div>',
    unsafe_allow_html=True,
)
st.sidebar.divider()

# ── User selector (dropdown — no free text to avoid exposing real IDs)
_known_users: list[str] = []
try:
    _uc = get_connection()
    _rows = _uc.execute("SELECT DISTINCT user_id FROM users ORDER BY user_id").fetchall()
    _uc.close()
    _known_users = [r["user_id"] for r in _rows if r["user_id"]]
except Exception:
    pass
if not _known_users:
    _known_users = ["demo_001"]

demo_user_id = st.sidebar.selectbox(
    "👤 Active User",
    _known_users,
    index=0,
    help="المستخدم المعروض في جميع التبويبات",
)

st.sidebar.caption(f"`{demo_user_id}`")
st.sidebar.divider()

col_a, col_b = st.sidebar.columns(2)
with col_a:
    auto_refresh = st.checkbox("🔄 Auto", value=True)
with col_b:
    refresh_sec = st.selectbox("⏱", [2, 3, 5], index=0, label_visibility="collapsed")

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

# ── Security Audit Quick Stats ──────────────────────
st.sidebar.divider()
st.sidebar.markdown("**🔐 Security Audit**")
try:
    _ac = get_connection()
    _ar = _ac.execute(
        "SELECT COUNT(*) as n, SUM(tokens_in+tokens_out) as t, "
        "SUM(CASE WHEN status='error' THEN 1 ELSE 0 END) as e, "
        "AVG(duration_ms) as avg_ms "
        "FROM security_audit"
    ).fetchone()
    _ac.close()
    if _ar and _ar["n"]:
        _c1, _c2 = st.sidebar.columns(2)
        _c1.metric("Calls", _ar["n"])
        _c2.metric("Tokens", f'{(_ar["t"] or 0):,}')
        _err = _ar["e"] or 0
        _avg = int(_ar["avg_ms"] or 0)
        _c3, _c4 = st.sidebar.columns(2)
        _c3.metric("Errors", f'{"⚠️ " if _err else "✅ "}{_err}')
        _c4.metric("Avg ms", _avg)
    else:
        st.sidebar.info("No audit records yet")
except Exception:
    st.sidebar.caption("security_audit not ready — run fix_db.py")

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
    agents_active = len(set(r["agent"] for r in logs)) if logs else 0
    avg_dur = (
        int(sum(r["duration_ms"] for r in logs if r["duration_ms"]) /
            max(1, sum(1 for r in logs if r["duration_ms"])))
        if logs else 0
    )

    m1, m2, m3, m4, m5 = st.columns(5)
    for col, val, lbl in [
        (m1, len(logs),      "Events"),
        (m2, total_tokens,   "Tokens Est."),
        (m3, total_llm,      "LLM Calls"),
        (m4, agents_active,  "Agents Active"),
        (m5, f"{avg_dur}ms", "Avg Latency"),
    ]:
        col.markdown(
            f'<div class="kpi-card"><div class="kpi-val">{val}</div>'
            f'<div class="kpi-lbl">{lbl}</div></div>',
            unsafe_allow_html=True,
        )

    st.divider()

    if not logs:
        st.markdown(
            '<div style="text-align:center;padding:40px;color:#374151;">'
            '<div style="font-size:40px;margin-bottom:8px;">💤</div>'
            '<div style="font-size:15px;font-weight:600;color:#6b7280;">لا يوجد نشاط بعد</div>'
            '<div style="font-size:12px;color:#4b5563;margin-top:4px;">'
            'ابعث رسالة للبوت أو استخدم تبويب <b>Test Router</b></div>'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        ICONS = {
            "orchestrator": "⚙️", "coach": "🎓", "planner": "📋",
            "researcher": "🔍", "fixer": "🔧", "onboarding": "🆕",
        }

        # Filter bar
        _all_agents = sorted(set(r["agent"] for r in logs))
        _filter_col1, _filter_col2 = st.columns([2, 3])
        with _filter_col1:
            _agent_filter = st.multiselect(
                "Filter by agent", _all_agents, default=_all_agents,
                label_visibility="collapsed", placeholder="Filter by agent…"
            )
        with _filter_col2:
            _route_filter = st.multiselect(
                "Filter by route",
                sorted(set(r["route"] for r in logs if r["route"])),
                label_visibility="collapsed", placeholder="Filter by route…"
            )

        for row in logs:
            agent  = row["agent"]
            if _agent_filter and agent not in _agent_filter:
                continue
            route  = row["route"] or ""
            if _route_filter and route not in _route_filter:
                continue

            action = row["action"]
            detail = row["detail"] or ""
            tokens = row["tokens_est"]
            dur    = row["duration_ms"]
            ts     = (row["ts"] or "")[-8:]
            icon   = ICONS.get(agent, "•")

            route_html  = f'<span class="route-badge rb-{route}">{route}</span>' if route else ""
            token_html  = f'<span class="meta"> ·~{tokens}t</span>' if tokens > 0 else ""
            dur_html    = f'<span class="meta"> ·{dur}ms</span>' if dur > 0 else ""
            detail_html = (
                f'<span style="opacity:0.72;font-size:11.5px;"> — {detail[:120]}{"…" if len(detail)>120 else ""}</span>'
                if detail else ""
            )

            st.markdown(
                f'<div class="agent-row agent-{agent}">'
                f'<span class="ts">{ts}</span>'
                f'{route_html}'
                f'<b>{icon} {agent}</b> → <code style="font-size:11px;opacity:0.9">{action}</code>'
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
        entries = list(debate_rows)
        debates: list[dict] = []
        buffer: dict = {}

        for row in reversed(entries):
            action = row["action"]
            ts     = (row["ts"] or "")[-8:]
            route  = row["route"] or ""
            detail = row["detail"] or ""
            agent  = row["agent"]

            if action == "consensus_triggered":
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

        if buffer:
            debates.append(buffer)

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
                "user_id":         demo_user_id,
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
        total_ms  = len(milestones)
        done_ms   = sum(1 for m in milestones if m["completed"])
        pct       = int(done_ms / total_ms * 100)
        st.markdown(
            f'<div style="background:#111827;border:1px solid #1f2937;border-radius:10px;padding:14px 18px;margin-bottom:10px;">'
            f'<div style="display:flex;justify-content:space-between;margin-bottom:8px;">'
            f'<span style="color:#94a3b8;font-size:12px;font-weight:600;">OVERALL PROGRESS</span>'
            f'<span style="color:#f1f5f9;font-weight:700;">{done_ms}/{total_ms} milestones</span></div>'
            f'<div style="background:#1f2937;border-radius:6px;height:8px;">'
            f'<div style="background:linear-gradient(90deg,#22c55e,#16a34a);width:{pct}%;height:8px;border-radius:6px;"></div>'
            f'</div><div style="text-align:right;color:#4ade80;font-size:12px;margin-top:4px;">{pct}%</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        for m in milestones:
            done   = bool(m["completed"])
            icon   = "✅" if done else "⏳"
            color  = "#22c55e" if done else "#374151"
            label  = m["title"]
            weeks  = f"Wk {m['week_start']}–{m['week_end']}"
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:10px;padding:6px 0;'
                f'border-bottom:1px solid #1f2937;">'
                f'<span style="font-size:16px;">{icon}</span>'
                f'<span style="flex:1;color:#e2e8f0;font-size:13px;font-weight:500;">{label}</span>'
                f'<span style="background:#1f2937;color:#64748b;font-size:10.5px;'
                f'padding:2px 8px;border-radius:10px;">{weeks}</span>'
                f'<div style="width:60px;background:#1f2937;border-radius:4px;height:5px;">'
                f'<div style="background:{color};width:{"100" if done else "0"}%;height:5px;border-radius:4px;"></div>'
                f'</div></div>',
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            '<div style="text-align:center;padding:20px;color:#4b5563;">'
            '<div style="font-size:32px;">🗺️</div>'
            '<div style="font-size:13px;margin-top:4px;">لا توجد milestones — أكمل الـ onboarding أولاً</div>'
            '</div>', unsafe_allow_html=True,
        )

    st.subheader("🧠 Planner Snapshots")
    conn = get_connection()
    snaps = conn.execute(
        "SELECT * FROM snapshots WHERE user_id = ? ORDER BY id DESC LIMIT 3",
        (demo_user_id,)
    ).fetchall()
    conn.close()
    if snaps:
        for s in snaps:
            with st.expander(f"📸 Snapshot — Milestone {s['milestone_index']}  |  {s['created_at']}"):
                st.code(s["snapshot"], language=None)
    else:
        st.info("لا توجد snapshots بعد")

# ════════════════════════════════════════════════════
# TAB 4 — TEST ROUTER
# ════════════════════════════════════════════════════
with tab_test:
    st.subheader("💬 Test Message Router")
    st.caption("اختبر رسالة مباشرة — النتيجة تظهر هنا والـ Activity Log يتحدث")

    _quick = [
        "كيف أتعلم Python؟",
        "خلصت الدرس اليوم",
        "أبي تغيير في الخطة",
        "وين أتعلم من؟",
        "هذا المستوى سهل بالنسبة لي",
        "ما فيه فايدة، تعبت",
    ]
    test_msg = st.text_input(
        "الرسالة:",
        placeholder='مثال: "كيف أتعلم Python؟" أو "خلصت الدرس"',
        label_visibility="collapsed",
    )
    st.caption("💡 رسائل سريعة:")
    _qcols = st.columns(len(_quick))
    for _qc, _qt in zip(_qcols, _quick):
        if _qc.button(_qt, use_container_width=True):
            test_msg = _qt

    if st.button("▶️ إرسال", type="primary", use_container_width=True) and test_msg:
        import asyncio as _asyncio
        _t0 = time.time()
        with st.spinner("⚙️ الـ agents تعمل..."):
            try:
                if _asyncio.iscoroutinefunction(orc.handle_message):
                    reply = _asyncio.run(orc.handle_message(demo_user_id, test_msg))
                else:
                    reply = orc.handle_message(demo_user_id, test_msg)
            except Exception as _e:
                reply = f"❌ Error: {_e}"
        _elapsed = round((time.time() - _t0) * 1000)
        st.markdown(
            f'<div style="background:#0f2027;border:1px solid #22c55e33;border-radius:10px;'
            f'padding:16px 20px;margin-top:10px;">'
            f'<div style="display:flex;justify-content:space-between;margin-bottom:8px;">'
            f'<span style="color:#22c55e;font-weight:700;font-size:13px;">✅ رد الوكيل</span>'
            f'<span style="color:#4b5563;font-size:11px;">⏱ {_elapsed}ms</span></div>'
            f'<div style="color:#e2e8f0;font-size:14px;line-height:1.7;white-space:pre-wrap;">{reply}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.caption("📡 راجع تبويب Agent Activity لترى تفاصيل القرارات الداخلية")

# ════════════════════════════════════════════════════
# TAB 5 — SEMANTIC DEPENDENCY GRAPH
# ════════════════════════════════════════════════════
with tab_graph:
    st.subheader("🕸️ Semantic Dependency Graph — تدفق الوكلاء الحي")
    st.caption(
        "يعكس آخر جلسة للمستخدم المختار | "
        "🟢 أخضر = نجاح | 🔴 أحمر = فشل / Fixer | "
        "🟡 أصفر = تحذير / LLM Synthesis | 🔵 أزرق = تدفق عادي | ⚫ رمادي = غير نشط"
    )

    # Read logs
    conn_g = get_connection()
    g_rows = conn_g.execute(
        "SELECT agent, action, route, detail FROM agent_log "
        "WHERE user_id = ? ORDER BY id DESC LIMIT 100",
        (demo_user_id,),
    ).fetchall()
    conn_g.close()

    # Parse state
    last_route  = None
    res_tier    = None
    res_ok      = None
    sem_gap     = False
    cons_action = None
    fixer_on    = False
    fixer_via   = None
    planner_on  = False
    coach_on    = False

    for (_, action, route, detail) in g_rows:
        d = (detail or "").lower()
        r = route or ""
        if action == "route_decision" and last_route is None:
            last_route = r
        if action == "fetch_result" and res_tier is None:
            if   "wiki"      in d: res_tier = "wiki"
            elif "tavily"    in d: res_tier = "tavily"
            elif "synthesis" in d: res_tier = "synthesis"
            else:                  res_tier = "kb"
            res_ok = True
        if action == "no_info" and res_tier is None:
            res_tier = "no_info"; res_ok = False
        if action == "semantic_gap" and not sem_gap:
            sem_gap = "practical challenge" in d or "challenge_hint" in d
        if action == "consensus_decision" and cons_action is None:
            for _a in ("rebuild", "simplify", "proceed_adjusted", "proceed"):
                if _a in d: cons_action = _a; break
        if action in ("streak_intervention", "gap_intervention") and not fixer_on:
            fixer_on = True
            fixer_via = "streak" if "streak" in action else "gap"
        if action in ("revise", "build", "rebuild") and not planner_on:
            planner_on = True
        if action in ("answer_question", "daily_task", "greeting_checkin", "meta_info") and not coach_on:
            coach_on = True

    # Colour constants
    _G  = "#22c55e"; _R  = "#ef4444"; _Y  = "#f59e0b"
    _B  = "#60a5fa"; _P  = "#a78bfa"; _GR = "#374151"
    _W  = "#e2e8f0"; _DIM = "#1e2837"; _DIMB = "#2d3f55"

    def _c(cond, col, idle=None): return col if cond else (idle or _GR)
    def _w(cond, w=2.5, wi=1.0):  return w   if cond else wi

    import math

    # Node positions on 920×540 canvas
    _N = {
        "user":       (460, 50),
        "router":     (460, 140),
        "researcher": (75,  265),
        "coach":      (240, 265),
        "consensus":  (440, 265),
        "planner":    (635, 265),
        "fixer":      (815, 265),
        "kb_t1":      (30,  390),
        "kb_t2":      (120, 390),
        "kb_t3":      (210, 390),
        "kb_t4":      (310, 390),
        "snapshot":   (795, 390),
        "output":     (460, 490),
    }

    # Node active styles (fill, border)
    _cons_styles = {
        "proceed":          ("#064e3b", "#22c55e"),
        "proceed_adjusted": ("#1e3a8a", "#60a5fa"),
        "simplify":         ("#78350f", "#f59e0b"),
        "rebuild":          ("#7f1d1d", "#ef4444"),
    }
    _NS = {
        "user":       ("#4f46e5", "#818cf8"),
        "router":     ("#6d28d9", "#a78bfa") if last_route else (_DIM, _DIMB),
        "researcher": ("#5b21b6", "#8b5cf6") if last_route == "content_question" else (_DIM, _DIMB),
        "coach":      ("#065f46", "#34d399") if coach_on else (_DIM, _DIMB),
        "consensus":  _cons_styles.get(cons_action, ("#3b2f0e", "#92400e")) if cons_action else (_DIM, _DIMB),
        "planner":    ("#1e3a8a", "#60a5fa") if planner_on else (_DIM, _DIMB),
        "fixer":      ("#7f1d1d", "#f87171") if fixer_on else (_DIM, _DIMB),
        "kb_t1":      ("#064e3b", "#10b981") if res_tier == "kb"       else (_DIM, _DIMB),
        "kb_t2":      ("#064e3b", "#10b981") if res_tier == "wiki"     else (_DIM, _DIMB),
        "kb_t3":      ("#1a3a1a", "#4ade80") if res_tier == "tavily"   else (_DIM, _DIMB),
        "kb_t4":      ("#78350f", "#fbbf24") if res_tier == "synthesis"
                      else ("#7f1d1d", "#f87171") if res_tier == "no_info" else (_DIM, _DIMB),
        "snapshot":   ("#1e3a5f", "#38bdf8") if (
                          last_route in ("daily_check", "greeting_checkin") or planner_on
                      ) else (_DIM, _DIMB),
        "output":     ("#1f3a2f", "#4ade80") if (coach_on or planner_on or fixer_on) else (_DIM, _DIMB),
    }

    # SVG helpers
    def _marker(hx):
        nm = hx.replace("#", "")
        return (
            f'<marker id="arr-{nm}" markerWidth="10" markerHeight="7" '
            f'refX="9" refY="3.5" orient="auto">'
            f'<polygon points="0 0,10 3.5,0 7" fill="{hx}"/>'
            f'</marker>'
        )

    def _edge(src, dst, hex_c, sw, label="", dashed=False):
        x0, y0 = _N[src]; x1, y1 = _N[dst]
        dx, dy = x1-x0, y1-y0
        dist   = math.sqrt(dx*dx + dy*dy) or 1
        nd     = 30
        ax0 = x0 + nd*dx/dist; ay0 = y0 + nd*dy/dist
        ax1 = x1 - nd*dx/dist; ay1 = y1 - nd*dy/dist
        dash  = 'stroke-dasharray="5,4" ' if dashed else ""
        mn    = "arr-" + hex_c.replace("#", "")
        line  = (
            f'<line x1="{ax0:.1f}" y1="{ay0:.1f}" x2="{ax1:.1f}" y2="{ay1:.1f}" '
            f'stroke="{hex_c}" stroke-width="{sw:.1f}" {dash}'
            f'marker-end="url(#{mn})"/>'
        )
        lbl = ""
        if label:
            mx = (x0+x1)/2; my = (y0+y1)/2
            ox = -10*dy/dist; oy = 10*dx/dist
            lbl = (
                f'<rect x="{mx+ox-22:.1f}" y="{my+oy-7:.1f}" width="44" height="13" '
                f'rx="3" fill="#0f172a" opacity="0.88"/>'
                f'<text x="{mx+ox:.1f}" y="{my+oy+1:.1f}" text-anchor="middle" '
                f'dominant-baseline="middle" fill="{hex_c}" '
                f'font-size="9" font-family="monospace">{label}</text>'
            )
        return line + lbl

    def _node(nid, lines, r=26):
        x, y  = _N[nid]
        fill, border = _NS[nid]
        glow   = f'<circle cx="{x}" cy="{y}" r="{r+6}" fill="{border}" opacity="0.12"/>'
        circle = (
            f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" '
            f'stroke="{border}" stroke-width="2"/>'
        )
        texts  = ""
        for i, ln in enumerate(lines):
            dy2 = (i - (len(lines)-1)/2) * 14
            texts += (
                f'<text x="{x}" y="{y+dy2:.1f}" text-anchor="middle" '
                f'dominant-baseline="middle" fill="{_W}" '
                f'font-size="11" font-family="monospace">{ln}</text>'
            )
        return glow + circle + texts

    # Derived edge colours
    _in_cq    = last_route == "content_question"
    _in_daily = last_route in ("daily_check", "greeting_checkin")
    _in_plan  = last_route == "plan_change"
    _in_gap   = last_route == "gap" or fixer_via == "gap"

    _tier_c   = {"kb": _G, "wiki": _G, "tavily": _G, "synthesis": _Y, "no_info": _R}
    _rc2c     = _Y if sem_gap else (_G if res_ok else (_R if res_ok is False else _GR))
    _cons_c   = {"proceed": _G, "proceed_adjusted": _B,
                 "simplify": _Y, "rebuild": _R}.get(cons_action, _GR)

    _used_hex = {
        _G, _R, _Y, _B, _P, _GR, _rc2c, _cons_c,
        _c(_in_cq, _G), _c(_in_daily, _G), _c(_in_plan, _B), _c(_in_gap, _R),
        _tier_c.get(res_tier, _GR),
    }
    _markers_svg = "".join(_marker(h) for h in _used_hex)

    _fixer_rebuild_c = _c(fixer_on and fixer_via == "streak", _R)
    _edges_svg = "".join([
        _edge("user",       "router",     _P,                        2.5),
        _edge("router",     "researcher", _c(_in_cq,    _G),         _w(_in_cq),    "content_q"),
        _edge("router",     "coach",      _c(_in_daily, _G),         _w(_in_daily), "daily"),
        _edge("router",     "consensus",  _c(_in_plan,  _B),         _w(_in_plan),  "plan_chg"),
        _edge("router",     "fixer",      _c(_in_gap,   _R),         _w(_in_gap),   "gap"),
        _edge("researcher", "kb_t1",      _c(res_tier=="kb",    _G), _w(res_tier=="kb")),
        _edge("researcher", "kb_t2",      _c(res_tier=="wiki",  _G), _w(res_tier=="wiki")),
        _edge("researcher", "kb_t3",      _c(res_tier=="tavily",_G), _w(res_tier=="tavily")),
        _edge("researcher", "kb_t4",
              _tier_c.get(res_tier, _GR) if res_tier in ("synthesis","no_info") else _GR,
              _w(res_tier in ("synthesis","no_info")),
              "NO_INFO" if res_tier == "no_info" else ("Synth" if res_tier == "synthesis" else "")),
        _edge("researcher", "coach",      _rc2c,
              _w(res_ok is not None),    "gap" if sem_gap else ("ctx" if res_ok else "")),
        _edge("coach",      "consensus",  _c(cons_action is not None, _B),
              _w(cons_action is not None), "", True),
        _edge("fixer",      "consensus",  _c(cons_action is not None, _B),
              _w(cons_action is not None), "", True),
        _edge("consensus",  "planner",    _cons_c, _w(cons_action is not None), cons_action or ""),
        _edge("snapshot",   "coach",      _c(_in_daily,    _B), _w(_in_daily),    "read", True),
        _edge("planner",    "snapshot",   _c(planner_on,   _B), _w(planner_on),   "save", True),
        _edge("fixer",      "planner",    _fixer_rebuild_c,
              _w(fixer_on and fixer_via=="streak"), "rebuild"),
        _edge("coach",      "output",     _c(coach_on,   _G), _w(coach_on)),
        _edge("planner",    "output",     _c(planner_on, _G), _w(planner_on)),
        _edge("fixer",      "output",     _c(fixer_on,   _G), _w(fixer_on)),
    ])

    _node_defs = [
        ("user",       ["User Input"],   28),
        ("router",     ["Router"],       26),
        ("researcher", ["Researcher"],   24),
        ("coach",      ["Coach"],        24),
        ("consensus",  ["Consensus"],    24),
        ("planner",    ["Planner"],      24),
        ("fixer",      ["Fixer"],        24),
        ("kb_t1",      ["KB Local"],     19),
        ("kb_t2",      ["Wikipedia"],    19),
        ("kb_t3",      ["Tavily"],       19),
        ("kb_t4",      ["LLM Synth"],    19),
        ("snapshot",   ["Snapshot"],     19),
        ("output",     ["Response"],     28),
    ]
    _nodes_svg = "".join(_node(nid, lines, r) for nid, lines, r in _node_defs)

    _emoji_map = {
        "user": ("💬", 50), "router": ("⚙️", 140), "researcher": ("🔍", 265),
        "coach": ("🎓", 265), "consensus": ("🤝", 265), "planner": ("📋", 265),
        "fixer": ("🔧", 265), "kb_t1": ("📚", 390), "kb_t2": ("🌐", 390),
        "kb_t3": ("🔎", 390), "kb_t4": ("🤖", 390), "snapshot": ("💾", 390),
        "output": ("📤", 490),
    }
    _emoji_svg = "".join(
        f'<text x="{_N[nid][0]}" y="{_N[nid][1]-2}" text-anchor="middle" '
        f'dominant-baseline="middle" font-size="14">{em}</text>'
        for nid, (em, _) in _emoji_map.items()
    )

    _SW, _SH = 920, 540
    _seps = "".join(
        f'<line x1="20" y1="{y}" x2="{_SW-20}" y2="{y}" '
        f'stroke="#1e293b" stroke-width="1" stroke-dasharray="3,6"/>'
        for y in (95, 200, 328, 442)
    )
    _layer_labels = "".join(
        f'<text x="{_SW-8}" y="{y}" text-anchor="end" fill="#334155" '
        f'font-size="9" font-family="monospace">{txt}</text>'
        for y, txt in [(50,"INPUT"),(140,"ROUTER"),(265,"AGENTS"),(390,"KNOWLEDGE"),(490,"OUTPUT")]
    )

    _svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_SW}" height="{_SH}" '
        f'style="background:#0f172a;border-radius:12px;display:block;margin:auto;max-width:100%">'
        f'<defs>{_markers_svg}</defs>'
        f'<rect width="{_SW}" height="{_SH}" rx="12" fill="#0f172a"/>'
        f'{_seps}{_edges_svg}{_nodes_svg}{_emoji_svg}{_layer_labels}'
        f'</svg>'
    )

    st.html(f'<div style="overflow-x:auto;padding:4px 0">{_svg}</div>')

    st.divider()
    _g1, _g2, _g3, _g4, _g5 = st.columns(5)
    _route_lbl = {
        "content_question": "content_q", "daily_check": "daily",
        "greeting_checkin": "greeting",  "plan_change":  "plan_change",
        "goal_reset": "goal_reset",      "out_of_scope": "OOS", "gap": "gap",
    }.get(last_route, "—")
    _tier_lbl  = {"kb":"KB Local","wiki":"Wikipedia","tavily":"Tavily",
                  "synthesis":"LLM Synth","no_info":"NO_INFO"}.get(res_tier,"—")
    _cons_lbl  = {"proceed":"proceed","proceed_adjusted":"adjusted",
                  "simplify":"simplify","rebuild":"rebuild"}.get(cons_action,"—")
    _g1.metric("Route",        _route_lbl)
    _g2.metric("Researcher",   _tier_lbl)
    _g3.metric("Semantic Gap", "detected" if sem_gap else "clean")
    _g4.metric("Consensus",    _cons_lbl)
    _g5.metric("Fixer",        fixer_via if fixer_on else "idle")
