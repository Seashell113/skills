#!/usr/bin/env python3
"""collect.py — 扫描 Claude Code / Codex 本地会话，计算统一 SessionMeta 并缓存。

确定性计算层（不调用任何 LLM）：
  1. 适配器解析各工具原生 JSONL → 统一事件流（user / assistant_text / tool_use / tool_result / interrupt / tokens）
  2. compute_meta() 在统一事件流上计算 SessionMeta（与 Claude Code /insights 源码逻辑对齐）
  3. 为待提取 facet 的会话生成格式化 transcript，输出 pending_facets.json 供 LLM 层消费

用法:
  python3 collect.py [--home ~/.agent-insights] [--days N] [--max-load 200]
                     [--max-facets 40] [--claude-dir ~/.claude] [--codex-dir ~/.codex]

输出（写入 --home 目录）:
  cache/meta/{agent}/{session_id}.json     SessionMeta 缓存（按源文件 mtime 失效）
  cache/facets/{agent}/{session_id}.json   facet 缓存（由 LLM 层写入，本脚本只读）
  transcripts/{agent}/{session_id}.txt     待提取 facet 的格式化 transcript
  work/pending_facets.json                 待提取清单
  work/collect-summary.json                本次采集摘要（同时打印到 stdout）
"""

import argparse
import difflib
import json
import os
import re
import sys
from datetime import datetime, timezone

SCHEMA_VERSION = 5
INTERRUPT_MARKER = "[Request interrupted by user"
# Claude Code 把 /command 的本地执行记录也写成 user 消息，不是人类输入
CLAUDE_NOISE_RE = re.compile(
    r"^\s*<(command-name|command-message|command-args|local-command-stdout|"
    r"local-command-caveat|system-reminder)\b|^\s*Caveat: [Tt]he messages below")
TRANSCRIPT_CAP = 120_000  # 字符；超过则头 80k + 尾 40k 截断（divergence：源码用 LLM 分块摘要）
TRANSCRIPT_HEAD = 80_000
TRANSCRIPT_TAIL = 40_000

EXTENSION_TO_LANGUAGE = {
    ".ts": "TypeScript", ".tsx": "TypeScript", ".js": "JavaScript", ".jsx": "JavaScript",
    ".py": "Python", ".rb": "Ruby", ".go": "Go", ".rs": "Rust", ".java": "Java",
    ".md": "Markdown", ".json": "JSON", ".yaml": "YAML", ".yml": "YAML",
    ".sh": "Shell", ".css": "CSS", ".html": "HTML",
}

# 跨工具归一化：工具名 → 行为类别，用于跨工具对比
CLAUDE_TOOL_CATEGORY = {
    "Bash": "shell", "BashOutput": "shell", "KillShell": "shell",
    "Read": "read", "Edit": "edit", "Write": "edit", "MultiEdit": "edit", "NotebookEdit": "edit",
    "Grep": "search", "Glob": "search", "LS": "search",
    "WebSearch": "web", "WebFetch": "web",
    "Task": "agent", "Agent": "agent", "Workflow": "agent",
    "TodoWrite": "plan", "TaskCreate": "plan", "TaskUpdate": "plan", "ExitPlanMode": "plan",
    "Skill": "skill",
}
CODEX_TOOL_CATEGORY = {
    "exec_command": "shell", "shell": "shell", "local_shell": "shell",
    "write_stdin": "shell", "read_thread_terminal": "shell",
    "apply_patch": "edit", "view_image": "read",
    "web_search": "web", "update_plan": "plan",
    "spawn_agent": "agent", "wait_agent": "agent", "close_agent": "agent",
    "click": "browser", "navigate_page": "browser", "take_screenshot": "browser",
    "take_snapshot": "browser", "list_pages": "browser", "new_page": "browser",
    "evaluate_script": "browser", "list_console_messages": "browser",
    "list_network_requests": "browser", "type_text": "browser", "press_key": "browser",
    "resize_page": "browser", "set_value": "browser", "js": "browser",
}

