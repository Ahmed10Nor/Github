GRAPH_TAB_CODE = r'''
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

    # All hex colours used (for arrowhead markers)
    _used_hex = {
        _G, _R, _Y, _B, _P, _GR, _rc2c, _cons_c,
        _c(_in_cq, _G), _c(_in_daily, _G), _c(_in_plan, _B), _c(_in_gap, _R),
        _tier_c.get(res_tier, _GR),
    }
    _markers_svg = "".join(_marker(h) for h in _used_hex)

    # Edge list
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

    # Node definitions
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

    # Node emoji labels (separate text above each node)
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

    # Layer separators and labels
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

    # State summary
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
'''
