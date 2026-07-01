---
name: codex-thread-organizer
description: |-
  Organize Codex threads for long-running or split workflows. Use when the user asks to rename Codex sessions/threads, apply a thread naming convention, close out the current thread, produce a short thread summary, create or update handoff prompts, build an index of related threads, identify historical/test/archive candidates, or says phrases like "codex-thread-organizer:init", "codex-thread-organizer:scan", "codex-thread-organizer:rename", "codex-thread-organizer:handoff", "codex-thread-organizer:closeout", "先重命名本会话", "按命名规则收口这个会话", "整理最近会话标题", "整理团队skills最近PKM会话", "给这组会话生成索引", "检查哪些会话该归档", "codex-threads", or "codex-thread-namer". Do not use for code changes, repository documentation, or project knowledge management unless the task is specifically about Codex thread organization.
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
- Treat `codex-threads`, `codex-thread-namer`, `thread organizer`, `会话命名 skill`, and `线程整理 skill` as aliases for this skill when the request is about Codex thread naming or closeout.

## Command Interface

Treat short commands as explicit tool-like entrypoints. Prefer these commands over inferring intent from loose wording:

- `codex-thread-organizer:init` or `codex-thread-namer:init`: initialize the current thread as a long-lived thread naming manager.
- `codex-thread-organizer:scan` or `codex-thread-namer:scan`: scan recent or queried threads and produce a rename/archive preview only. Do not apply changes.
- `codex-thread-organizer:rename` or `codex-thread-namer:rename`: rename the current thread or a specified target thread. If no title is provided, infer one from the current task and related thread context.
- `codex-thread-organizer:handoff` or `codex-thread-namer:handoff`: produce only the next-thread handoff prompt, with enough context for continuation. Do not rename unless explicitly requested in the same command.
- `codex-thread-organizer:closeout` or `codex-thread-namer:closeout`: close out a Codex session/thread by applying the naming rules, producing the five-line summary, and producing a handoff when pending or unconfirmed items remain.

For command-style calls, report the command result directly:

```text
command:
thread tools:
scan scope:
rename:
temporary title:
handoff:
missing evidence:
```

Omit fields that do not apply. Keep the response concise.

### Manager Init

When the user invokes `:init`, initialize the current thread as the thread naming manager:

Prefer initializing this manager in a projectless/general Codex conversation, then pinning that conversation. If the current thread is project-bound, still treat the manager as cross-project by default; do not limit future scans to the current cwd unless the user says "current project" or gives an explicit cwd.

1. Try to rename the thread to `[索引] 线程命名管理器`.
2. Output the operating rules below as the pinned/long-lived usage guide.
3. Do not perform batch rename work during init unless the user explicitly asks.

Manager usage guide:

```text
这是常驻 Codex 线程命名管理器，只处理 Codex 会话/线程标题、收口、索引、归档建议和失败补救。

常用命令：
- codex-thread-organizer:rename：重命名当前线程或指定线程。
- codex-thread-organizer:scan：扫描最近或指定范围会话，只输出预览，不改名。
- codex-thread-organizer:handoff：只生成下一会话 handoff。
- codex-thread-organizer:closeout：收口当前会话，包含命名、五行摘要和必要 handoff。
- 确认应用：只应用预览中确定项，跳过不确定项。

规则：
- 批量改名前默认先预览。
- 默认跨所有可见 Codex 线程扫描；只有明确说当前项目/当前工作区时才限制到当前 cwd。
- 连续主线编号取最高编号 + 1，不填补缺号。
- 区分主线、测试、安装、回归、临时验证。
- 自动评审、审批、automation 线程默认跳过或单独标注。
- 线程工具不可用时，输出建议标题、线程 ID 和待补动作，不直接写本地数据库。
```

## Preflight Rename

When the user explicitly asks to rename before continuing, handle the title before the main task.

- If the user says "先重命名本会话，然后继续", attempt the rename first, report whether it completed, then continue the main task.
- If the user only says "先处理会话名" or "先重命名本会话", stop after the rename result unless they also ask to continue.
- If the rename cannot be completed, report the failure class, the best temporary or suggested title, and whether continuing is safe under the user's wording.
- Do not bury a rename failure inside a long task report.

For `:rename`, do only the rename operation and the minimum evidence report. Do not produce a closeout summary, handoff, archive suggestion, or batch preview unless the user asks for them.