ERROR_RULES = [  # (子串列表, 分类) — 与源码一致，顺序敏感
    (["exit code"], "Command Failed"),
    (["rejected", "doesn't want"], "User Rejected"),
    (["string to replace not found", "no changes"], "Edit Failed"),
    (["modified since read"], "File Changed"),
    (["exceeds maximum", "too large"], "File Too Large"),
    (["file not found", "does not exist"], "File Not Found"),
]


def classify_error(text):
    low = (text or "").lower()
    for needles, cat in ERROR_RULES:
        if any(n in low for n in needles):
            return cat
    return "Other"


def lang_of(path):
    _, ext = os.path.splitext(path or "")
    return EXTENSION_TO_LANGUAGE.get(ext.lower())


def parse_ts(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


# ============================================================================
# 统一事件流: 每个事件 {kind, ts(datetime|None), ...}
#   user: text         assistant_text: text       tool_use: tool, input(dict)
#   tool_result: is_error, error_text             interrupt: -
#   tokens: tokens_in, tokens_out
# ============================================================================

class ParsedSession:
    def __init__(self, agent, session_id, project_path, events, start, end,
                 summary=None, source=None):
        self.agent = agent
        self.session_id = session_id
        self.project_path = project_path
        self.events = events
        self.start = start
        self.end = end
        self.summary = summary
        self.source = source  # codex: vscode / Codex Desktop / cli


# ---------------------------- Claude Code 适配器 ----------------------------

def claude_scan(claude_dir):
    projects = os.path.join(claude_dir, "projects")
    out = []
    if not os.path.isdir(projects):
        return out
    for d in os.listdir(projects):
        pdir = os.path.join(projects, d)
        if not os.path.isdir(pdir):
            continue
        for f in os.listdir(pdir):
            if f.endswith(".jsonl"):
                p = os.path.join(pdir, f)
                try:
                    st = os.stat(p)
                except OSError:
                    continue
                out.append({"agent": "claude-code", "session_id": f[:-6],
                            "path": p, "mtime": st.st_mtime, "size": st.st_size})
    return out


def _claude_best_branch(entries):
    """分支去重：从 leaf 回溯 parentUuid 链，保留人类消息最多的分支（平手取时长更长），与源码一致。"""
    by_uuid, referenced = {}, set()
    for e in entries:
        u = e.get("uuid")
        if u:
            by_uuid[u] = e
        if e.get("parentUuid"):
            referenced.add(e["parentUuid"])
    leaves = [e for e in entries if e.get("uuid") and e["uuid"] not in referenced]
    if not leaves:
        return entries

    def chain_of(leaf):
        chain, cur, seen = [], leaf, set()
        while cur is not None:
            u = cur.get("uuid")
            if u in seen:
                break
            seen.add(u)
            chain.append(cur)
            cur = by_uuid.get(cur.get("parentUuid"))
        chain.reverse()
        return chain

    def is_human(e):
        if e.get("type") != "user" or not isinstance(e.get("message"), dict):
            return False
        c = e["message"].get("content")
        if isinstance(c, str) and c.strip():
            return True
        if isinstance(c, list):
            return any(isinstance(b, dict) and b.get("type") == "text" for b in c)
        return False

    def span(ch):
        ts = [parse_ts(e.get("timestamp")) for e in ch]
        ts = [t for t in ts if t]
        return (max(ts) - min(ts)).total_seconds() if len(ts) >= 2 else 0

    best, best_key = None, None
    for leaf in leaves:
        ch = chain_of(leaf)
        key = (sum(1 for e in ch if is_human(e)), span(ch))
        if best is None or key > best_key:
            best, best_key = ch, key
    return best


def claude_parse(path, session_id):
    entries, summary = [], None
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            t = o.get("type")
            if t == "summary":
                summary = o.get("summary") or summary
            elif t in ("user", "assistant", "system"):
                entries.append(o)
    if not entries:
        return None

    # 元会话过滤：facet 提取自身的 API 调用也会被记成会话，需排除（与源码一致）
    seen_user = 0
    for e in entries:
        if e.get("type") == "user" and isinstance(e.get("message"), dict):
            c = e["message"].get("content")
            if isinstance(c, str):
                if "RESPOND WITH ONLY A VALID JSON OBJECT" in c or "record_facets" in c:
                    return None
            seen_user += 1
            if seen_user >= 5:
                break

    chain = _claude_best_branch(entries)
    project_path = next((e.get("cwd") for e in chain if e.get("cwd")), "")
    events = []
    for e in chain:
        ts = parse_ts(e.get("timestamp"))
        msg = e.get("message")
        if not isinstance(msg, dict):
            continue
        content = msg.get("content")
        if e.get("type") == "assistant":
            usage = msg.get("usage") or {}
            if usage.get("input_tokens") or usage.get("output_tokens"):
                events.append({"kind": "tokens", "ts": ts,
                               "tokens_in": usage.get("input_tokens") or 0,
                               "tokens_out": usage.get("output_tokens") or 0})
            # 模型与深思信号：实际响应的模型（接国产模型时记录的是真实模型名）
            model = msg.get("model")
            has_thinking = isinstance(content, list) and any(
                isinstance(b, dict) and b.get("type") == "thinking" for b in content)
            if model and model != "<synthetic>":
                events.append({"kind": "turn", "ts": ts, "model": model,
                               "effort": None, "thinking": has_thinking})
            if isinstance(content, list):
                for b in content:
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "text" and b.get("text"):
                        events.append({"kind": "assistant_text", "ts": ts, "text": b["text"]})
                    elif b.get("type") == "tool_use" and b.get("name"):
                        events.append({"kind": "tool_use", "ts": ts, "tool": b["name"],
                                       "input": b.get("input") if isinstance(b.get("input"), dict) else {}})
        elif e.get("type") == "user":
            texts = []
            if isinstance(content, str) and content.strip():
                texts.append(content)
            elif isinstance(content, list):
                for b in content:
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "text" and b.get("text"):
                        texts.append(b["text"])
                    elif b.get("type") == "tool_result":
                        rc = b.get("content")
                        rc_text = rc if isinstance(rc, str) else json.dumps(rc, ensure_ascii=False)[:500] if rc else ""
                        events.append({"kind": "tool_result", "ts": ts,
                                       "is_error": bool(b.get("is_error")),
                                       "error_text": rc_text if b.get("is_error") else ""})
            for txt in texts:
                if INTERRUPT_MARKER in txt:
                    events.append({"kind": "interrupt", "ts": ts})
                if CLAUDE_NOISE_RE.match(txt):
                    continue  # /command 本地记录、注入提醒：不算人类消息
                events.append({"kind": "user", "ts": ts, "text": txt})

    tss = [ev["ts"] for ev in events if ev["ts"]]
    if not tss:
        return None
    return ParsedSession("claude-code", session_id, project_path, events,
                         min(tss), max(tss), summary=summary)


# ------------------------------- Codex 适配器 -------------------------------

CODEX_FILE_RE = re.compile(r"rollout-.*-([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.jsonl$")
EXIT_CODE_RE = re.compile(r"exited with code (\d+)")
PATCH_FILE_RE = re.compile(r"^\*\*\* (Add|Update|Delete) File: (.+)$", re.MULTILINE)
CODEX_WRAPPER_RE = re.compile(r"^<(environment_context|user_instructions|permissions|turn_context)", re.IGNORECASE)


def codex_scan(codex_dir):
    root = os.path.join(codex_dir, "sessions")
    out = []
    if not os.path.isdir(root):
        return out
    for dirpath, _dirnames, filenames in os.walk(root):
        for f in filenames:
            m = CODEX_FILE_RE.search(f)
            if not m:
                continue
            p = os.path.join(dirpath, f)
            try:
                st = os.stat(p)
            except OSError:
                continue
            out.append({"agent": "codex", "session_id": m.group(1),
                        "path": p, "mtime": st.st_mtime, "size": st.st_size})
    return out


def _codex_patch_stats(patch_text, events, ts):
    """解析 apply_patch 的 patch 文本 → 文件/语言/增删行，折算为统一 tool_use 事件的 input。"""
    files = [m.group(2).strip() for m in PATCH_FILE_RE.finditer(patch_text or "")]
    added = removed = 0
    for line in (patch_text or "").splitlines():
        if line.startswith("+") and not line.startswith("+++") and not line.startswith("*** "):
            added += 1
        elif line.startswith("-") and not line.startswith("---") and not line.startswith("*** "):
            removed += 1
    events.append({"kind": "tool_use", "ts": ts, "tool": "apply_patch",
                   "input": {"_files": files, "_added": added, "_removed": removed}})


def codex_parse(path, session_id):
    events, project_path, source = [], "", None
    start = None
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            t, p = o.get("type"), o.get("payload") or {}
            ts = parse_ts(o.get("timestamp"))
            if t == "session_meta":
                # resume 会追加新的 session_meta，start/cwd 以第一条为准
                project_path = project_path or p.get("cwd") or ""
                source = source or p.get("originator") or p.get("source")
                start = start or ts
            elif t == "turn_context":
                project_path = project_path or p.get("cwd") or ""
                # 模型与推理强度（low/medium/high/xhigh），每轮记录一次
                if p.get("model") or p.get("effort"):
                    events.append({"kind": "turn", "ts": ts, "model": p.get("model"),
                                   "effort": p.get("effort"), "thinking": None})
            elif t == "event_msg":
                pt = p.get("type")
                if pt == "user_message":
                    txt = p.get("message") or ""
                    if txt.strip() and not CODEX_WRAPPER_RE.match(txt.strip()):
                        events.append({"kind": "user", "ts": ts, "text": txt})
                elif pt == "token_count":
                    info = p.get("info") or {}
                    last = info.get("last_token_usage") or {}
                    if last:
                        # 对齐 Claude 口径：input 不含缓存读取
                        tin = max(0, (last.get("input_tokens") or 0) - (last.get("cached_input_tokens") or 0))
                        events.append({"kind": "tokens", "ts": ts, "tokens_in": tin,
                                       "tokens_out": last.get("output_tokens") or 0})
                elif pt == "turn_aborted" and p.get("reason") == "interrupted":
                    events.append({"kind": "interrupt", "ts": ts})
                elif pt == "web_search_end":
                    events.append({"kind": "tool_use", "ts": ts, "tool": "web_search", "input": {}})
            elif t == "response_item":
                pt = p.get("type")
                if pt == "message" and p.get("role") == "assistant":
                    txt = " ".join(b.get("text", "") for b in p.get("content") or []
                                   if isinstance(b, dict) and b.get("type") == "output_text")
                    if txt.strip():
                        events.append({"kind": "assistant_text", "ts": ts, "text": txt})
                elif pt == "function_call":
                    name = p.get("name") or "unknown"
                    try:
                        args = json.loads(p.get("arguments") or "{}")
                        if not isinstance(args, dict):
                            args = {}
                    except (json.JSONDecodeError, TypeError):
                        args = {}
                    if name == "apply_patch":
                        _codex_patch_stats(args.get("input") or args.get("patch") or "", events, ts)
                    else:
                        events.append({"kind": "tool_use", "ts": ts, "tool": name, "input": args})
                elif pt == "custom_tool_call":
                    name = p.get("name") or "unknown"
                    if name == "apply_patch":
                        _codex_patch_stats(p.get("input") or "", events, ts)
                    else:
                        events.append({"kind": "tool_use", "ts": ts, "tool": name, "input": {}})
                elif pt == "function_call_output":
                    out_text = p.get("output") or ""
                    m = EXIT_CODE_RE.search(out_text if isinstance(out_text, str) else "")
                    is_err = bool(m and m.group(1) != "0")
                    events.append({"kind": "tool_result", "ts": ts, "is_error": is_err,
                                   "error_text": ("exit code " + m.group(1) + " " + out_text[:300]) if is_err else ""})
    tss = [ev["ts"] for ev in events if ev["ts"]]
    if not tss:
        return None
    return ParsedSession("codex", session_id, project_path, events,
                         start or min(tss), max(tss), source=source)


# ============================================================================
# SessionMeta 计算（与 /insights 源码 extractToolStats / logToSessionMeta 对齐）
# ============================================================================

def compute_meta(s: ParsedSession, src_mtime):
    tool_counts, languages, error_cats = {}, {}, {}
    category_counts = {}
    git_commits = git_pushes = tokens_in = tokens_out = 0
    interruptions = tool_errors = 0
    lines_added = lines_removed = 0
    files_modified = set()
    response_times, message_hours, user_ts = [], [], []
    uses = {"task_agent": False, "mcp": False, "web_search": False, "web_fetch": False}
    user_count = assistant_count = 0
    models, efforts = {}, {}
    thinking_turns = thinking_total = 0
    first_prompt = ""
    cat_map = CLAUDE_TOOL_CATEGORY if s.agent == "claude-code" else CODEX_TOOL_CATEGORY
    last_assistant_ts = None

    for ev in s.events:
        k, ts = ev["kind"], ev["ts"]
        if k == "tokens":
            tokens_in += ev["tokens_in"]
            tokens_out += ev["tokens_out"]
        elif k == "assistant_text":
            assistant_count += 1
            if ts:
                last_assistant_ts = ts
        elif k == "tool_use":
            if ts:
                last_assistant_ts = ts
            name = ev["tool"]
            tool_counts[name] = tool_counts.get(name, 0) + 1
            cat = "mcp" if name.startswith("mcp__") else cat_map.get(name, "other")
            category_counts[cat] = category_counts.get(cat, 0) + 1
            if name in ("Task", "Agent", "spawn_agent"):
                uses["task_agent"] = True
            if name.startswith("mcp__"):
                uses["mcp"] = True
            if name in ("WebSearch", "web_search"):
                uses["web_search"] = True
            if name == "WebFetch":
                uses["web_fetch"] = True
            inp = ev.get("input") or {}
            fp = inp.get("file_path") or ""
            if fp:
                lg = lang_of(fp)
                if lg:
                    languages[lg] = languages.get(lg, 0) + 1
                if name in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
                    files_modified.add(fp)
            if name == "Edit":
                old = (inp.get("old_string") or "").splitlines()
                new = (inp.get("new_string") or "").splitlines()
                sm = difflib.SequenceMatcher(None, old, new, autojunk=False)
                for tag, i1, i2, j1, j2 in sm.get_opcodes():
                    if tag in ("replace", "delete"):
                        lines_removed += i2 - i1
                    if tag in ("replace", "insert"):
                        lines_added += j2 - j1
            if name == "Write":
                c = inp.get("content") or ""
                if c:
                    lines_added += c.count("\n") + 1
            if name == "apply_patch":
                for f in inp.get("_files") or []:
                    files_modified.add(f)
                    lg = lang_of(f)
                    if lg:
                        languages[lg] = languages.get(lg, 0) + 1
                lines_added += inp.get("_added") or 0
                lines_removed += inp.get("_removed") or 0
            cmd = inp.get("command") or inp.get("cmd") or ""
            if isinstance(cmd, list):
                cmd = " ".join(str(x) for x in cmd)
            if "git commit" in cmd:
                git_commits += 1
            if "git push" in cmd:
                git_pushes += 1
        elif k == "tool_result":
            if ev.get("is_error"):
                tool_errors += 1
                cat = classify_error(ev.get("error_text"))
                error_cats[cat] = error_cats.get(cat, 0) + 1
        elif k == "interrupt":
            interruptions += 1
        elif k == "turn":
            if ev.get("model"):
                models[ev["model"]] = models.get(ev["model"], 0) + 1
            if ev.get("effort"):
                efforts[ev["effort"]] = efforts.get(ev["effort"], 0) + 1
            if ev.get("thinking") is not None:
                thinking_total += 1
                if ev["thinking"]:
                    thinking_turns += 1
        elif k == "user":
            user_count += 1
            if not first_prompt:
                first_prompt = ev["text"].strip()[:200]
            if ts:
                local = ts.astimezone()
                message_hours.append(local.hour)
                user_ts.append(iso(ts))
                if last_assistant_ts:
                    rt = (ts - last_assistant_ts).total_seconds()
                    if 2 < rt < 3600:
                        response_times.append(round(rt, 1))

    duration_min = round((s.end - s.start).total_seconds() / 60)
    # 活跃时长：事件间隔求和，单段 gap 封顶 15 分钟。跨天/跨周 resume 的会话
    # 用首尾跨度会严重虚高（一个会话挂一周 = 168h），聚合统计应使用本值。
    all_ts = sorted(ev["ts"] for ev in s.events if ev["ts"])
    active_sec = sum(min((b - a).total_seconds(), 900)
                     for a, b in zip(all_ts, all_ts[1:]))
    active_min = round(active_sec / 60)
    return {
        "schema_version": SCHEMA_VERSION,
        "agent": s.agent,
        "session_id": s.session_id,
        "source": s.source,
        "project_path": s.project_path,
        "start_time": iso(s.start),
        "end_time": iso(s.end),
        "duration_minutes": duration_min,
        "active_minutes": active_min,
        "user_message_count": user_count,
        "assistant_message_count": assistant_count,
        "tool_counts": tool_counts,
        "tool_category_counts": category_counts,
        "languages": languages,
        "git_commits": git_commits,
        "git_pushes": git_pushes,
        "input_tokens": tokens_in,
        "output_tokens": tokens_out,
        "first_prompt": first_prompt,
        "summary": s.summary,
        "user_interruptions": interruptions,
        "user_response_times": response_times,
        "tool_errors": tool_errors,
        "tool_error_categories": error_cats,
        "uses_task_agent": uses["task_agent"],
        "uses_mcp": uses["mcp"],
        "uses_web_search": uses["web_search"],
        "uses_web_fetch": uses["web_fetch"],
        "lines_added": lines_added,
        "lines_removed": lines_removed,
        "files_modified": len(files_modified),
        "message_hours": message_hours,
        "user_message_timestamps": user_ts,
        "models": models,                    # 模型名 → 轮次（Claude 为 assistant 消息数）
        "reasoning_effort": efforts,         # 仅 Codex：low/medium/high/xhigh → 轮次
        "thinking_turns": thinking_turns,    # 仅 Claude：含 thinking 块的轮次
        "thinking_total": thinking_total,
        "src_mtime": src_mtime,
    }


def format_transcript(s: ParsedSession, meta):
    lines = [
        f"Agent: {s.agent}",
        f"Session: {s.session_id[:8]}",
        f"Date: {meta['start_time']}",
        f"Project: {meta['project_path']}",
        f"Duration: {meta['duration_minutes']} min",
        "",
    ]
    for ev in s.events:
        if ev["kind"] == "user":
            lines.append(f"[User]: {ev['text'][:500]}")
        elif ev["kind"] == "assistant_text":
            lines.append(f"[Assistant]: {ev['text'][:300]}")
        elif ev["kind"] == "tool_use":
            lines.append(f"[Tool: {ev['tool']}]")
        elif ev["kind"] == "interrupt":
            lines.append("[User interrupted the agent]")
    text = "\n".join(lines)
    if len(text) > TRANSCRIPT_CAP:
        text = (text[:TRANSCRIPT_HEAD]
                + "\n\n[... middle of long session truncated ...]\n\n"
                + text[-TRANSCRIPT_TAIL:])
    return text


# ============================================================================
# 主流程
# ============================================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--home", default=os.path.expanduser("~/.agent-insights"))
    ap.add_argument("--claude-dir", default=os.environ.get("CLAUDE_CONFIG_DIR", os.path.expanduser("~/.claude")))
    ap.add_argument("--codex-dir", default=os.path.expanduser("~/.codex"))
    ap.add_argument("--days", type=int, default=0, help="只分析最近 N 天（0=全部）")
    ap.add_argument("--max-load", type=int, default=200, help="单次最多解析的未缓存会话数")
    ap.add_argument("--max-facets", type=int, default=40, help="单次最多生成的 facet 待提取数")
    args = ap.parse_args()

    home = args.home
    for sub in ("cache/meta/claude-code", "cache/meta/codex",
                "cache/facets/claude-code", "cache/facets/codex",
                "transcripts/claude-code", "transcripts/codex", "work"):
        os.makedirs(os.path.join(home, sub), exist_ok=True)

    scanned = claude_scan(args.claude_dir) + codex_scan(args.codex_dir)
    if args.days > 0:
        cutoff = datetime.now().timestamp() - args.days * 86400
        scanned = [s for s in scanned if s["mtime"] >= cutoff]
    scanned.sort(key=lambda x: -x["mtime"])

    metas, parsed_cache = [], {}
    loaded = skipped_cache = failed = 0
    for info in scanned:
        meta_path = os.path.join(home, "cache/meta", info["agent"], info["session_id"] + ".json")
        cached = None
        if os.path.exists(meta_path):
            try:
                with open(meta_path, encoding="utf-8") as fh:
                    cached = json.load(fh)
                if (cached.get("schema_version") != SCHEMA_VERSION
                        or cached.get("src_mtime") != info["mtime"]):
                    cached = None  # 源文件有更新或 schema 升级 → 重算
            except (json.JSONDecodeError, OSError):
                cached = None
        if cached:
            metas.append(cached)
            skipped_cache += 1
            continue
        if loaded >= args.max_load:
            continue
        loaded += 1
        try:
            parse = claude_parse if info["agent"] == "claude-code" else codex_parse
            s = parse(info["path"], info["session_id"])
        except (OSError, UnicodeDecodeError):
            s = None
        if s is None:
            failed += 1
            continue
        meta = compute_meta(s, info["mtime"])
        with open(meta_path, "w", encoding="utf-8") as fh:
            json.dump(meta, fh, ensure_ascii=False, indent=1)
        os.chmod(meta_path, 0o600)
        metas.append(meta)
        parsed_cache[(info["agent"], info["session_id"])] = s

    # substantive 过滤（≥2 条人类消息、≥1 分钟）后挑选待提取 facet 的会话（新→旧）
    substantive = [m for m in metas if m["user_message_count"] >= 2 and m["duration_minutes"] >= 1]
    substantive.sort(key=lambda m: m["start_time"], reverse=True)
    pending = []
    for m in substantive:
        if len(pending) >= args.max_facets:
            break
        facet_path = os.path.join(home, "cache/facets", m["agent"], m["session_id"] + ".json")
        if os.path.exists(facet_path):
            continue
        key = (m["agent"], m["session_id"])
        s = parsed_cache.get(key)
        if s is None:
            src = next((i for i in scanned if (i["agent"], i["session_id"]) == key), None)
            if not src:
                continue
            try:
                parse = claude_parse if m["agent"] == "claude-code" else codex_parse
                s = parse(src["path"], m["session_id"])
            except (OSError, UnicodeDecodeError):
                s = None
            if s is None:
                continue
        tpath = os.path.join(home, "transcripts", m["agent"], m["session_id"] + ".txt")
        with open(tpath, "w", encoding="utf-8") as fh:
            fh.write(format_transcript(s, m))
        os.chmod(tpath, 0o600)
        pending.append({"agent": m["agent"], "session_id": m["session_id"],
                        "transcript_path": tpath, "facet_path": facet_path,
                        "chars": os.path.getsize(tpath)})

    with open(os.path.join(home, "work/pending_facets.json"), "w", encoding="utf-8") as fh:
        json.dump(pending, fh, ensure_ascii=False, indent=1)

    by_agent = {}
    for m in metas:
        by_agent[m["agent"]] = by_agent.get(m["agent"], 0) + 1
    summary = {
        "home": home,
        "scanned_files": len(scanned),
        "metas_total": len(metas),
        "metas_by_agent": by_agent,
        "from_cache": skipped_cache,
        "parsed_now": loaded - failed,
        "parse_failed_or_meta": failed,
        "substantive": len(substantive),
        "pending_facets": len(pending),
        "pending_facets_file": os.path.join(home, "work/pending_facets.json"),
        "note_remaining_uncached": max(0, len(scanned) - skipped_cache - loaded),
    }
    with open(os.path.join(home, "work/collect-summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    sys.exit(main())
