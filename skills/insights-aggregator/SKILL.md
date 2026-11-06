---
name: insights-aggregator
description: 跨工具 AI 编程助手使用洞察分析。扫描 Claude Code 与 Codex 的本地会话记录，计算使用统计、提取语义 facets、生成跨工具对比与组合使用分析，可选提取历史业务/项目/技术/组织经验并评估 Agent、subagent、Skill、模型与工具的实际效果，输出自包含 HTML 报告与可选独立知识盘点。当用户要求"分析我的 agent 使用情况"、"生成 insights 报告"、"跨工具使用分析"、"/insights"、"claude code 和 codex 用得怎么样"、"从历史会话提取经验"、"分析 Agent 基建效果"时使用。
---

# insights-aggregator

跨工具（Claude Code + Codex）会话洞察分析。架构：**本地脚本做全部确定性计算，LLM 只做两层语义分析**（单会话 facet 提取 → 跨会话洞察生成）。逻辑对齐 Claude Code 官方 `/insights` 源码，并扩展了跨工具关联分析。

## 目录

```
scripts/collect.py        扫描+解析双工具会话 → SessionMeta 缓存 + facet 待提取清单
scripts/aggregate.py      聚合 + 跨工具关联（并行/接力/项目矩阵）→ aggregated.json + insight-context.md
scripts/render.py         沿用原模板渲染报告，可另输出知识盘点 HTML / Markdown / JSON
scripts/knowledge_inventory.py  独立知识盘点渲染与校验
prompts/facet-extraction.md    facet 提取子 agent 提示词
prompts/insight-sections.md    原 9 个洞察 section + 2 个可选 section + at_a_glance 提示词
reference/evidence-bundle.md   已准备证据复用协议（不重跑 facet）
reference/knowledge-inventory.md  知识盘点与阅读报告的分工、数据结构
reference/claude-insights-spec.md   Claude /insights 源码逻辑完整规范（背景知识，执行时不必读）
reference/codex-session-schema.md   Codex rollout JSONL 格式与字段映射表
```

数据目录默认 `~/.agent-insights/`（缓存、transcript、报告都在这里，原始会话只读不动）。

## 执行流程

### Step 0 — 与用户确认范围（开跑前）

默认分析**最近一个月**（`--days 30`）、facet 提取上限 **50 条**。开跑前向用户确认一句，并说明：调大窗口或分析数（如全历史、`--max-facets 200`）意味着更多并行子 agent 调用、更高的 LLM 开销和耗时。用户没有特殊要求就用默认值直接开始。

### 已有证据时：跳过重复抽取

用户已有选样任务材料、核验片段和统计时，先检查它们能否构成 [evidence bundle](reference/evidence-bundle.md)。通过 `aggregate.py --evidence-bundle /path/bundle.json --home /private/path/run` 进入 Step 4 / 5；无需重做昂贵 facet。复用语义材料不等于缩减统计：已有统计不足时先用 Step 1 / 3 重算窗口内确定性数据（`--max-facets 0`），再把结果并入 bundle。统计母体和直接阅读样本分别说明，不能用样本数量冒充全部使用量。使用独立 home，避免混入旧 section。范围和冻结时间以 bundle 为准，未知指标保留未知，直接阅读数与 facet 数分开记录。

### Step 1 — 采集（脚本，无 LLM）

```bash
python3 {skill_dir}/scripts/collect.py [--days 30] [--max-facets 50]
```

窗口语义为 `(since, as_of]`。按窗口内真实用户活动纳入根会话，老会话在窗口内续聊同样计入；所有消息、工具、模型、时间指标仅计窗口内事件。根会话统计包含一次用户输入的短任务，facet 另用实质会话门槛。`--since` 指定精确起点，或用 `--days` 推算；`--as-of` 固定终点。`--timezone Asia/Shanghai` 可指定日期与时段的展示时区，未指定使用本机时区；两者使用同一时区，时区变化使缓存重算。collect 与 aggregate 使用同一窗口，未显式指定时聚合沿用 collect-summary 的窗口。Codex 同时扫描 sessions、archived_sessions 和 `.jsonl.zst`；压缩文件需要本机 zstd。

读 stdout JSON：关注 `metas_by_agent`（两个工具是否都有数据）、`substantive_in_window` / `facets_already_cached` / `pending_facets`（窗口内总数 / 已有缓存 / 本次待提取）、`note_remaining_uncached`（>0 说明还有历史会话未解析 meta，可提高 `--max-load` 再跑一次）。同时检查 `codex_ownership.owner_leakage_lines`、`invalid_json_lines` 和 `result_call_link_rate`；存在非零 owner 泄漏或快照校验失败时，不继续生成洞察。

