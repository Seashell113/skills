#!/usr/bin/env python3
"""aggregate.py — 合并 SessionMeta + Facets，输出全局/分工具聚合与跨工具关联分析。

输入（--home 目录，由 collect.py 与 LLM facet 提取层产生）:
  cache/meta/{agent}/*.json      SessionMeta
  cache/facets/{agent}/*.json    SessionFacets（LLM 写入）

输出:
  work/aggregated.json           全部聚合数据（combined + per-agent + cross_tool）
  work/insight-context.md        供 insight section 生成用的 LLM 上下文
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

HANDOFF_WINDOW_MIN = 45      # 同项目跨工具接力窗口
OVERLAP_WINDOW_MS = 30 * 60_000  # 并行检测滑动窗口（与源码一致）
MAX_SUMMARIES = 60
MAX_FRICTION = 25
MAX_INSTRUCTIONS = 20

REQUIRED_FACET_KEYS = ("underlying_goal", "outcome", "brief_summary",
                       "goal_categories", "user_satisfaction_counts", "friction_counts")


def load_dir(d):
    out = []
    if not os.path.isdir(d):
        return out
    for f in os.listdir(d):
        if f.endswith(".json"):
            try:
                with open(os.path.join(d, f), encoding="utf-8") as fh:
                    out.append(json.load(fh))
            except (json.JSONDecodeError, OSError):
                pass
    return out


def valid_facet(f):
    return isinstance(f, dict) and all(k in f for k in REQUIRED_FACET_KEYS)


def parse_iso(s):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, AttributeError, TypeError):
        return None


def bump(d, k, n=1):
    if k:
        d[k] = d.get(k, 0) + n


def normalize_project(p):
    """统一斜杠后取尾部两段作为项目键：同一项目在不同根路径下
    （如 ~/Desktop/workspace/projects/skills 与 ~/workspace/projects/skills）也能对齐。"""
    parts = (p or "").rstrip("/").split("/")
    return "/".join(parts[-2:]) if len(parts) >= 2 else (p or "(unknown)")


def project_label(p):
    return normalize_project(p)


# ---------------------------------------------------------------------------
# 单组会话聚合（combined 与 per-agent 共用）
# ---------------------------------------------------------------------------

def aggregate_group(metas, facets_by_key):
    r = {
        "total_sessions": len(metas), "sessions_with_facets": 0,
        "date_range": {"start": "", "end": ""},
        "total_messages": 0, "total_duration_hours": 0.0,
        "total_input_tokens": 0, "total_output_tokens": 0,
        "tool_counts": {}, "tool_category_counts": {}, "languages": {},
        "git_commits": 0, "git_pushes": 0, "projects": {},
        "goal_categories": {}, "outcomes": {}, "satisfaction": {},
        "helpfulness": {}, "session_types": {}, "friction": {}, "success": {},
        "session_summaries": [],
        "total_interruptions": 0, "total_tool_errors": 0, "tool_error_categories": {},
        "median_response_time": 0, "avg_response_time": 0,
        "sessions_using_task_agent": 0, "sessions_using_mcp": 0,
        "sessions_using_web_search": 0, "sessions_using_web_fetch": 0,
        "total_lines_added": 0, "total_lines_removed": 0, "total_files_modified": 0,
        "days_active": 0, "messages_per_day": 0, "message_hours": [],
        "models": {}, "reasoning_effort": {},
        "thinking_turns": 0, "thinking_total": 0,
    }
    dates, rts = [], []
    for m in metas:
        dates.append(m["start_time"])
        r["total_messages"] += m["user_message_count"]
        r["total_duration_hours"] += m.get("active_minutes", m["duration_minutes"]) / 60
        r["total_input_tokens"] += m["input_tokens"]
        r["total_output_tokens"] += m["output_tokens"]
        r["git_commits"] += m["git_commits"]
        r["git_pushes"] += m["git_pushes"]
        r["total_interruptions"] += m["user_interruptions"]
        r["total_tool_errors"] += m["tool_errors"]
        r["total_lines_added"] += m["lines_added"]
        r["total_lines_removed"] += m["lines_removed"]
        r["total_files_modified"] += m["files_modified"]
        rts.extend(m["user_response_times"])
        r["message_hours"].extend(m["message_hours"])
        for d, key in ((m["tool_counts"], "tool_counts"),
                       (m.get("tool_category_counts") or {}, "tool_category_counts"),
                       (m["languages"], "languages"),
                       (m["tool_error_categories"], "tool_error_categories"),
                       (m.get("models") or {}, "models"),
                       (m.get("reasoning_effort") or {}, "reasoning_effort")):
            for k, v in d.items():
                bump(r[key], k, v)
        r["thinking_turns"] += m.get("thinking_turns") or 0
        r["thinking_total"] += m.get("thinking_total") or 0
        for flag, key in (("uses_task_agent", "sessions_using_task_agent"),
                          ("uses_mcp", "sessions_using_mcp"),
                          ("uses_web_search", "sessions_using_web_search"),
                          ("uses_web_fetch", "sessions_using_web_fetch")):
            if m.get(flag):
                r[key] += 1
        if m["project_path"]:
            bump(r["projects"], project_label(m["project_path"]))
        f = facets_by_key.get((m["agent"], m["session_id"]))
        if f:
            r["sessions_with_facets"] += 1
            for k, v in (f.get("goal_categories") or {}).items():
                if v > 0:
                    bump(r["goal_categories"], k, v)
            bump(r["outcomes"], f.get("outcome"))
            for k, v in (f.get("user_satisfaction_counts") or {}).items():
                if v > 0:
                    bump(r["satisfaction"], k, v)
            bump(r["helpfulness"], f.get("agent_helpfulness") or f.get("claude_helpfulness"))
            bump(r["session_types"], f.get("session_type"))
            for k, v in (f.get("friction_counts") or {}).items():
                if v > 0:
                    bump(r["friction"], k, v)
            ps = f.get("primary_success")
            if ps and ps != "none":
                bump(r["success"], ps)
        if len(r["session_summaries"]) < MAX_SUMMARIES:
            sm, se = m.get("models") or {}, m.get("reasoning_effort") or {}
            r["session_summaries"].append({
                "agent": m["agent"], "id": m["session_id"][:8],
                "date": m["start_time"][:10],
                "model": max(sm, key=sm.get) if sm else None,
                "effort": max(se, key=se.get) if se else None,
                "active_minutes": m.get("active_minutes"),
                "summary": (f.get("brief_summary") if f else None) or m.get("summary")
                           or m["first_prompt"][:100],
                "goal": f.get("underlying_goal") if f else None,
            })
    dates.sort()
    if dates:
        r["date_range"] = {"start": dates[0][:10], "end": dates[-1][:10]}
    if rts:
        srt = sorted(rts)
        r["median_response_time"] = srt[len(srt) // 2]
        r["avg_response_time"] = round(sum(rts) / len(rts), 1)
    r["response_times"] = rts
    days = {d[:10] for d in dates}
    r["days_active"] = len(days)
    r["messages_per_day"] = round(r["total_messages"] / len(days), 1) if days else 0
    r["total_duration_hours"] = round(r["total_duration_hours"], 1)
    return r


# ---------------------------------------------------------------------------
# 跨工具关联分析
# ---------------------------------------------------------------------------

def detect_overlap(metas):
    """滑动窗口并行检测（s1→s2→s1），区分同工具并行与跨工具并行。"""
    msgs = []
    for m in metas:
        for t in m["user_message_timestamps"]:
            dt = parse_iso(t)
            if dt:
                msgs.append((dt.timestamp() * 1000, m["session_id"], m["agent"]))
    msgs.sort()
    pairs, cross_pairs = set(), set()
    last_idx = {}
    win_start = 0
    for i, (ts, sid, agent) in enumerate(msgs):
        while win_start < i and ts - msgs[win_start][0] > OVERLAP_WINDOW_MS:
            if last_idx.get(msgs[win_start][1]) == win_start:
                del last_idx[msgs[win_start][1]]
            win_start += 1
        prev = last_idx.get(sid)
        if prev is not None:
            for j in range(prev + 1, i):
                jts, jsid, jagent = msgs[j]
                if jsid != sid:
                    pair = tuple(sorted((sid, jsid)))
                    pairs.add(pair)
                    if jagent != agent:
                        cross_pairs.add(pair)
                    break
        last_idx[sid] = i
    sessions_involved = {s for p in pairs for s in p}
    return {
        "overlap_events": len(pairs),
        "sessions_involved": len(sessions_involved),
        "cross_tool_overlap_events": len(cross_pairs),
        "cross_tool_sessions_involved": len({s for p in cross_pairs for s in p}),
    }


def detect_handoffs(metas):
    """同项目内，工具 A 会话结束后 HANDOFF_WINDOW_MIN 分钟内工具 B 会话开始 → 接力事件。"""
    by_project = {}
    for m in metas:
        p = normalize_project(m["project_path"])
        if p:
            by_project.setdefault(p, []).append(m)
    handoffs, direction = [], {}
    for p, group in by_project.items():
        if len({m["agent"] for m in group}) < 2:
            continue
        group.sort(key=lambda m: m["start_time"])
        for i, a in enumerate(group):
            a_end = parse_iso(a.get("end_time") or a["start_time"])
            if not a_end:
                continue
            for b in group[i + 1:]:
                b_start = parse_iso(b["start_time"])
                if not b_start:
                    continue
                gap_min = (b_start - a_end).total_seconds() / 60
                if gap_min > HANDOFF_WINDOW_MIN:
                    break
                if b["agent"] != a["agent"] and -5 <= gap_min:
                    key = f"{a['agent']} -> {b['agent']}"
                    bump(direction, key)
                    if len(handoffs) < 30:
                        handoffs.append({
                            "project": project_label(p), "direction": key,
                            "gap_minutes": round(gap_min, 1),
                            "from_session": {"agent": a["agent"], "id": a["session_id"][:8],
                                             "first_prompt": a["first_prompt"][:150]},
                            "to_session": {"agent": b["agent"], "id": b["session_id"][:8],
                                           "first_prompt": b["first_prompt"][:150]},
                        })
                    break  # 每个 a 只配最近的一个跨工具 b
    return {"direction_counts": direction, "examples": handoffs}


def project_tool_matrix(metas):
    mat = {}
    for m in metas:
        if not m["project_path"]:
            continue
        lbl = project_label(m["project_path"])
        mat.setdefault(lbl, {}).setdefault(m["agent"], 0)
        mat[lbl][m["agent"]] += 1
    # 只保留有一定量级的项目，按总会话排序
    rows = sorted(mat.items(), key=lambda kv: -sum(kv[1].values()))
    return {k: v for k, v in rows[:25]}


# ---------------------------------------------------------------------------
# LLM 上下文构建
# ---------------------------------------------------------------------------

def top(d, n):
    return dict(sorted(d.items(), key=lambda kv: -kv[1])[:n])


def build_context(agg, facets):
    c = agg["combined"]
    lines = ["# Usage data for insight generation", "",
             "## Combined stats (all agents)", "```json"]
    lines.append(json.dumps({
        "agents_present": list(agg["by_agent"].keys()),
        "sessions": c["total_sessions"], "analyzed_with_facets": c["sessions_with_facets"],
        "date_range": c["date_range"], "user_messages": c["total_messages"],
        "hours": c["total_duration_hours"], "days_active": c["days_active"],
        "git_commits": c["git_commits"], "lines_added": c["total_lines_added"],
        "lines_removed": c["total_lines_removed"],
        "interruptions": c["total_interruptions"], "tool_errors": c["total_tool_errors"],
        "median_response_time_sec": c["median_response_time"],
        "top_tool_categories": top(c["tool_category_counts"], 8),
        "top_goals": top(c["goal_categories"], 8),
        "outcomes": c["outcomes"], "satisfaction": c["satisfaction"],
        "friction": c["friction"], "success": c["success"],
        "languages": top(c["languages"], 8), "top_projects": top(c["projects"], 10),
    }, ensure_ascii=False, indent=1))
    lines.append("```")

    lines.append("\n## Per-agent comparison\n```json")
    per = {}
    for agent, a in agg["by_agent"].items():
        per[agent] = {
            "sessions": a["total_sessions"], "hours": a["total_duration_hours"],
            "user_messages": a["total_messages"], "git_commits": a["git_commits"],
            "models_by_turns": top(a["models"], 8),
            "reasoning_effort_by_turns": a["reasoning_effort"],
            "thinking_block_ratio": (round(a["thinking_turns"] / a["thinking_total"], 2)
                                     if a["thinking_total"] else None),
            "top_tools": top(a["tool_counts"], 8),
            "tool_categories": top(a["tool_category_counts"], 8),
            "top_goals": top(a["goal_categories"], 6),
            "outcomes": a["outcomes"], "satisfaction": a["satisfaction"],
            "friction": top(a["friction"], 8),
            "tool_errors": a["total_tool_errors"], "interruptions": a["total_interruptions"],
            "median_response_time_sec": a["median_response_time"],
            "top_projects": top(a["projects"], 8),
            "message_hours_histogram": {str(h): a["message_hours"].count(h)
                                        for h in sorted(set(a["message_hours"]))},
        }
    lines.append(json.dumps(per, ensure_ascii=False, indent=1))
    lines.append("```")

    x = agg["cross_tool"]
    lines.append("\n## Cross-tool signals\n```json")
    lines.append(json.dumps({
        "concurrent_multitasking": x["overlap"],
        "same_project_handoffs": x["handoffs"]["direction_counts"],
        "handoff_examples": x["handoffs"]["examples"][:12],
        "project_tool_matrix": x["project_tool_matrix"],
    }, ensure_ascii=False, indent=1))
    lines.append("```")

    lines.append("\n## Context notes（解读数据前必读）")
    w = agg.get("window") or {}
    if w.get("days"):
        lines.append(f"- 本报告是**阶段性窗口报告**：只覆盖最近 {w['days']} 天（{w.get('cutoff')} 之后）的会话，"
                     "统计与语义同窗。叙事请立足'这个阶段'，不要写成全历史总结。")
    lines.append("- 跨工具混用的常见动因是**成本控制**而非单纯能力偏好：Codex 走官方模型，"
                 "Claude Code 可方便地接入低成本第三方/国产模型（看 models_by_turns 即可判断是否如此——"
                 "若出现 kimi/deepseek/glm 等模型名，说明用户在用国产模型跑可控任务）。评价分工时请基于这一动因。")
    lines.append("- reasoning_effort 仅 Codex 提供（low/medium/high/xhigh，按轮次计）；"
                 "thinking_block_ratio 是 Claude 侧带思考块的轮次占比，是推理深度的近似信号。")
    lines.append("- Session summaries 每行带 [agent|model|effort|active_min] 标签：请结合任务内容评估"
                 "**任务-模型/推理强度匹配度**——重点找两类错配：简单任务用了过高推理强度（浪费时间），"
                 "复杂任务用了弱模型或过低强度（返工风险）。")
    n_internal = agg.get("internal_sessions_excluded") or 0
    if n_internal:
        b = agg.get("internal_breakdown") or {}
        lines.append(f"- 已排除 {n_internal} 个**内部会话**（spawn_agent 子代理 {b.get('subagent', 0)} 个、"
                     f"自动评审 {b.get('auto_review', 0)} 个）：它们不是用户发起的交互，"
                     "所有统计均只反映用户主会话。但'大量使用子代理/自动评审'本身是值得在叙事中提及的工作方式信号。")

    lines.append("\n## Session summaries")
    for s in c["session_summaries"]:
        f = next((fc for fc in facets if fc.get("session_id", "").startswith(s["id"])), None)
        suffix = f" ({f['outcome']}, {f.get('agent_helpfulness') or f.get('claude_helpfulness')})" if f else ""
        tag = "|".join(str(x) for x in (s["agent"], s.get("model"), s.get("effort"),
                                        f"{s.get('active_minutes')}min") if x and x != "None")
        lines.append(f"- [{tag}] {s['date']}: {s['summary']}{suffix}")

    fr = [f for f in facets if f.get("friction_detail")][:MAX_FRICTION]
    lines.append("\n## Friction details")
    lines.extend(f"- [{f.get('agent', '?')}] {f['friction_detail']}" for f in fr) if fr else lines.append("- None captured")

    instr = []
    for f in facets:
        for i in f.get("user_instructions_to_agent") or f.get("user_instructions_to_claude") or []:
            instr.append(f"- [{f.get('agent', '?')}] {i}")
    lines.append("\n## Repeated user instructions to agents")
    lines.extend(instr[:MAX_INSTRUCTIONS] if instr else ["- None captured"])
    return "\n".join(lines)


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--home", default=os.path.expanduser("~/.agent-insights"))
    ap.add_argument("--days", type=int, default=30, help="报告窗口：最近 N 天（0=全历史），统计与语义同窗")
    args = ap.parse_args()
    home = args.home

    metas = []
    for agent in ("claude-code", "codex"):
        metas.extend(load_dir(os.path.join(home, "cache/meta", agent)))
    # 窗口过滤：统计与语义使用同一时间窗，保证报告叙事口径一致
    cutoff_iso = ""
    if args.days > 0:
        cutoff_iso = (datetime.now(timezone.utc) - timedelta(days=args.days)) \
            .isoformat().replace("+00:00", "Z")
        metas = [m for m in metas if m["start_time"] >= cutoff_iso]
    facets_raw = []
    for agent in ("claude-code", "codex"):
        for f in load_dir(os.path.join(home, "cache/facets", agent)):
            if valid_facet(f):
                f.setdefault("agent", agent)
                facets_raw.append(f)

    facets_by_key = {(f["agent"], f["session_id"]): f for f in facets_raw if f.get("session_id")}

    # substantive + warmup + 内部会话过滤
    def is_minimal(m):
        f = facets_by_key.get((m["agent"], m["session_id"]))
        if not f:
            return False
        cats = [k for k, v in (f.get("goal_categories") or {}).items() if v > 0]
        return cats == ["warmup_minimal"]

    # 内部会话（spawn_agent 子会话 / 纯自动评审）单独计数后排除：
    # 它们不是用户发起的交互，会虚高会话数、low 档位占比和"并行多开"信号
    internal = [m for m in metas if m.get("is_internal")]
    metas = [m for m in metas
             if not m.get("is_internal")
             and m["user_message_count"] >= 2 and m["duration_minutes"] >= 1
             and not is_minimal(m)]
    # 分支/重复去重（同 agent+session_id 保留人类消息最多者）
    best = {}
    for m in metas:
        k = (m["agent"], m["session_id"])
        e = best.get(k)
        if not e or (m["user_message_count"], m["duration_minutes"]) > (e["user_message_count"], e["duration_minutes"]):
            best[k] = m
    metas = sorted(best.values(), key=lambda m: m["start_time"], reverse=True)
    used_facets = [facets_by_key[k] for k in ((m["agent"], m["session_id"]) for m in metas)
                   if k in facets_by_key]

    agg = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window": {"days": args.days, "cutoff": cutoff_iso[:10] if cutoff_iso else None},
        "internal_sessions_excluded": len(internal),
        "internal_breakdown": {
            "subagent": sum(1 for m in internal if m.get("thread_source") == "subagent"),
            "auto_review": sum(1 for m in internal if m.get("thread_source") != "subagent"),
        },
        "combined": aggregate_group(metas, facets_by_key),
        "by_agent": {agent: aggregate_group([m for m in metas if m["agent"] == agent], facets_by_key)
                     for agent in sorted({m["agent"] for m in metas})},
        "cross_tool": {
            "overlap": detect_overlap(metas),
            "handoffs": detect_handoffs(metas),
            "project_tool_matrix": project_tool_matrix(metas),
        },
    }

    os.makedirs(os.path.join(home, "work"), exist_ok=True)
    out = os.path.join(home, "work/aggregated.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(agg, fh, ensure_ascii=False, indent=1)
    ctx = build_context(agg, used_facets)
    ctx_path = os.path.join(home, "work/insight-context.md")
    with open(ctx_path, "w", encoding="utf-8") as fh:
        fh.write(ctx)

    print(json.dumps({
        "sessions_after_filter": len(metas),
        "internal_sessions_excluded": len(internal),
        "by_agent": {a: g["total_sessions"] for a, g in agg["by_agent"].items()},
        "facets_used": len(used_facets),
        "cross_tool_overlap_events": agg["cross_tool"]["overlap"]["cross_tool_overlap_events"],
        "handoff_direction_counts": agg["cross_tool"]["handoffs"]["direction_counts"],
        "aggregated": out, "insight_context": ctx_path,
        "context_chars": len(ctx),
    }, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    sys.exit(main())
