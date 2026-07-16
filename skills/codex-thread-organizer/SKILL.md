---
name: codex-thread-organizer
description: |-
  Organize Codex threads for long-running or split workflows. Use whenever the user asks to rename or close out Codex sessions/threads, scan recent or all visible threads, audit title quality, renumber a related thread family, produce a short summary or handoff prompt, build an index, or identify test/install/automation/archive candidates. Treat commands and phrases such as "codex-thread-organizer:init", "scan", "scan all", "audit 5", "renumber 对象或类别", "确认应用", "先重命名本会话", "按命名规则收口", "整理最近会话标题", and "codex-threads" as explicit entrypoints. Do not use for code changes, repository documentation, or project knowledge management unless the task is specifically about Codex thread organization.
---

# Codex Thread Organizer

Organize Codex threads so the user can recover related work quickly without reading full transcripts. A good title answers: `这个会话最终值得因为什么被找回来？`

## Safety And Authority

- Use host-provided thread tools. Do not write `state_5.sqlite` or another local Codex database as the normal path.
- Normal organization runs in the current thread; do not use subagents.
- Preview batch changes before applying them. Rename directly only when the user explicitly asks or has already confirmed the target set and naming rule.
- Do not archive, pin, create, fork, hand off, or message threads without explicit user authority for that action.
- Treat Automation, scheduled brief, auto-review, system, approval, and other host-managed threads as `skip` unless the user explicitly includes them.
- A request such as `确认应用` or `都改掉` never includes `needs-review`. Apply uncertain items only when the user names them or explicitly accepts that risk.

## Command Interface

Treat the prefixed and short forms below as equivalent when the intent is unambiguous:

| Command | Behavior |
| --- | --- |
| `codex-thread-organizer:init` | Initialize the current thread as a long-lived naming manager; do not scan yet. |
| `scan` / `codex-thread-organizer:scan` | Inspect the 10 most recent visible threads and preview only items that need action. |
| `scan all` | Inspect all threads visible through the host, in bounded batches when needed. |
| `audit N` | Sample and conditionally read `N` threads to estimate title accuracy and identify failure patterns; do not rename. |
| `renumber <对象或类别>` | Preview relation and numbering changes only for the named family; do not apply them. |
| `codex-thread-organizer:rename` | Rename only the current or explicitly identified thread. |
| `codex-thread-organizer:handoff` | Produce only the continuation package. |
| `codex-thread-organizer:closeout` | Recompute the closeout title, give a five-line summary, and add a handoff when unfinished work remains. |
| `确认应用` | Apply only high-confidence `rename` rows from the latest preview. |
| `都改掉` | Apply all previewed `rename` rows, still excluding `needs-review`. |

For command-style calls, report the result with concise Chinese labels and omit irrelevant fields:

```text
命令：
线程工具：
扫描范围：
元数据：
补读：
未读范围：
重命名：
跳过：
待复核：
交接：
缺失证据：
```

## Scan Algorithm

Follow these passes in order. Do not jump from readable metadata directly to the final table.

1. **List** the exact requested range and keep every item in scope.
2. **Normalize** each durable object across aliases, casing, repository names, CLI names, and Skill names.
3. **Flag individual anomalies**: low-information/prompt titles, missing useful prefixes, lifecycle verbs, preview conflict, persistent roles, and protected items.
4. **Build families** across the complete range using canonical object + work context + handoff/version/artifact/first-goal evidence. Include individually clear members.
5. **Read evidence** for every anomaly and every member needed by a family decision. Interpret `newest_first`, then reduce to evidence cards that separate the durable task identity from the latest interaction.
6. **Resolve individual decisions and family decisions together**. Topic/category describes each member; relation/number describes the family. `duplicate` is a relation role, not a category value.
7. **Close the ledger**: a multi-member family must end as a complete sequence, proven independent roles, or affected members in `needs-review`. No family member may disappear into the bulk skip count while relation is unresolved.
8. **Render** every action row with the required columns and report preview counts separately from changes actually applied.