需要审计级复现时，先由调用方生成包含 `path`、`session_id`、`byte_length`、`mtime_ns`、`sha256` 和 `snapshot_id` 的私密 Codex snapshot manifest，再传入：

```bash
python3 {skill_dir}/scripts/collect.py \
  --codex-snapshot-manifest /path/to/snapshot-manifest.json \
  --since 2026-09-01T00:00:00Z --as-of 2026-10-01T00:00:00Z \
  --max-load 2000 --max-facets 0
```

采集器只读取每个 rollout 的冻结物理字节前缀并验证 SHA-256，压缩源先校验再解压；时间窗口另由事件时间裁切，物理快照不等同于时间窗口。

冻结后原 JSONL 被压缩迁移时，按[采集重放与阅读前归属校准](reference/collection-replay.md)使用 `recover_codex_snapshot.py` 生成认证映射，再给 collect 传 `--codex-recovery-map`；旧 manifest 保持不变。解压后的旧冻结前缀身份与压缩文件物理身份分别校验，不能仅替换路径后缀。

为深读制作消息包或分组任务前，先通过同一冻结源集合完成归属校准，复用上述参考中的 reader 入口。已确认的继承历史按原身份复用或按需作背景；归属待核实内容单列，不按时间戳直接当成本期新增。容量分块不是业务阶段，长会话分工后由主控串行核对后续修正与前期结论的关系。

### Step 2 — Facet 提取（并行子 agent）

读 `~/.agent-insights/work/pending_facets.json`。若为空（命中缓存或本次不提取 facet）直接跳到 Step 3。

按 `prompts/facet-extraction.md` 中的 PROMPT 模板，为每个待提取会话派发一个子 agent（替换 `{{transcript_path}}`、`{{facet_path}}`、`{{agent}}`、`{{session_id}}`、`{{user_message_count}}`、`{{parser_schema_version}}`、`{{analysis_window}}` 占位符，取值都在 pending_facets.json 里）。要点：

- **并行**派发，每批 8-10 个；子 agent 用最快可用的模型即可（提取任务不需要最强模型）。若快模型报 429/不可用，直接降级用默认模型重试，不要反复重试快模型。
- 子 agent 自己读 transcript、自己写 facet JSON 文件，主 agent 不要捧着 transcript 内容。
- 某个子 agent 失败就跳过该会话，不要重试超过 1 次——缺个别 facet 不影响整体。

### Step 3 — 聚合（脚本，无 LLM）

```bash
python3 {skill_dir}/scripts/aggregate.py [--days 30] [--as-of 2026-08-27T13:56:10.186054+00:00]
```

`--since` / `--days` 和 `--as-of` 必须与 Step 1 的实际窗口一致；默认沿用 collect-summary 的冻结窗口。`--days 0` 为截至 as_of 的全历史。不同窗口的 meta / facet 不混算；聚合报告会给出不匹配与过期缓存数量。读 stdout：`facets_used`、`stale_codex_facets_ignored`、`cross_tool_overlap_events`、`handoff_direction_counts`。无效的 facet 文件会被忽略；若 `facets_used` 明显小于已提取数，检查 facet JSON 格式和解析版本。

### Step 4 — 洞察生成（并行子 agent + 1 个串行）

先确定本期值得分析的工具范围。检出记录不等于有足够使用样本；用户已说明近期停用某工具，或仅有零星、无实质任务的残留记录时，简短说明后聚焦实际使用的工具，跳过少样本工具分析和跨工具对比。仅凭数量少不能断言完全没用过；结合任务内容及用户说明判断，不设通用数量阈值。完整采集结果保留，报告统计、图表和叙事使用同一分析范围；已有聚合数据可按 [bundle 协议](reference/evidence-bundle.md) 生成单工具输入，无需重跑抽取。

按 `prompts/insight-sections.md`：

1. 9 个 section 并行派发（单工具数据则跳过 `tool_comparison`、`cross_tool_workflows`，剩 7 个）。每个子 agent 读 `work/insight-context.md`，写 `work/insights/{section}.json`。此层用**较强的模型**（叙事质量敏感）。
2. 用户要求历史知识提取/基建效果分析，或本轮复盘材料确有可复用经验或基建效果问题时，按同一提示词追加 `knowledge_findings` 与 `infrastructure_effectiveness` 两个可选 section；保留原 7/9 个使用洞察。读取 Skill/规则、实际执行、结果与采纳状态分别记录，证据不足写未知。facet 的头尾摘要、短 prefix 不能代表完整会话；关键结论缺链时按已授权 session_id / locator 有界下钻相关原文，记录实际读取范围与未覆盖部分，不默认扩大全历史抽取。
3. 用户要求知识与经验盘点时，按 [独立知识盘点](reference/knowledge-inventory.md) 输出 `knowledge-inventory.json`。按知识点和任务阶段拆条，不受阅读报告卡片数量约束；注明长会话实际读取范围。报告只保留少量有启发的精选，不把全盘点塞进正文。
4. 全部完成后，串行生成 `at_a_glance`（上下文 = insight-context.md + 各 section 产出要点）。

