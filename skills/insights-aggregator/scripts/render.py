#!/usr/bin/env python3
"""render.py — 将 aggregated.json + insights/*.json 渲染为自包含中文 HTML 报告。

用法: python3 render.py [--home ~/.agent-insights] [--out reports/report-YYYY-MM-DD.html]
"""

import argparse
import html
import json
import os
import re
import sys
from datetime import date

LABEL_MAP = {
    # 目标类别
    "debug_investigate": "调试排查", "implement_feature": "实现功能", "fix_bug": "修 Bug",
    "write_script_tool": "写脚本/工具", "refactor_code": "重构代码", "configure_system": "配置系统",
    "create_pr_commit": "提交 PR/Commit", "analyze_data": "数据分析", "understand_codebase": "理解代码库",
    "write_tests": "写测试", "write_docs": "写文档", "deploy_infra": "部署/运维", "warmup_minimal": "预热会话",
    # 成功因素
    "fast_accurate_search": "搜索快且准", "correct_code_edits": "代码改得对",
    "good_explanations": "解释到位", "proactive_help": "主动补位",
    "multi_file_changes": "多文件改动", "handled_complexity": "多文件改动", "good_debugging": "调试给力",
    # 摩擦类型
    "misunderstood_request": "误解需求", "wrong_approach": "方法不对", "buggy_code": "代码有 Bug",
    "user_rejected_action": "用户拒绝操作", "claude_got_blocked": "Agent 被卡住",
    "user_stopped_early": "提前叫停", "wrong_file_or_location": "改错位置",
    "excessive_changes": "改动过度", "slow_or_verbose": "冗长拖沓", "tool_failed": "工具失败",
    "user_unclear": "需求不清", "external_issue": "外部问题",
    # 满意度
    "frustrated": "沮丧", "dissatisfied": "不满", "likely_satisfied": "大概满意",
    "satisfied": "满意", "happy": "开心", "unsure": "不确定", "neutral": "中性", "delighted": "惊喜",
    # 会话类型
    "single_task": "单任务", "multi_task": "多任务", "iterative_refinement": "迭代打磨",
    "exploration": "探索", "quick_question": "快问快答",
    # 结果
    "fully_achieved": "完全达成", "mostly_achieved": "基本达成",
    "partially_achieved": "部分达成", "not_achieved": "未达成", "unclear_from_transcript": "不明确",
    # 帮助程度
    "unhelpful": "没帮上", "slightly_helpful": "略有帮助", "moderately_helpful": "中等帮助",
    "very_helpful": "很有帮助", "essential": "不可或缺",
    # 工具行为类别
    "shell": "终端命令", "edit": "编辑文件", "read": "读取文件", "search": "搜索",
    "web": "联网", "agent": "子代理", "plan": "规划", "mcp": "MCP",
    "browser": "浏览器", "skill": "技能", "other": "其他",
    # 推理强度
    "low": "低", "medium": "中", "high": "高", "xhigh": "极高",
}
SATISFACTION_ORDER = ["frustrated", "dissatisfied", "likely_satisfied", "satisfied", "happy", "unsure"]
OUTCOME_ORDER = ["not_achieved", "partially_achieved", "mostly_achieved", "fully_achieved", "unclear_from_transcript"]
EFFORT_ORDER = ["low", "medium", "high", "xhigh"]
AGENT_BADGE = {"claude-code": ("Claude Code", "#d97706"), "codex": ("Codex", "#0ea5e9")}


def esc(s):
    return html.escape(str(s if s is not None else ""), quote=True)


def md_bold(s):
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", esc(s))


def md_html(md):
    if not md:
        return ""
    return "\n".join(f"<p>{md_bold(p).replace(chr(10), '<br>')}</p>" for p in md.split("\n\n"))


def label(k):
    return LABEL_MAP.get(k, str(k).replace("_", " ").title())


def top_key(d):
    return max(d, key=d.get) if d else None


def bar_chart(data, color, max_items=6, fixed_order=None, raw_labels=False):
    if fixed_order:
        entries = [(k, data[k]) for k in fixed_order if data.get(k, 0) > 0]
    else:
        entries = sorted(data.items(), key=lambda kv: -kv[1])[:max_items]
    if not entries:
        return '<p class="empty">暂无数据</p>'
    mx = max(v for _, v in entries)
    rows = []
    for k, v in entries:
        lbl = str(k) if raw_labels else label(k)
        rows.append(
            f'<div class="bar-row"><div class="bar-label" title="{esc(lbl)}">{esc(lbl)}</div>'
            f'<div class="bar-track"><div class="bar-fill" style="width:{v / mx * 100:.0f}%;background:{color}"></div></div>'
            f'<div class="bar-value">{v}</div></div>')
    return "".join(rows)