If one newest-three-turn read explicitly points to a missing closeout, origin, or handoff that blocks the family decision, request at most one additional bounded cursor page for that thread with `includeOutputs:false` and `turnLimit:3`. Stop after that page and use `needs-review` if still unresolved.

## Title Semantics

### Lifecycle

Titles have three useful lifecycle states:

1. **Initial title**: derive it from the first real task while work is starting.
2. **Current title**: update it only after a clear task pivot. Do not react to routine messages such as `继续`、`跑测试`、`再看看`.
3. **Closeout title**: recompute it from the stable task identity, actual artifact, and final durable stage.

Keep stages only when they improve retrieval. `设计收敛`、`实现发布`、`复验收口` and `验证阻塞` are useful; `已完成`、`进行中` and `继续` usually are not.

Mark `title_drift=true` when the current title's object, category, or stage conflicts with the latest stable result. A move from design into implementation, release, regression, or a durable blocker is a likely drift signal; a minor execution step is not.

Do not equate a readable title with an aligned title. Compare the verb and stage against the work that actually happened:

- `升级`、`搭建`、`完善` or `推进` can overstate execution when the thread only assessed, designed, or clarified the work;
- `设计`、`需求` or `实现中` can become stale after implementation, merge, release, regression, or a durable handoff;
- `建立 ... 入口` should become `[索引] ...` when the durable result is a long-lived capture or management entrypoint.

Use the stable main task for the title. A late one-off note, message delivery, or minor follow-up does not replace the durable identity of a completed release or implementation thread.

Treat post-completion requests such as `把状态发给另一个线程`、`组织交接`、`还有待办吗` or `记录一条改进建议` as continuation evidence. They do not turn a thread that owns implementation, MR, version, test, or release artifacts into a handoff/sidecar thread. A true sidecar only reviews, verifies, reports, or delivers another thread's result and does not own the durable implementation result.

### Prefix Priority

The square-bracket prefix is the most stable retrieval and relation axis. Choose it in this order:

1. A durable work object that may continue evolving: `[web-ai-daily-paper] 设计收敛`.
2. A repository-wide or cross-object governance category: `[Skills] 发布流程统一`.
3. A horizontal work type when the type is more useful than one object: `[SDD测试] 标签页拖拽验证`, `[工具安装] 钉钉CLI`.
4. An index role: `[索引] 线程命名管理器`.

Do not add the current project name merely because the thread is listed under that project. Inside the Skills project, prefer `[web-ai-daily-paper] ...` over `[Skills] ...` when one skill is the durable object. Keep an object name when a thread analyzes it from another project.

The current cwd/project leaf is grouping context, not a default object prefix. Inside `admin-mes`, use `[PKM] 知识入口初始化` for project-level knowledge work rather than `[admin-mes] ...`; inside `saas-frontend`, keep a clear `[Review] API调整` instead of replacing it with `[saas-frontend] ...`. Use the project/object name only when the thread is cross-project or the surrounding project group does not already supply it.

Use these structural forms:

```text
[ObjectNN] Distinct stage or result
[Object] Distinct stage or result
[Category测试] Test purpose
[Category安装] Install or consistency check
[索引] Topic
```

Use an object/category/index prefix when the thread represents a durable object, recurring role, or workstream that may have siblings or later phases. An unprefixed title may pass only for a self-contained one-off whose object and action are already unambiguous and whose relation to other threads is confidently irrelevant. For example, `查找某部门通讯录` may remain unprefixed; `审阅某个持续演进的 Skill` should use that Skill as its prefix.

The body after the prefix is usually 8–20 Chinese characters or an equivalent concise length. Treat this as a readability guide, never as a mechanical truncation rule for object names.

## Adaptive Evidence Protocol

The goal is to maximize decision quality per unit of thread content, not to deeply read everything.

### Layer 1: Metadata Scan

For `scan`, call the thread list once with `limit: 10`. For `scan all`, honor the host's visible range and caps; use bounded query/category batches if one list call cannot cover it, and state the actual range rather than claiming completeness.

Use only these fields for the first pass:

- thread id and host id;
- current title and preview/initial task summary;
- cwd/project;
- created and updated time;
- current status.