主控通读整篇，检查各节是否提供不同的信息、建议是否仍值得做，以及结论是否有具体结果支撑。按用户的读者与表达偏好修订，保留有用细节，合并重复案例和方法说明；不以压缩篇幅代替洞察质量。

### Step 5 — 渲染与交付

```bash
python3 {skill_dir}/scripts/render.py --knowledge-inventory /private/path/knowledge-inventory.json
# 未要求知识盘点时省略 --knowledge-inventory
```

保持现有 CSS、导航、卡片和图表组件；内容扩展不同时重设计页面。核对统计母体、语义样本、未知项及来源，再在浏览器检查可读性与链接。

然后：
1. 展示生成的报告及独立知识盘点入口；
2. 在对话里给用户一段 At a Glance 中文摘要（What's working / What's hindering / 工具分工 / Quick wins / Ambitious workflows 各 1-2 句）+ 报告路径；
3. 问用户是否要深入某个 section 或采纳某条配置建议。

## 增量与缓存

- SessionMeta 按 `(agent, session_id)` 缓存并记录 `analysis_window`；不同窗口重算，不复用全生命周期指标。源文件的 mtime、mtime_ns、size、snapshot id 或 SHA-256 变化时自动重算。
- facet 按 `(agent, session_id)` 缓存。会话 resume 后大幅续写（消息 +5 条以上，依据 `_user_message_count` 戳）会重提；Codex 的 `_parser_schema_version` 缺失或不同也会重新排队，避免格式修复后继续使用漏读用户消息的旧结论。Claude facet 不因 Codex 解析升级而失效；两种工具的 facet 均需匹配 `_analysis_window`。旧无窗口戳的 facet 仅在原会话完整首尾均落在窗口内时兼容复用。
- 解析升级后的首次正常采集可能重算 meta，并在已授权窗口及 `--max-facets` 上限内重提 Codex facet；采集器只生成待提取清单，不自行调用模型或覆盖旧 facet。当前 SessionMeta schema 为 15。
- 聚合时也校验 Codex facet 的解析版本；过期语义不参与摘要、结果统计或 warmup 排除，当前有效 meta 统计仍保留。提取失败或数量上限截断时同样生效，不删除旧文件、不扩大重算范围；`stale_codex_facets_ignored` 表示本次保留的根会话中跳过旧语义的数量。
- 同窗口重复运行可复用缓存；不同窗口不把旧语义直接当作当前窗口结果。已有可靠分析也可通过 evidence bundle 复用，单独声明分析范围。强制全量重提：删 `~/.agent-insights/cache/facets/`。

统计母体由本次 collect 的有效身份清单固定；相同窗口更换 manifest 或解析失败时，旧缓存保留但不混入聚合。

工具计量按顶层调用日志。出现 `functions.exec` 编排时，`tool_wrapped_calls` 与 `metric_coverage` 标明内部工具未解析；提交、行数、语言、工具报错不能当完整工程总量，报告隐藏这些不完整指标。活跃时长为事件间隔封顶估计，不等于人的投入、节约时间或费用。

## 模型与成本视角（重要背景）

相当一部分用户跨工具混用的动因是**成本**而非能力偏好：Codex 走官方模型，Claude Code 则常被接入低成本第三方/国产模型（kimi / deepseek / glm / qwen…）来跑可控任务。本 skill 已采集相应信号，分析时不要默认两个工具都跑官方高价模型：

- `models`：每会话的实际模型分布（Claude 取 `assistant.message.model`；Codex 取 `turn_context.model`）。Codex 的单位是去重后的 native turn（按 `turn_id`）配置记录；缺失 `turn_id` 的旧记录保留为单条记录。
- `reasoning_effort`：Codex 的推理强度配置（当前已知 low/medium/high/xhigh/max/ultra；新档位会单列展示）。单位同上。
- `thinking_turns/thinking_total`：Claude 侧带 thinking 块的轮次占比，作为推理深度近似。

模型/强度分布只能作为人工复核的配置线索。现有数据不能把档位逐轮连接到设计、执行、审查阶段和结果，不能据此断言 max 导致慢、过度设计或返工；需要该结论时另行采集阶段与结果归因证据。