def rt_histogram(times):
    if not times:
        return '<p class="empty">暂无数据</p>'
    buckets = [("2-10秒", 2, 10), ("10-30秒", 10, 30), ("30秒-1分", 30, 60), ("1-2分", 60, 120),
               ("2-5分", 120, 300), ("5-15分", 300, 900), (">15分", 900, 1e9)]
    counts = {lbl: sum(1 for t in times if lo <= t < hi) for lbl, lo, hi in buckets}
    mx = max(counts.values()) or 1
    return "".join(
        f'<div class="bar-row"><div class="bar-label">{lbl}</div>'
        f'<div class="bar-track"><div class="bar-fill" style="width:{c / mx * 100:.0f}%;background:#6366f1"></div></div>'
        f'<div class="bar-value">{c}</div></div>'
        for lbl, c in counts.items())


def tod_chart(hours):
    if not hours:
        return '<p class="empty">暂无数据</p>'
    periods = [("上午 (6-12点)", range(6, 12)), ("下午 (12-18点)", range(12, 18)),
               ("晚间 (18-24点)", range(18, 24)), ("深夜 (0-6点)", range(0, 6))]
    counts = [(lbl, sum(1 for h in hours if h in rng)) for lbl, rng in periods]
    mx = max(c for _, c in counts) or 1
    return "".join(
        f'<div class="bar-row"><div class="bar-label">{lbl}</div>'
        f'<div class="bar-track"><div class="bar-fill" style="width:{c / mx * 100:.0f}%;background:#8b5cf6"></div></div>'
        f'<div class="bar-value">{c}</div></div>'
        for lbl, c in counts)


def badge(agent):
    name, color = AGENT_BADGE.get(agent, (agent, "#64748b"))
    return f'<span class="tool-badge" style="background:{color}">{esc(name)}</span>'


