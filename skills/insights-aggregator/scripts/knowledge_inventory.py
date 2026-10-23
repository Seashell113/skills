"""Render a separate evidence inventory with the report's existing stylesheet."""
import html
import json
import os
from collections import Counter
from pathlib import Path


def load_inventory(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not isinstance(data.get("scope"), dict):
        raise ValueError("inventory requires schema_version=1 and scope")
    items = data.get("items")
    if not isinstance(items, list):
        raise ValueError("inventory items must be a list")
    ids = set()
    for item in items:
        if not isinstance(item, dict) or not all(item.get(k) for k in ("id", "title", "summary", "status", "evidence")):
            raise ValueError("inventory item requires id, title, summary, status and evidence")
        if item["id"] in ids:
            raise ValueError("duplicate inventory item id")
        ids.add(item["id"])
        if not isinstance(item["evidence"], list) or any(not isinstance(e, dict) or not e.get("locator") for e in item["evidence"]):
            raise ValueError("inventory evidence requires locators")
    return data


def text(value):
    if isinstance(value, list):
        return "；".join(text(v) for v in value)
    if isinstance(value, dict):
        labels = {"cutoff": "开始", "as_of": "截至", "days": "窗口天数", "session_id": "会话",
                  "packet": "证据包", "source_lines": "原文行号", "relation": "关系", "target": "位置",
                  "note": "说明", "type": "类型", "text": "建议", "selection": "选样",
                  "in_window_messages": "窗口内可见消息", "in_window_user_messages": "用户消息",
                  "in_window_assistant_messages": "助手消息", "pre_window_context_messages": "窗口前背景消息",
                  "active_user_days": "样本用户活跃日", "upstream_reading": "复用范围", "current_review": "本轮回读",
                  "wiki_lookup": "知识核对", "commit": "固定版本", "queries": "查询词", "read_pages": "回读页面",
                  "boundary": "覆盖边界"}
        return "；".join(f"{labels.get(k, k)}：{text(v)}" for k, v in value.items() if v not in (None, "", []))
    return str(value or "")


def write_inventory(data, directory, css, report_name):
    """Emit independent HTML / Markdown / JSON; no knowledge-store mutation."""
    esc = lambda value: html.escape(text(value), quote=True)
    title = data.get("title") or "历史知识与经验盘点"
    scope = data["scope"]
    items = data["items"]
    categories = list(dict.fromkeys(i.get("category") or "未分类" for i in items))
    scope_labels = {"window": "分析窗口", "window_semantics": "窗口边界", "sessions_read": "阅读任务数",
                    "coverage": "读取覆盖", "limits": "边界"}
    scope_text = "\n\n".join(f"{scope_labels.get(k, k)}：{text(v)}" for k, v in scope.items())
    scope_summary = "；".join(f"{scope_labels.get(k, k)}：{text(scope[k])}" for k in ("window", "sessions_read") if k in scope)
    nav = '<a href="' + esc(report_name) + '">返回洞察报告</a> ' + " ".join(
        f'<a href="#category-{n}">{esc(category)}</a>' for n, category in enumerate(categories))
    markdown = [f"# {title}", "", scope_text, "", "条目为盘点结果；未自动写入长期知识，也不将候选视作已采纳。", ""]
    sections = []
    labels = [("context", "形成背景"), ("lesson", "经验与判断"), ("verification", "验证边界"), ("reuse_when", "复用条件"),
              ("existing_knowledge", "已有知识关系"), ("next_step", "后续动作")]
    for n, category in enumerate(categories):
        cards = []
        markdown += [f"## {category}", ""]
        for item in items:
            if (item.get("category") or "未分类") != category:
                continue
            references = "".join('<li>' + esc(e.get("source_id")) + ' · ' + esc(e["locator"])
                                 + ('：' + esc(e["quote_or_summary"]) if e.get("quote_or_summary") else '') + '</li>'
                                 for e in item["evidence"])
            fields = "".join(f'<p><strong>{label}：</strong>{esc(item[key])}</p>'
                             for key, label in labels if item.get(key))
            cards.append(f'<div class="narrative" style="overflow-wrap:anywhere"><p><strong>{esc(item["id"])} · {esc(item["title"])}</strong></p>'
                         f'<p>{esc(item["summary"])}</p><p><strong>状态：</strong>{esc(item["status"])}</p>'
                         f'<details><summary>背景、复用与来源</summary>{fields}<ul>{references}</ul></details></div>')
            markdown += [f'### {item["id"]} · {item["title"]}', "", item["summary"], "", f'状态：{item["status"]}', ""]
            for key, label in labels:
                if item.get(key):
                    markdown += [f"{label}：{text(item[key])}", ""]
            markdown += ["来源：", ""] + [f'- {e.get("source_id", "")} · {e["locator"]}：{e.get("quote_or_summary", "")}' for e in item["evidence"]] + [""]
        sections.append(f'<h2 id="category-{n}">{esc(category)}</h2>' + "".join(cards))
    counts = Counter(i["status"] for i in items)
    doc = ('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
           '<meta name="viewport" content="width=device-width, initial-scale=1">'
           f'<title>{esc(title)}</title><style>{css}</style></head><body><div class="container">'
           f'<h1>{esc(title)}</h1><div class="subtitle">{len(items)} 个知识点 · {len(categories)} 个领域 · 独立盘点结果</div>'
           f'<div class="nav-toc">{nav}</div><div class="narrative" style="overflow-wrap:anywhere"><p>{esc(scope_summary)}</p>'
           '<p>条目为盘点结果；未自动写入长期知识，也不将候选视作已采纳。</p>'
           f'<p>{esc("；".join(f"{k} {v} 项" for k, v in counts.items()))}</p>'
           f'<details><summary>读取覆盖与盘点边界</summary><p>{esc(scope_text)}</p></details></div>'
           + "".join(sections) + '</div></body></html>')
    payloads = {"knowledge-inventory.html": doc, "knowledge-inventory.md": "\n".join(markdown),
                "knowledge-inventory.json": json.dumps(data, ensure_ascii=False, indent=2) + "\n"}
    outputs = []
    for name, content in payloads.items():
        path = Path(directory) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        os.chmod(path, 0o600)
        outputs.append(str(path))
    return outputs