Classify every candidate from `title + preview + cwd` first, then perform a scan-wide cluster pass before declaring any non-protected item clear. Candidate clusters include:

- the same durable object in the same project/work context;
- explicit `继续`、`交接`、`剩余任务` or source/target language;
- successive versions, releases, branches, changes, or shared artifact paths;
- identical or near-identical first goals that may be a fork, delegated execution, or duplicate;
- repeated persistent roles such as multiple `[索引] 线程命名管理器` threads.

Individual readability does not prove `skip`. A title passes only after the lifecycle and cluster checks also pass.

Normalize obvious aliases and casing before clustering, such as a product name, repository name, CLI name, and Skill name referring to the same durable object. A family can therefore contain differently written titles when cwd, handoff, versions, artifacts, or first goals connect them. Do not limit clustering to literal title similarity.

### Layer 2: Conditional Read

Read a thread only when at least one anomaly remains:

- the title is empty or low-information, such as `如何处理`、`继续`、`看看`、`搞一下`;
- the title contains a full prompt, Markdown link, local Skill path, or obviously excessive text;
- title and preview disagree about the object or action;
- the work may have moved from design to implementation, release, regression, or a blocker;
- an execution verb may overstate work that is still assessment, design, or clarification;
- a persistent entrypoint or manager role is expressed as a one-time creation task;
- a continuous relation or number is being decided;
- the same project has duplicate or highly similar titles;
- metadata identifies the topic but not the category or relation.

Treat a mainline title centered on `设计`、`升级`、`搭建`、`推进`、`完善`、`重构`、`实现` or `发布` as a lifecycle checkpoint, not as self-validating prose. Read it when the preview describes a different stage, when `updated_at` shows meaningful continuation beyond the opening task, or when related threads suggest a later release/handoff. If the preview itself says `考虑`、`评估`、`是否`、`先设计` or similar language while the title asserts execution, metadata is already enough to flag drift.

Use bounded reads only:

```text
read_thread({
  threadId,
  hostId,
  includeOutputs: false,
  turnLimit: 3
})
```

- Never request tool or command outputs for naming work.
- Read only the latest 2–3 relevant turns. Do not page into older history unless the current evidence explicitly points to a missing handoff or origin turn.
- When several threads need evidence and the host supports parallel calls, issue the bounded reads together.
- When relation or numbering is in scope, read every candidate member needed to establish the family and order, including members whose individual titles already look clear. Reading only the visibly bad duplicate cannot establish a sequence.
- Do not impose a tiny total-read target. In an anomaly-heavy scan, several bounded reads are correct; efficiency comes from bounding each read and skipping genuinely clear items, not from suppressing anomalies.
- Treat the host response as `newest_first`. Use turn timestamps/status to identify the newest completed evidence; do not assume the last array element is latest. A newer completed implementation, release, real run, merge, or handoff overrides the initial preview and older design discussion.
- Do not paste, quote, or carry the raw `read_thread` response or full prose into working notes or the final response. Immediately reduce each read to a 500–1000 character evidence card containing only: `latest_evidence_at`, `latest_user_intent`, `stable_result`, `artifact_or_branch`, and `continuation_evidence`.
- Build the evidence card from newest to oldest. Use older turns only to recover origin/continuation; never let an older initial task overwrite a newer stable result.
- In the card, `latest_user_intent` describes the newest interaction while `stable_result` describes what the thread durably owns. If the newest interaction is only status delivery, handoff, or note-taking, keep the owned implementation/release as `stable_result`.
- Never invoke an unbounded read as a shortcut. If the bounded read is insufficient, exit to `needs-review`.

### Layer 3: Exit

After the bounded read, stop when any title-critical decision remains unstable. Mark the item `needs-review` and state the missing evidence. Coverage is secondary to avoiding a wrong high-confidence rename.

Before finalizing a scan, run this closure check over the complete metadata set:

1. Every lifecycle-checkpoint title is either supported by current evidence or listed as `rename`/`needs-review`.
2. Every candidate family with at least two members has an explicit relation and numbering disposition for every member; no member is silently skipped because its individual title looks good. If two same-object mainline candidates share a work context and relation is not confidently irrelevant, both must appear in the family card and cannot be finalized with `relation_group=null`.
3. Every repeated persistent index/manager role is either proven to have a distinct scope or the older idle entry is listed as `archive-candidate`.
4. Every `rename` row has high T/C/R/N confidence. If relation or numbering is irrelevant, record it as high-confidence not-applicable with `relation_group=null`; do not leave medium confidence on a rename row.
5. Reject a proposed prefix equal to the cwd/project leaf unless the thread is explicitly cross-project or that project name is itself the durable object missing from the sidebar context.
6. Reconcile counts before answering: `bounded-read unique + metadata-only unique = scope`, protected items are a subset of metadata-only/skip items, and preview/action/skip totals must classify the complete scope exactly once.

If any closure item cannot be completed from bounded evidence, use `needs-review`; do not finish with a generic bulk skip claim.

## Separate The Decisions

Evaluate these fields independently before choosing an action:

1. **Topic**: the durable object being worked on.
2. **Category**: mainline, test, install, review, regression, temporary validation, Automation, or system.
3. **Relation**: which threads form one evolution chain.
4. **Number**: whether that chain needs numbering and its order.
5. **Title drift**: whether the existing title is stale or conflicts with the stable result.

Use only these category values: `mainline`, `test`, `install`, `review`, `regression`, `temporary-validation`, `automation`, `system`, or `unknown`. Lifecycle words such as `design` and `release` belong in the title body or drift analysis, not in the category field.

`handoff`、`requirements` and `duplicate` are relation roles or lifecycle evidence, not category values. Keep the category in the allowed enum and record those roles in the evidence/family card.

Record `high`, `medium`, or `low` for topic, category, relation, and number:

- `high`: a direct user statement or at least two independent, non-conflicting signals.
- `medium`: one strong signal or several weak signals, with no direct contradiction.
- `low`: missing evidence, conflicting signals, or reliance on project/category similarity alone.

Relation and number confidence are `high` when a one-off is confidently unrelated and non-numbered, as well as when a sequence is proven. `high` can therefore mean “confidently not applicable.” This prevents an obvious install/test/review task from becoming `needs-review` merely because it has no family. Use `relation_group=null` for that case.

Choose exactly one action:

- `rename`: every decision that affects the proposed title is high confidence.
- `skip`: the title has passed retrieval-axis, lifecycle, duplicate, relation, and numbering checks, or the thread is a protected Automation/system item. “标题能看懂” alone is not a valid skip reason.
- `needs-review`: any decision that can change the title remains medium/low after bounded evidence. A low relation signal does not block an otherwise clear non-numbered one-off when relation is confidently irrelevant.
- `archive-candidate`: the evidence supports a suggestion, but never archive automatically.

## Relation And Numbering

Relation evidence can include same cwd/project, same durable object, Skill/change/spec path, consistent first goal, explicit `继续`/`交接`/`剩余任务` language, shared artifact/branch/worktree, and time adjacency. Category or project equality alone never proves relation.

Version succession plus an explicit handoff or shared artifact is strong evolution evidence. Consecutive released versions for the same object and cwd/work context provide strong order evidence even when each phase has a different immediate goal. A well-titled earlier release remains a member of the family and must be included in the numbering preview.

Conversely, a forked/delegated thread with the same first goal may be a parallel execution role rather than the next chronological phase. Keep such a duplicate out of the numbered sequence until its role is high confidence. Use `archive-candidate` only when bounded evidence shows its durable result was absorbed elsewhere; otherwise use `needs-review`.

For each candidate family, create a compact family card before deciding actions:

```text
canonical_object | work_context | members | handoff/version/artifact evidence | role per member | order | numbering decision
```

The family card is internal and must contain all visible members in scope. A newer release member does not make an earlier release member disappear; when the evolution is sequential, preview the whole numbered family.

If the family card contains two or more same-object mainline members in the same work context, choose one of only three outcomes:

1. high-confidence sequence: assign one `relation_group` and preview the complete numbering family;
2. high-confidence independent roles: keep all unnumbered and state the distinct role evidence per member;
3. unresolved relation/order: mark the affected members `needs-review`.