def copy_block(text, lbl="粘贴给你的 Agent："):
    return (f'<div class="copyable-prompt-section"><div class="prompt-label">{esc(lbl)}</div>'
            f'<div class="copyable-prompt-row"><code class="copyable-prompt">{esc(text)}</code>'
            f'<button class="copy-btn" onclick="copyText(this)">复制</button></div></div>')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--home", default=os.path.expanduser("~/.agent-insights"))
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    home = args.home

    with open(os.path.join(home, "work/aggregated.json"), encoding="utf-8") as fh:
        agg = json.load(fh)
    ins = {}
    ins_dir = os.path.join(home, "work/insights")
    if os.path.isdir(ins_dir):
        for f in os.listdir(ins_dir):
            if f.endswith(".json"):
                try:
                    with open(os.path.join(ins_dir, f), encoding="utf-8") as fh:
                        ins[f[:-5]] = json.load(fh)
                except (json.JSONDecodeError, OSError):
                    pass

    c = agg["combined"]
    by_agent = agg["by_agent"]
    cross = agg["cross_tool"]
    multi_tool = len(by_agent) > 1
    window = agg.get("window") or {}
    window_label = f"近 {window['days']} 天" if window.get("days") else "全部历史"
    n_internal = agg.get("internal_sessions_excluded") or 0
    internal_note = f" · 已排除 {n_internal} 个子代理/自动评审会话" if n_internal else ""

    # ---- 顶部统计 ----
    stats = [
        (f"{c['total_sessions']}", "会话"),
        (f"{c['sessions_with_facets']}/{c['total_sessions']}", "语义深析"),
        (f"{c['total_messages']:,}", "消息"),
        (f"{c['total_duration_hours']:.0f}h", "活跃时长"),
        (f"{c['git_commits']}", "提交"),
        (f"+{c['total_lines_added']:,}/-{c['total_lines_removed']:,}", "代码行"),
        (f"{c['days_active']}", "活跃天数"),
    ]
    stats_html = "".join(f'<div class="stat"><div class="stat-value">{esc(v)}</div>'
                         f'<div class="stat-label">{esc(l)}</div></div>' for v, l in stats)

    # ---- At a Glance ----
    g = ins.get("at_a_glance") or {}
    glance_items = [("行之有效", g.get("whats_working"), "#section-wins"),
                    ("卡点所在", g.get("whats_hindering"), "#section-friction"),
                    ("工具分工", g.get("tool_division"), "#section-toolcmp"),
                    ("值得做的", g.get("quick_wins"), "#section-features"),
                    ("未来规划", g.get("ambitious_workflows"), "#section-horizon")]
    glance_html = ""
    if any(v for _, v, _ in glance_items):
        rows = "".join(f'<div class="glance-section"><strong>{t}：</strong>{md_bold(v)}'
                       f' <a href="{a}" class="see-more">详见 →</a></div>'
                       for t, v, a in glance_items if v)
        glance_html = f'<div class="at-a-glance"><div class="glance-title">速览</div><div class="glance-sections">{rows}</div></div>'

    # ---- 工具总览表 ----
    tool_rows = ""
    for agent, a in by_agent.items():
        pos = sum(v for k, v in a["satisfaction"].items() if k in ("satisfied", "happy", "likely_satisfied", "delighted"))
        tot_sat = sum(a["satisfaction"].values()) or 1
        ach = sum(v for k, v in a["outcomes"].items() if k in ("fully_achieved", "mostly_achieved"))
        tot_out = sum(a["outcomes"].values()) or 1
        main_model = top_key(a.get("models") or {}) or "—"
        if a.get("reasoning_effort"):
            eff = a["reasoning_effort"]
            hi = sum(eff.get(k, 0) for k in ("high", "xhigh"))
            depth = f"高强度 {hi * 100 // (sum(eff.values()) or 1)}%"
        elif a.get("thinking_total"):
            depth = f"深思 {a['thinking_turns'] * 100 // a['thinking_total']}%"
        else:
            depth = "—"
        tool_rows += (f"<tr><td>{badge(agent)}</td><td><code class='model-name'>{esc(main_model)}</code></td>"
                      f"<td>{depth}</td><td>{a['total_sessions']}</td>"
                      f"<td>{a['total_duration_hours']:.0f}h</td><td>{a['total_messages']:,}</td>"
                      f"<td>{a['git_commits']}</td><td>+{a['total_lines_added']:,}/-{a['total_lines_removed']:,}</td>"
                      f"<td>{a['total_tool_errors']}</td><td>{a['total_interruptions']}</td>"
                      f"<td>{pos * 100 // tot_sat}%</td><td>{ach * 100 // tot_out}%</td></tr>")
    tool_table = (f'<h2 id="section-tools">工具概览</h2><table class="tool-table"><thead><tr>'
                  f"<th>工具</th><th>主力模型</th><th>推理深度</th><th>会话</th><th>时长</th><th>消息</th>"
                  f"<th>提交</th><th>代码行</th><th>报错</th><th>打断</th><th>满意度+</th><th>达成率</th>"
                  f"</tr></thead><tbody>{tool_rows}</tbody></table>") if multi_tool else ""

    # ---- 项目领域 ----
    areas = (ins.get("project_areas") or {}).get("areas") or []
    areas_html = ""
    if areas:
        rows = ""
        for a in areas:
            tools = "".join(badge(t) for t in a.get("tools_used") or [])
            rows += (f'<div class="project-area"><div class="area-header"><span class="area-name">{esc(a.get("name"))}</span>'
                     f'<span>{tools}<span class="area-count">约 {esc(a.get("session_count"))} 个会话</span></span></div>'
                     f'<div class="area-desc">{esc(a.get("description"))}</div></div>')
        areas_html = f'<h2 id="section-work">工作版图</h2><div class="project-areas">{rows}</div>'

    # ---- 交互风格 ----
    style = ins.get("interaction_style") or {}
    style_html = ""
    if style.get("narrative"):
        kp = f'<div class="key-insight"><strong>关键模式：</strong>{esc(style.get("key_pattern"))}</div>' if style.get("key_pattern") else ""
        style_html = f'<h2 id="section-usage">和Agent的协作方式</h2><div class="narrative">{md_html(style["narrative"])}{kp}</div>'

    # ---- 工具对比（跨工具）----
    tc = ins.get("tool_comparison") or {}
    tc_html = ""
    if multi_tool and tc.get("narrative"):
        division = ""
        for d in tc.get("division_of_labor") or []:
            models_line = f'<div class="card-line"><strong>模型：</strong><code class="model-name">{esc(d["models"])}</code></div>' if d.get("models") else ""
            division += (f'<div class="division-card">{badge(d.get("tool", ""))}{models_line}'
                         f'<div class="card-line"><strong>擅长：</strong>{md_bold(d.get("best_at_for_you", ""))}</div>'
                         f'<div class="card-line"><strong>注意：</strong>{md_bold(d.get("watch_out", ""))}</div></div>')
        fit = ""
        for o in tc.get("model_fit_observations") or []:
            fit += (f'<div class="fit-card"><div class="card-line">{md_bold(o.get("observation", ""))}</div>'
                    f'<div class="card-line fit-suggest"><strong>建议：</strong>{md_bold(o.get("suggestion", ""))}</div></div>')
        fit_html = f'<h3 class="sub-h3">任务与模型的适配观察</h3><div class="fit-row">{fit}</div>' if fit else ""
        rec = f'<div class="key-insight"><strong>建议：</strong>{md_bold(tc.get("recommendation", ""))}</div>' if tc.get("recommendation") else ""
        tc_html = (f'<h2 id="section-toolcmp">分工格局：Claude Code vs Codex</h2>'
                   f'<div class="narrative">{md_html(tc["narrative"])}</div>'
                   f'<div class="division-row">{division}</div>{fit_html}{rec}')

    # ---- 做得漂亮的地方 ----
    ww = ins.get("what_works") or {}
    ww_html = ""
    if ww.get("impressive_workflows"):
        intro = f'<p class="section-intro">{esc(ww.get("intro"))}</p>' if ww.get("intro") else ""
        cards = "".join(f'<div class="big-win"><div class="card-title">{esc(w.get("title"))}</div>'
                        f'<div class="card-line">{md_bold(w.get("description", ""))}</div></div>'
                        for w in ww["impressive_workflows"])
        ww_html = f'<h2 id="section-wins">使用亮点</h2>{intro}<div class="big-wins">{cards}</div>'

    # ---- 摩擦 ----
    fa = ins.get("friction_analysis") or {}
    fr_html = ""
    if fa.get("categories"):
        intro = f'<p class="section-intro">{esc(fa.get("intro"))}</p>' if fa.get("intro") else ""
        cats = ""
        for cat in fa["categories"]:
            ex = "".join(f"<li>{esc(e)}</li>" for e in cat.get("examples") or [])
            cats += (f'<div class="friction-category"><div class="friction-title">{esc(cat.get("category"))}</div>'
                     f'<div class="friction-desc">{esc(cat.get("description"))}</div>'
                     f'<ul class="friction-examples">{ex}</ul></div>')
        fr_html = f'<h2 id="section-friction">摩擦与症结</h2>{intro}<div class="friction-categories">{cats}</div>'

    # ---- 建议 ----
    sg = ins.get("suggestions") or {}
    sg_html = ""
    if sg:
        parts = []
        adds = sg.get("config_additions") or []
        if adds:
            items = ""
            for i, a in enumerate(adds):
                tgt = esc(a.get("target_file", "CLAUDE.md"))
                data_text = esc(f"[{a.get('target_file', '')}] {a.get('prompt_scaffold') or ''}\\n\\n{a.get('addition', '')}")
                items += (f'<div class="claude-md-item"><input type="checkbox" id="cmd-{i}" class="cmd-checkbox" checked data-text="{data_text}">'
                          f'<label for="cmd-{i}"><code class="cmd-code"><span class="cmd-target">{tgt}</span> {esc(a.get("addition"))}</code>'
                          f'<button class="copy-btn" onclick="copyCmdItem({i})">复制</button></label>'
                          f'<div class="cmd-why">{esc(a.get("why"))}</div></div>')
            parts.append(f'<h2 id="section-features">沉淀与进阶</h2>'
                         f'<div class="claude-md-section"><h3>沉淀为持久配置（CLAUDE.md / AGENTS.md）</h3>'
                         f'<p class="hint">勾选后一键复制，粘贴给任一 Agent 即可帮你写入对应配置文件。</p>'
                         f'<div class="claude-md-actions"><button class="copy-all-btn" onclick="copyAllCheckedClaudeMd()">复制选中项</button></div>{items}</div>')
        feats = sg.get("features_to_try") or []
        if feats:
            fcards = ""
            for f in feats:
                code = copy_block(f["example_code"], "复制使用：") if f.get("example_code") else ""
                fcards += (f'<div class="feature-card"><div class="card-title">{esc(f.get("feature"))} {badge(f.get("applies_to", "")) if f.get("applies_to") not in (None, "both") else ""}</div>'
                           f'<div class="card-line">{esc(f.get("one_liner"))}</div>'
                           f'<div class="card-line"><strong>对你的价值：</strong>{esc(f.get("why_for_you"))}</div>{code}</div>')
            parts.append(f'<h3 class="sub-h3">待解锁的功能</h3><div class="features-section">{fcards}</div>')
        pats = sg.get("usage_patterns") or []
        if pats:
            pcards = ""
            for p in pats:
                cp = copy_block(p["copyable_prompt"]) if p.get("copyable_prompt") else ""
                pcards += (f'<div class="pattern-card"><div class="card-title">{esc(p.get("title"))}</div>'
                           f'<div class="card-line">{esc(p.get("suggestion"))}</div>'
                           f'<div class="card-line">{esc(p.get("detail"))}</div>{cp}</div>')
            parts.append(f'<h2 id="section-patterns">用法进阶</h2><div class="patterns-section">{pcards}</div>')
        sg_html = "".join(parts)

    # ---- 跨工具组合 ----
    cw = ins.get("cross_tool_workflows") or {}
    cw_html = ""
    if multi_tool and (cw.get("observed_patterns") or cw.get("combination_suggestions")):
        intro = f'<p class="section-intro">{esc(cw.get("intro"))}</p>' if cw.get("intro") else ""
        obs = ""
        for o in cw.get("observed_patterns") or []:
            ev = f'<div class="feedback-evidence"><em>证据：</em>{esc(o.get("evidence"))}</div>' if o.get("evidence") else ""
            obs += (f'<div class="horizon-card"><div class="card-title">{esc(o.get("title"))}</div>'
                    f'<div class="card-line">{md_bold(o.get("description", ""))}</div>{ev}</div>')
        sug = ""
        for s in cw.get("combination_suggestions") or []:
            cp = copy_block(s["copyable_prompt"]) if s.get("copyable_prompt") else ""
            sug += (f'<div class="pattern-card"><div class="card-title">{esc(s.get("title"))}</div>'
                    f'<div class="card-line">{md_bold(s.get("suggestion", ""))}</div>{cp}</div>')
        ov = cross["overlap"]
        dirs = cross["handoffs"]["direction_counts"]
        dir_txt = "，".join(f"{k} × {v}" for k, v in dirs.items()) or "无"
        facts = (f'<div class="key-insight">数据信号：跨工具并行事件 {ov["cross_tool_overlap_events"]} 次；'
                 f'同项目接力 {dir_txt}。</div>')
        cw_html = (f'<h2 id="section-crosstool">跨工具协同</h2>{intro}{facts}'
                   f'<div class="horizon-section">{obs}</div><h3 class="sub-h3">组合建议</h3>'
                   f'<div class="patterns-section">{sug}</div>')

    # ---- 项目 × 工具矩阵 ----
    matrix_html = ""
    if multi_tool and cross.get("project_tool_matrix"):
        agents = sorted(by_agent.keys())
        head = "".join(f"<th>{esc(AGENT_BADGE.get(a, (a,))[0])}</th>" for a in agents)
        rows = ""
        for proj, counts in list(cross["project_tool_matrix"].items())[:15]:
            cells = "".join(f"<td>{counts.get(a, 0) or '·'}</td>" for a in agents)
            rows += f'<tr><td class="proj-name">{esc(proj)}</td>{cells}</tr>'
        matrix_html = (f'<div class="chart-card matrix-card"><div class="chart-title">项目 × 工具（会话数）</div>'
                       f'<table class="tool-table small"><thead><tr><th>项目</th>{head}</tr></thead><tbody>{rows}</tbody></table></div>')

    # ---- 未来可期 ----
    oh = ins.get("on_the_horizon") or {}
    oh_html = ""
    if oh.get("opportunities"):
        intro = f'<p class="section-intro">{esc(oh.get("intro"))}</p>' if oh.get("intro") else ""
        cards = ""
        for o in oh["opportunities"]:
            tip = f'<div class="horizon-tip"><strong>如何开始：</strong>{esc(o.get("how_to_try"))}</div>' if o.get("how_to_try") else ""
            cp = copy_block(o["copyable_prompt"]) if o.get("copyable_prompt") else ""
            cards += (f'<div class="horizon-card"><div class="card-title">{esc(o.get("title"))}</div>'
                      f'<div class="card-line">{esc(o.get("whats_possible"))}</div>{tip}{cp}</div>')
        oh_html = f'<h2 id="section-horizon">未来可期</h2>{intro}<div class="horizon-section">{cards}</div>'

    # ---- 图表 ----
    agent_sessions = {AGENT_BADGE.get(a, (a,))[0]: g2["total_sessions"] for a, g2 in by_agent.items()}
    codex_effort = (by_agent.get("codex") or {}).get("reasoning_effort") or {}
    charts = [
        ("各工具会话数", bar_chart(agent_sessions, "#0ea5e9", raw_labels=True)) if multi_tool else None,
        ("模型构成（按轮次）", bar_chart(c.get("models") or {}, "#14b8a6", 8, raw_labels=True)),
        ("Codex 推理强度分布", bar_chart(codex_effort, "#a855f7", fixed_order=EFFORT_ORDER)) if codex_effort else None,
        ("工具行为类别", bar_chart(c.get("tool_category_counts") or {}, "#3b82f6", 9)),
        ("任务目标", bar_chart(c["goal_categories"], "#10b981", 8)),
        ("涉及语言", bar_chart(c["languages"], "#f59e0b", 8)),
        ("任务结果", bar_chart(c["outcomes"], "#22c55e", fixed_order=OUTCOME_ORDER)),
        ("满意度信号", bar_chart(c["satisfaction"], "#eab308", fixed_order=SATISFACTION_ORDER)),
        ("摩擦类型", bar_chart(c["friction"], "#ef4444", 8)),
        ("工具报错类别", bar_chart(c["tool_error_categories"], "#f97316", 7, raw_labels=True)),
        ("你的响应耗时", rt_histogram(c.get("response_times") or [])),
        ("使用时段", tod_chart(c["message_hours"])),
    ]
    charts_html = "".join(f'<div class="chart-card"><div class="chart-title">{esc(t)}</div>{b}</div>'
                          for tb in charts if tb for t, b in [tb])

    # ---- 趣味结尾 ----
    fe = ins.get("fun_ending") or {}
    fe_html = ""
    if fe.get("headline"):
        det = f'<div class="fun-detail">{esc(fe.get("detail"))}</div>' if fe.get("detail") else ""
        fe_html = f'<div class="fun-ending"><div class="fun-headline">“{esc(fe["headline"])}”</div>{det}</div>'

    toc = [("#section-tools", "工具总览") if multi_tool else None, ("#section-work", "项目领域"),
           ("#section-usage", "协作风格"), ("#section-toolcmp", "分工对比") if multi_tool else None,
           ("#section-wins", "亮点"), ("#section-friction", "摩擦"),
           ("#section-features", "建议"), ("#section-crosstool", "跨工具组合") if multi_tool else None,
           ("#section-horizon", "未来"), ("#section-charts", "图表")]
    toc_html = "".join(f'<a href="{a}">{t}</a>' for x in toc if x for a, t in [x])

    css = """
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', -apple-system, sans-serif; background: #f8fafc; color: #334155; line-height: 1.7; padding: 48px 24px; }
    .container { max-width: 880px; margin: 0 auto; }
    h1 { font-size: 30px; font-weight: 700; color: #0f172a; margin-bottom: 8px; }
    h2 { font-size: 20px; font-weight: 600; color: #0f172a; margin-top: 48px; margin-bottom: 16px; }
    .sub-h3 { font-size: 15px; font-weight: 600; color: #334155; margin: 20px 0 12px; }
    .subtitle { color: #64748b; font-size: 14px; margin-bottom: 24px; }
    .hint { font-size: 12px; color: #64748b; margin-bottom: 12px; }
    .nav-toc { display: flex; flex-wrap: wrap; gap: 8px; margin: 16px 0 28px; padding: 14px; background: white; border-radius: 8px; border: 1px solid #e2e8f0; }
    .nav-toc a { font-size: 12px; color: #64748b; text-decoration: none; padding: 6px 12px; border-radius: 6px; background: #f1f5f9; }
    .nav-toc a:hover { background: #e2e8f0; color: #334155; }
    .stats-row { display: flex; gap: 24px; margin-bottom: 36px; padding: 18px 0; border-top: 1px solid #e2e8f0; border-bottom: 1px solid #e2e8f0; flex-wrap: wrap; }
    .stat { text-align: center; }
    .stat-value { font-size: 22px; font-weight: 700; color: #0f172a; }
    .stat-label { font-size: 12px; color: #64748b; }
    .at-a-glance { background: linear-gradient(135deg, #fef3c7, #fde68a); border: 1px solid #f59e0b; border-radius: 12px; padding: 20px 24px; margin-bottom: 32px; }
    .glance-title { font-size: 16px; font-weight: 700; color: #92400e; margin-bottom: 14px; }
    .glance-sections { display: flex; flex-direction: column; gap: 12px; }
    .glance-section { font-size: 14px; color: #78350f; }
    .glance-section strong { color: #92400e; }
    .see-more { color: #b45309; text-decoration: none; font-size: 13px; white-space: nowrap; }
    .tool-badge { display: inline-block; color: white; font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 10px; margin-right: 6px; }
    .model-name { font-family: monospace; font-size: 12px; background: #f1f5f9; padding: 1px 6px; border-radius: 4px; color: #0f766e; }
    .tool-table { width: 100%; border-collapse: collapse; background: white; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; font-size: 13px; }
    .tool-table th { background: #f1f5f9; text-align: left; padding: 8px 10px; font-size: 12px; color: #64748b; white-space: nowrap; }
    .tool-table td { padding: 8px 10px; border-top: 1px solid #f1f5f9; }
    .tool-table.small { font-size: 12px; }
    .proj-name { font-family: monospace; font-size: 11px; }
    .project-areas, .big-wins, .friction-categories, .features-section, .patterns-section, .horizon-section { display: flex; flex-direction: column; gap: 12px; margin-bottom: 24px; }
    .project-area { background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; }
    .area-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
    .area-name { font-weight: 600; font-size: 15px; color: #0f172a; }
    .area-count { font-size: 12px; color: #64748b; background: #f1f5f9; padding: 2px 8px; border-radius: 4px; }
    .area-desc { font-size: 14px; color: #475569; }
    .narrative { background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; margin-bottom: 16px; }
    .narrative p { margin-bottom: 12px; font-size: 14px; color: #475569; line-height: 1.8; }
    .key-insight { background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 12px 16px; margin: 12px 0; font-size: 14px; color: #166534; }
    .section-intro { font-size: 14px; color: #64748b; margin-bottom: 16px; }
    .card-title { font-weight: 600; font-size: 15px; color: #0f172a; margin-bottom: 6px; }
    .card-line { font-size: 13px; color: #475569; margin-bottom: 6px; line-height: 1.6; }
    .big-win { background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 16px; }
    .big-win .card-title { color: #166534; }
    .friction-category { background: #fef2f2; border: 1px solid #fca5a5; border-radius: 8px; padding: 16px; }
    .friction-title { font-weight: 600; font-size: 15px; color: #991b1b; margin-bottom: 6px; }
    .friction-desc { font-size: 13px; color: #7f1d1d; margin-bottom: 10px; }
    .friction-examples { margin-left: 20px; font-size: 13px; color: #334155; }
    .division-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: 12px 0; }
    .division-card { background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px; }
    .fit-row { display: flex; flex-direction: column; gap: 10px; margin-bottom: 12px; }
    .fit-card { background: #fffbeb; border: 1px solid #fcd34d; border-radius: 8px; padding: 12px 16px; }
    .fit-suggest { color: #92400e; }
    .claude-md-section { background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; padding: 16px; margin-bottom: 20px; }
    .claude-md-section h3 { font-size: 14px; font-weight: 600; color: #1e40af; margin-bottom: 8px; }
    .claude-md-actions { margin-bottom: 12px; padding-bottom: 12px; border-bottom: 1px solid #dbeafe; }
    .copy-all-btn { background: #2563eb; color: white; border: none; border-radius: 4px; padding: 6px 12px; font-size: 12px; cursor: pointer; font-weight: 500; }
    .copy-all-btn.copied { background: #16a34a; }
    .claude-md-item { display: flex; flex-wrap: wrap; align-items: flex-start; gap: 8px; padding: 10px 0; border-bottom: 1px solid #dbeafe; }
    .claude-md-item:last-child { border-bottom: none; }
    .claude-md-item label { display: flex; flex: 1; gap: 8px; align-items: flex-start; }
    .cmd-code { background: white; padding: 8px 12px; border-radius: 4px; font-size: 12px; color: #1e40af; border: 1px solid #bfdbfe; font-family: inherit; display: block; white-space: pre-wrap; word-break: break-word; flex: 1; }
    .cmd-target { background: #1e40af; color: white; border-radius: 3px; padding: 1px 6px; font-size: 10px; margin-right: 4px; font-family: monospace; }
    .cmd-why { font-size: 12px; color: #64748b; width: 100%; padding-left: 24px; }
    .feature-card { background: #f0fdf4; border: 1px solid #86efac; border-radius: 8px; padding: 16px; }
    .pattern-card { background: #f0f9ff; border: 1px solid #7dd3fc; border-radius: 8px; padding: 16px; }
    .copyable-prompt-section { margin-top: 10px; padding-top: 10px; border-top: 1px solid #e2e8f0; }
    .copyable-prompt-row { display: flex; align-items: flex-start; gap: 8px; }
    .copyable-prompt { flex: 1; background: #f8fafc; padding: 10px 12px; border-radius: 4px; font-family: inherit; font-size: 12px; color: #334155; border: 1px solid #e2e8f0; white-space: pre-wrap; }
    .prompt-label { font-size: 11px; font-weight: 600; color: #64748b; margin-bottom: 6px; }
    .copy-btn { background: #e2e8f0; border: none; border-radius: 4px; padding: 4px 10px; font-size: 11px; cursor: pointer; color: #475569; flex-shrink: 0; }
    .charts-row { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 20px 0; }
    .chart-card { background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; }
    .matrix-card { grid-column: 1 / -1; }
    .chart-title { font-size: 13px; font-weight: 600; color: #64748b; margin-bottom: 12px; }
    .bar-row { display: flex; align-items: center; margin-bottom: 6px; }
    .bar-label { width: 130px; font-size: 11px; color: #475569; flex-shrink: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .bar-track { flex: 1; height: 6px; background: #f1f5f9; border-radius: 3px; margin: 0 8px; }
    .bar-fill { height: 100%; border-radius: 3px; }
    .bar-value { width: 40px; font-size: 11px; font-weight: 500; color: #64748b; text-align: right; }
    .empty { color: #94a3b8; font-size: 13px; }
    .horizon-card { background: linear-gradient(135deg, #faf5ff, #f5f3ff); border: 1px solid #c4b5fd; border-radius: 8px; padding: 16px; }
    .horizon-card .card-title { color: #5b21b6; }
    .horizon-tip { font-size: 13px; color: #6b21a8; background: rgba(255,255,255,.6); padding: 8px 12px; border-radius: 4px; margin-top: 8px; }
    .feedback-evidence { font-size: 12px; color: #64748b; margin-top: 8px; }
    .fun-ending { background: linear-gradient(135deg, #fef3c7, #fde68a); border: 1px solid #fbbf24; border-radius: 12px; padding: 24px; margin-top: 40px; text-align: center; }
    .fun-headline { font-size: 18px; font-weight: 600; color: #78350f; margin-bottom: 8px; }
    .fun-detail { font-size: 14px; color: #92400e; }
    @media (max-width: 640px) { .charts-row, .division-row { grid-template-columns: 1fr; } }
    """

    js = """
    function copyText(btn) {
      const code = btn.parentElement.querySelector('code') || btn.previousElementSibling;
      navigator.clipboard.writeText(code.textContent).then(() => {
        btn.textContent = '已复制!'; setTimeout(() => { btn.textContent = '复制'; }, 2000);
      });
    }
    function copyCmdItem(i) {
      const cb = document.getElementById('cmd-' + i);
      navigator.clipboard.writeText(cb.dataset.text.replace(/\\\\n/g, '\\n'));
      const btn = cb.parentElement.querySelector('.copy-btn');
      btn.textContent = '已复制!'; setTimeout(() => { btn.textContent = '复制'; }, 2000);
    }
    function copyAllCheckedClaudeMd() {
      const texts = [...document.querySelectorAll('.cmd-checkbox:checked')].map(cb => cb.dataset.text.replace(/\\\\n/g, '\\n'));
      navigator.clipboard.writeText(texts.join('\\n\\n---\\n\\n'));
      const btn = document.querySelector('.copy-all-btn');
      btn.textContent = '已复制 ' + texts.length + ' 条!'; btn.classList.add('copied');
      setTimeout(() => { btn.textContent = '复制选中项'; btn.classList.remove('copied'); }, 2500);
    }
    """

    agents_label = " + ".join(AGENT_BADGE.get(a, (a,))[0] for a in by_agent)
    doc = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Agent 使用洞察 — {esc(agents_label)}</title>
<style>{css}</style></head>
<body><div class="container">
<h1>Agent 使用洞察报告</h1>
<div class="subtitle">{esc(agents_label)} · {esc(window_label)}（{esc(c['date_range'].get('start'))} 至 {esc(c['date_range'].get('end'))}）{esc(internal_note)} · 生成于 {date.today().isoformat()}</div>
<div class="nav-toc">{toc_html}</div>
<div class="stats-row">{stats_html}</div>
{glance_html}
{tool_table}
{areas_html}
{style_html}
{tc_html}
{ww_html}
{fr_html}
{sg_html}
{cw_html}
{oh_html}
<h2 id="section-charts">数据全景</h2>
<div class="charts-row">{charts_html}{matrix_html}</div>
{fe_html}
<script>{js}</script>
</div></body></html>"""

    out = args.out or os.path.join(home, "reports", f"report-{date.today().isoformat()}.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(doc)
    os.chmod(out, 0o600)
    print(json.dumps({"report": out, "bytes": len(doc),
                      "sections_rendered": sorted(ins.keys())}, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