For `:scan`, default to all visible Codex threads, filtered by any user-provided time range, project name, cwd, keyword, or category. Limit to the current cwd only when the user explicitly says "current project", "current workspace", or provides the current cwd as the scan scope. Produce a preview table only. Include thread id, current title, project/cwd, classification, reason, proposed title, confidence, and recommended action (`rename`, `skip`, `archive-candidate`, or `needs-review`). Never rename, archive, pin, create, fork, or message threads during `:scan`.

For `:handoff`, do only the continuation prompt. Include the current topic, completed state, decisions/evidence, pending or unconfirmed items, and the next recommended first action. Do not rename or archive unless explicitly requested.

Use `:closeout` when the user wants the combined operation: naming, five-line summary, necessary handoff, and archive recommendation.

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

For numbered mainlines, first search related threads in the same category and project context when thread tools are available. Parse existing titles that match `[CategoryNN] ...`, take the highest `NN`, then use `NN + 1`. Do not fill gaps. If existing titles include `[PKM00]`, `[PKM01]`, `[PKM03]`, and `[PKM08]`, the next title is `[PKM09] ...`, not `[PKM02] ...`.

## Recent Context Classification

For single-thread closeout, use recent related threads to decide whether the current thread is a mainline, test, install check, regression, or temporary validation.

Classification priority:

1. User-explicit category or naming intent.
2. Recent same-project, same-batch, or same-category thread patterns.
3. Current thread purpose and constraints.
4. Whether the current thread produced real file changes.

Do not classify a thread as a formal mainline only because it produced real file changes. If recent related threads show an isolation test, clean-state regression, multi-repo init comparison, limited-input trial, or install consistency check, prefer a test/install/regression title.

Example: if recent same-project threads include `[PKM测试] 初始化` and `[PKM测试] 隔离验证`, and the current thread says "only use the current repo", "do not read memory", or "do not read external paths", name it like `[PKM测试] 知识入口初始化` even if it wrote `README.md`, `AGENTS.md`, or `CLAUDE.md`. Use `[PKM] 知识入口初始化` only when the user frames the work as official project deposition, pre-submit organization, continuous governance mainline, or when there is no test/regression context.

## Single-Thread Closeout

When the user asks to close out or maintain the current thread:

1. Confirm the skill is handling the request, then inspect the current thread context if thread tools are available.
2. Search same-category, same-project, and same-keyword recent threads to classify the current thread as mainline, test, install, regression, or temporary validation. Compute a number only after confirming it belongs to a numbered mainline.
3. Propose or set a title using the naming patterns.
4. Produce a summary in five lines or fewer:
   - topic
   - completed work
   - key decisions or evidence
   - remaining follow-up
   - next entry point
5. Produce a concise handoff prompt when the work should continue in a new thread. If the user explicitly asks to close out a Codex session or thread and there are pending or unconfirmed items, always provide a handoff prompt.
6. State whether archiving is recommended. Do not archive without confirmation.

## Thread Tools And Failures

Treat `No handler registered for tool: ...` from visible thread tools as a temporary host/tool-handler failure, not as a naming-rule failure and not as evidence that the skill did not trigger.

Prefer host-provided thread tools for listing, reading, and renaming. Do not default to directly writing local Codex databases such as `state_5.sqlite`; use local metadata only as diagnostic evidence or for a user-approved manual recovery path.

Failure classes:

- Tool absent: the host does not expose thread management. Provide title suggestions, summary, and handoff only.
- Handler unavailable: a visible tool returns `No handler registered for tool: ...`. Retry discovery or listing once if available.
- Permission denied: report that rename is blocked by approval or permission; do not work around it silently.
- List succeeds but set fails: compute and show the exact intended title, but say it was not applied.
- Set succeeds but verification is unavailable: say the rename request was sent, but the final title could not be verified.
- Related history unavailable: do not assign a mainline number.

When a thread tool handler is unavailable:

1. Retry tool discovery or listing once if that capability is available.
2. If thread tools still fail, read `CODEX_THREAD_ID` when available to identify the current thread.
3. If related thread history cannot be read, do not invent a numbered title. Use an unnumbered temporary title such as `[PKM] 入口语义收敛` and say the number is pending until thread tools recover.
4. Report what is missing, usually the related thread set needed to compute `highest number + 1`.

If a previous closeout used an unnumbered temporary title because tools failed, and tools later recover or the user asks to fix it, search related threads again. If the current thread is part of a numbered mainline, directly apply the computed `[CategoryNN] Main work` title.

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
- For closeout, distinguish skill triggered, thread tools available, rename actually completed, whether the title is temporary, and what evidence is missing when numbering cannot be computed.
- When relying on uncertain thread evidence, say what was inspected and keep the recommendation provisional.