Do not silently use a fourth outcome where one member is renamed, another clear-looking member is skipped, and the family receives no relation decision.

Use artifact ownership to distinguish mainline from sidecar:

- owning a branch/change/MR, implementation, regression suite, version, or release is mainline evidence even when the last turn is a handoff;
- only reviewing, validating, summarizing, or forwarding another thread's artifacts is sidecar evidence;
- if the bounded read shows both but ownership is unclear, use the one extra bounded page or exit to `needs-review` instead of confidently labeling a sidecar.

Set a non-null `relation_group` only when continuity itself is high confidence. Same object + same cwd + nearby time is useful candidate evidence, but without an explicit handoff, shared artifact/branch/worktree, or matching first goal it does not establish a chain.

Define a numbering family by `stable object or category + project/work context`. Do not connect similarly named threads across projects without explicit shared-work evidence.

- Tests, installs, reviews, regressions, temporary checks, and one-off work default to no number.
- For an established mainline, parse matching `[ObjectNN]` titles, take the highest number, and use `highest + 1`; do not fill gaps.
- During a batch preview, an unnumbered group may become a new sequence when at least two mainline threads have high relation confidence. Preview the complete family from `01`, ordered by explicit handoff first, then shared artifact chronology, then timestamps.
- Judge and preview the family as a unit. Do not renumber one member while silently leaving other high-confidence members unnumbered.
- Do not create a new numbering family during a single-thread rename from one candidate alone.
- `renumber <对象或类别>` limits analysis to that family and previews old title, relation evidence, order evidence, and new title. Apply only after confirmation.
- If order depends on timestamps alone or crosses project boundaries, use `needs-review`.

## Title Quality Gate

Before proposing `rename`, detect:

- empty or low-information titles;
- a complete prompt used as the title;
- Markdown links or local Skill paths;
- obviously excessive length;
- duplicate titles within one project;
- object/action conflict with the evidence card;
- a stale lifecycle stage;
- an execution verb that overstates an assessment or design-only result;
- a durable object or recurring role missing its useful object/category/index prefix;
- a persistent entrypoint still titled as a one-time creation action;
- multiple threads serving the same index/manager role;
- repeated project/category information.

A readable title still fails the gate when its prefix uses the project/category even though one durable object is explicit. For example, `[Skills] web-ai-daily-paper回归样例` must become an object-prefixed title; do not `skip` it merely because the body is understandable.

Apply that rule only to a durable sub-object, not to the current project itself. A clear type/category title such as `[Review] API调整` passes when its cwd already supplies the project and its preview confirms review work.

Do not use the cwd leaf as a convenience prefix. For a project-local migration assessment, prefer a durable object/type such as `[Vue3迁移] 方案评估` over repeating `[current-project] ...`. When the repository leaf is also the durable object, prefer its established short product/category alias for the title family, such as `[Tool01]`, rather than copying the full cwd leaf.

After applying changes, list the final titles and verify the targeted thread ids. For a renumber operation, re-list and verify the full family.

## Scan, Audit, And Apply Output

Internally classify every scanned item. In the user-facing preview, list only `rename`, `needs-review`, and `archive-candidate` rows; summarize clear and protected `skip` counts separately.

Use columns:

```text
thread id | current title | cwd/project | topic/category | proposed title | confidence T/C/R/N | drift | evidence | action
```

Always state:

- metadata range and count;
- bounded-read count and thread ids;
- which range/content was not read;
- protected Automation/system skip count;
- why each `needs-review` item stopped.

Keep the required columns even when the user requests a concise scan. If the user later asks for every skipped title, report the category, lifecycle alignment, and relation/duplicate reason for each one; do not repeat generic explanations such as “对象和动作明确”.

For every multi-member candidate family, add a compact `家族结论` section containing the members, relation evidence, role/order, and numbering decision. Include clear-looking members when their title would change under renumbering.

Distinguish preview from mutation in the summary, for example `重命名预览：8；实际重命名：0`. Do not report `重命名：0` when the table contains rename proposals.

