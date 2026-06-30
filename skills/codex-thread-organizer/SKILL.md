---
name: codex-thread-organizer
description: |-
  Organize Codex threads for long-running or split workflows. Use when the user asks to rename Codex sessions/threads, apply a thread naming convention, close out the current thread, produce a short thread summary, create or update handoff prompts, build an index of related threads, identify historical/test/archive candidates, or says phrases like "按命名规则收口这个会话", "整理最近会话标题", "整理团队skills最近PKM会话", "给这组会话生成索引", or "检查哪些会话该归档". Do not use for code changes, repository documentation, or project knowledge management unless the task is specifically about Codex thread organization.
---

# Codex Thread Organizer

Organize Codex threads so related work remains easy to scan and recover after the user intentionally splits one topic across many sessions.

## Core Rules

- Keep titles useful in the left sidebar: show the category first, then the main work.
- Use square-bracket prefixes for fast visual grouping.
- Do not repeat the project name when the thread already appears under that project group.
- Keep the object name when the thread is a cross-project analysis inside another project group.
- Prefer a preview before batch renaming. Rename directly only when the user explicitly asks to do so or the current request already confirms the naming rule and target set.
- Do not archive, pin, create, fork, or message threads unless the user explicitly asks or confirms a proposed action.
- Do not use subagents for thread organization.

## Naming Patterns

Use these patterns:

```text
[CategoryNN] Main work
[Category] Main work
[Category测试] Test purpose
[Category安装] Install or consistency check
[索引] Topic
```

Examples:

```text
[PKM06] 轻框架收敛
[PKM测试] 隔离验证
[PKM安装] 一致性核对
[Subagent02] 定位与成本校准
[SDD01] sdd-partner首版实现
[索引] 团队skills
```

Choose the category from the user's domain language, such as `PKM`, `Subagent`, `SDD`, `Review`, `Wiki`, `周报`, or another short label already used in the thread set.

Use numbering for a continuous mainline where ordering matters. Do not force numbering for tests, installs, one-off checks, or side investigations.

## Single-Thread Closeout

When the user asks to close out or maintain the current thread:

1. Inspect the current thread context if thread tools are available.
2. Propose or set a title using the naming patterns.
3. Produce a summary in five lines or fewer:
   - topic
   - completed work
   - key decisions or evidence
   - remaining follow-up
   - next entry point
4. Produce a concise handoff prompt when the work should continue in a new thread.
5. State whether archiving is recommended. Do not archive without confirmation.

## Batch Organization

When the user asks to organize multiple threads:

1. Search threads by project, keyword, category, and likely aliases.
2. Use thread title, cwd/project, preview, and recent summaries before reading deeper history.
3. Build a table with current title, reason, and proposed title.
4. Apply changes only after confirmation, unless the user asked to directly change them.
5. Report which threads were changed and which were skipped.

Skip threads when they are unrelated, ambiguous, active production work, or cannot be confidently classified from available evidence.

## Index Threads

When the user asks for an index:

1. Prefer one index per large topic or project group.
2. Use a title like `[索引] 团队skills`.
3. Include only durable navigation information:
   - mainline thread range
   - side/test/install threads
   - current latest entry point
   - open follow-ups
   - archived/history notes
4. Keep the index compact enough to read quickly. Avoid copying full summaries from every thread.

## Automation Guidance

If the user asks for automation:

- Prefer a scheduled scan that produces rename/archive suggestions.
- Do not create an automation that directly renames or archives threads unless the user explicitly asks for that risk.
- Suggested output: nonconforming titles, proposed titles, likely historical threads, archive candidates, and uncertain items needing review.

## Output Style

- Use Chinese by default.
- Be concise and operational.
- For batch changes, list the final titles and note any intentional exclusions.
- When relying on uncertain thread evidence, say what was inspected and keep the recommendation provisional.