## 隐私红线

- 原始会话文件只读；所有产物落在本地 `~/.agent-insights/`（权限 0600）。
- 报告含项目路径与会话摘要，**不要主动建议用户分享报告文件**；如用户要求归档到团队仓库，先提醒内含个人工作数据。

## 已知边界（与源码的有意差异）

- **历史窗口不对称**：Claude Code 默认自动清理约 30 天前的会话记录（`cleanupPeriodDays`），Codex 全量保留。跨工具对比时看"使用模式"而非绝对数量；洞察提示词中已要求 LLM 注意此口径。建议用户在 Claude `settings.json` 中调大 `cleanupPeriodDays` 以积累数据。
- **Codex rollout 不是天然的一会话一文件**：fork、resume 或 subagent 文件可能内嵌父会话历史。采集器以文件名和首条物理 `session_meta` 校验身份，区分 owned live、imported history 与 orphan；导入历史不计入物理会话指标。
- Codex 用户消息兼容旧 `event_msg/user_message` 与新 `event_msg/item_completed/UserMessage`；同一 native turn 的不同表示按相同文本一对一配对，保留同一来源的重复输入与不同消息 ID。用户追加输入不等于新增模型轮次，模型/强度仍按 native turn 配置计数。完整去重边界见 `reference/codex-session-schema.md`。
- 默认 facet transcript 有 120k 字符头尾截断及单消息截断，只适合使用模式提取，不代表完整覆盖。知识盘点按任务阶段/知识点有界下钻已授权原文并记录覆盖，不从头尾摘要声称穷尽长会话。
- Edit 行数统计用 `difflib`（对齐 `diffLines` 语义）；Codex 行数从 apply_patch 的 patch 文本解析。
- Codex 的 token 口径取 `input_tokens - cached_input_tokens`，对齐 Claude 的"不含缓存读取"口径。
- 会话时长有两个口径：`duration_minutes`（首尾跨度，源码兼容）与 `active_minutes`（事件间隔求和、单段 gap 封顶 15 分钟）。聚合统计用后者——Codex 会话常被跨天/跨周 resume，跨度口径会把一个会话算成上百小时。
- Claude 的 `/command` 本地执行记录（`<command-name>`、`<local-command-stdout>` 等）不计入人类消息。
- Codex 工具报错统计豁免 `rg`/`grep`/`diff`/`test` 等命令的退出码 1（无匹配/有差异是预期语义，不算失败），避免报错数虚高误导摩擦分析。
- 跨工具项目对齐用路径尾部两段作为键（同一项目在不同根路径下也能关联接力）。
- **内部会话过滤**：Codex 的 spawn_agent 子会话（`thread_source=subagent`）和纯自动评审会话（仅 `codex-auto-review` 轮次）标记为 `is_internal`，根会话统计、成功率、facet 与并行检测默认排除；报告单列内部模型/强度分布，供核对轻量 subagent 的实际使用。混在用户会话里的 auto-review 轮次不计入模型/强度分布。旧版本 Codex 会话无 `thread_source` 字段，保守按用户会话处理。
- facet 提示词新增 `user_instructions_to_agent`（源码类型里有但从未填充），用于支撑 CLAUDE.md/AGENTS.md 配置建议。
- 跨工具部分（overlap 区分跨工具并行、同项目 45 分钟接力检测、项目×工具矩阵、`tool_comparison` 与 `cross_tool_workflows` 两个 section、at_a_glance 的 `tool_division`）为本 skill 新增能力。

## 扩展新工具适配器

在 `collect.py` 中实现 `{tool}_scan()`（返回 agent/session_id/path/mtime/size）与 `{tool}_parse()`（解析为统一事件流：user / assistant_text / tool_use / tool_result / interrupt / tokens），并在 `CODEX_TOOL_CATEGORY` 旁补一张工具名→类别映射表，其余层零改动。详见 `reference/codex-session-schema.md` 的映射方法示范。

Codex fork 若未保留 foreign `session_meta`，采集器使用同次扫描或 manifest 中的父源，校验冻结 SHA-256 后逐行比较有 native turn/item/call ID 锚点的连续前缀；仅忽略 fork 重写的时间与 event thread 字段。匹配历史排除后保留累计 token 基线。父源缺失或无法证明前缀时保留原事件，并在 `source_audit.fork_history` 与 collect 的 `codex_ownership.fork_lineage_unverified` 明示未核实；这不证明存在复制历史，也不应自动清零正常 fork/subagent。发现可疑根会话时，须说明统计影响或将其单列未知，不能把 owner_leakage_lines=0 当完整归属已证实。manifest 之外的父源不会被自动读取。