For `audit N`, choose a mixed sample: clear titles, suspicious titles, and at least one protected item when available. Report sample accuracy, false-positive patterns, read count, time, and available token/tool-call evidence. Never present a small sample as proof of population-wide accuracy.

## Single Rename, Handoff, And Closeout

For `:rename`, perform only the rename and minimum evidence report. If the user says `先重命名本会话，然后继续`, handle the rename first and then continue; if they ask only for rename, stop afterward.

For `:handoff`, produce only a self-contained `交接包` with the next prompt, sources, changed files, decisions, validation, pending items, and first action. Do not rename or create a thread unless explicitly requested.

For `:closeout`:

1. Recompute the closeout title using the lifecycle and evidence rules.
2. Apply or propose it according to the user's authority.
3. Summarize topic, completed work, evidence/decision, follow-up, and next entry in five lines or fewer.
4. Add a handoff when pending or unconfirmed work remains.
5. Recommend whether to archive; do not archive without confirmation.

Generate handoff content in the source thread before creating a new one. Create a next thread only after explicit confirmation such as `新开`、`直接开` or `帮我创建`, unless the same request already gave that authority.

### Delegated Thread Protection

- Treat `source_thread_id` as provenance only, never as the rename target without explicit instruction.
- Rename a created/delegated thread only by the explicit `threadId` returned by `create_thread`.
- Before renaming it, confirm `target thread id` and `target title`.
- If the target id is missing, return a suggested title and do not rename.
- Source and target titles are separate actions and must be reported separately.

## Manager Init

For `:init`, try to rename the current thread to `[索引] 线程命名管理器`, then return this compact guide without scanning:

```text
这是常驻 Codex 线程命名管理器，只处理标题、收口、索引、归档建议和失败补救。

- scan：最近 10 个可见线程，只预览异常项。
- scan all：分批扫描全部可见线程。
- audit 5：抽样补读 5 个线程，评估标题质量。
- renumber <对象或类别>：只预览指定主线的关系和编号。
- rename / handoff / closeout：分别处理改名、交接、组合收口。
- 确认应用：只应用高置信 rename，永远跳过 needs-review。

元数据先行；异常项才限量补读；Automation/系统线程默认跳过；线程工具失败时不写本地数据库。
```

Prefer a projectless manager and pin it only when the user asks. A project-bound manager still scans across visible projects unless the user specifies the current project/cwd.

## Thread Tool Failures

Treat `No handler registered for tool: ...` as a temporary host handler failure, not a Skill trigger failure.

- Tool absent: provide suggestions, summary, and handoff only.
- Handler unavailable: retry discovery/listing once, then stop.
- Permission denied: report the blocked action; do not work around it.
- List succeeds but set fails: show the exact intended title and say it was not applied.
- Set succeeds but verification is unavailable: say the request was sent but not verified.
- Related history unavailable: do not invent a mainline number.

When tools fail, use an unnumbered temporary title only if topic and category are still high confidence, such as `[PKM] 入口语义收敛`. State the missing relation/number evidence and fix it after tools recover.

## Index And Automation Guidance

For an index, prefer one compact `[索引] Topic` thread containing mainline range, side/test/install threads, latest entry, open follow-ups, and archive notes. Do not copy full summaries.

When multiple visible threads serve the same persistent index/manager role, keep the newest active entry and mark an older idle duplicate as `archive-candidate` unless the evidence shows distinct scopes. Never archive it automatically.

Different generic projectless output directories, dates, or `new-chat` folders do not establish distinct manager scopes. Distinct scope requires topic evidence, such as separate `[索引] PKM` and `[索引] GCW` roles.

If the user asks for an automation, prefer a scheduled suggestion scan. Do not create an automation that directly renames or archives unless explicitly requested. Keep automation creation separate from organizing existing Automation/system threads.

## Output Style

- Use Chinese labels and concise operational wording by default.
- Preserve literal commands, ids, paths, titles, and code in their original form.
- Distinguish Skill trigger success, tool availability, rename request, verification, temporary titles, and missing evidence.
- When evidence is uncertain, name what was inspected and exit to `needs-review`.
