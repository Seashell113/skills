---
name: insights-aggregator
description: 跨工具 AI 编程助手使用洞察分析。扫描 Claude Code 与 Codex 的本地会话记录，计算使用统计、提取语义 facets、生成跨工具对比与组合使用分析，输出自包含 HTML 报告。当用户要求"分析我的 agent 使用情况"、"生成 insights 报告"、"跨工具使用分析"、"/insights"、"claude code 和 codex 用得怎么样"时使用。
---

# insights-aggregator

跨工具（Claude Code + Codex）会话洞察分析。架构：**本地脚本做全部确定性计算，LLM 只做两层语义分析**（单会话 facet 提取 → 跨会话洞察生成）。逻辑对齐 Claude Code 官方 `/insights` 源码，并扩展了跨工具关联分析。

## 目录

```
scripts/collect.py        扫描+解析双工具会话 → SessionMeta 缓存 + facet 待提取清单
scripts/aggregate.py      聚合 + 跨工具关联（并行/接力/项目矩阵）→ aggregated.json + insight-context.md
scripts/render.py         渲染自包含 HTML 报告
prompts/facet-extraction.md    facet 提取子 agent 提示词
prompts/insight-sections.md    9 个洞察 section + at_a_glance 提示词
reference/claude-insights-spec.md   Claude /insights 源码逻辑完整规范（背景知识，执行时不必读）
reference/codex-session-schema.md   Codex rollout JSONL 格式与字段映射表
```

数据目录默认 `~/.agent-insights/`（缓存、transcript、报告都在这里，原始会话只读不动）。

## 执行流程

### Step 0 — 与用户确认范围（开跑前）

默认分析**最近一个月**（`--days 30`）、facet 提取上限 **50 条**。开跑前向用户确认一句，并说明：调大窗口或分析数（如全历史、`--max-facets 200`）意味着更多并行子 agent 调用、更高的 LLM 开销和耗时。用户没有特殊要求就用默认值直接开始。

### Step 1 — 采集（脚本，无 LLM）

```bash
python3 {skill_dir}/scripts/collect.py [--days 30] [--max-facets 50]
```

窗口语义：SessionMeta 始终全量增量维护（便宜）；facet 只对窗口内的实质会话提取（新→旧，**不向窗口外回填**）。已提取过但 resume 后大幅续写（消息 +5 条以上）的会话会自动重新入队。

读 stdout JSON：关注 `metas_by_agent`（两个工具是否都有数据）、`substantive_in_window` / `facets_already_cached` / `pending_facets`（窗口内总数 / 已有缓存 / 本次待提取）、`note_remaining_uncached`（>0 说明还有历史会话未解析 meta，可提高 `--max-load` 再跑一次）。

### Step 2 — Facet 提取（并行子 agent）

读 `~/.agent-insights/work/pending_facets.json`。若为空（全部命中缓存）直接跳到 Step 3。

按 `prompts/facet-extraction.md` 中的 PROMPT 模板，为每个待提取会话派发一个子 agent（替换 `{{transcript_path}}`、`{{facet_path}}`、`{{agent}}`、`{{session_id}}`、`{{user_message_count}}` 占位符，取值都在 pending_facets.json 里）。要点：

- **并行**派发，每批 8-10 个；子 agent 用最快可用的模型即可（提取任务不需要最强模型）。若快模型报 429/不可用，直接降级用默认模型重试，不要反复重试快模型。
- 子 agent 自己读 transcript、自己写 facet JSON 文件，主 agent 不要捧着 transcript 内容。
- 某个子 agent 失败就跳过该会话，不要重试超过 1 次——缺个别 facet 不影响整体。

### Step 3 — 聚合（脚本，无 LLM）

```bash
python3 {skill_dir}/scripts/aggregate.py [--days 30]
```

`--days` 必须与 Step 1 一致（统计与语义同窗，报告才是真正的"阶段报告"；`--days 0` 为全历史）。读 stdout：`facets_used`、`cross_tool_overlap_events`、`handoff_direction_counts`。无效的 facet 文件会被静默忽略；若 `facets_used` 明显小于已提取数，检查 facet JSON 格式。

### Step 4 — 洞察生成（并行子 agent + 1 个串行）

按 `prompts/insight-sections.md`：

1. 9 个 section 并行派发（单工具数据则跳过 `tool_comparison`、`cross_tool_workflows`，剩 7 个）。每个子 agent 读 `work/insight-context.md`，写 `work/insights/{section}.json`。此层用**较强的模型**（叙事质量敏感）。
2. 全部完成后，串行生成 `at_a_glance`（上下文 = insight-context.md + 各 section 产出要点）。

### Step 5 — 渲染与交付

```bash
python3 {skill_dir}/scripts/render.py
```

然后：
1. `open` 生成的报告 HTML；
2. 在对话里给用户一段 At a Glance 中文摘要（What's working / What's hindering / 工具分工 / Quick wins / Ambitious workflows 各 1-2 句）+ 报告路径；
3. 问用户是否要深入某个 section 或采纳某条配置建议。

## 增量与缓存

- SessionMeta 按 `(agent, session_id)` 缓存，源 jsonl 文件 mtime 变化自动重算（全量增量维护）。
- facet 按 `(agent, session_id)` 永久缓存，仅当会话 resume 后大幅续写（消息 +5 条以上，依据 facet 内 `_user_message_count` 戳）才重提。
- 同窗口重复运行、或不同时期的窗口有重叠时，重叠部分直接复用缓存，只为新会话付 LLM 成本。强制全量重提：删 `~/.agent-insights/cache/facets/`。

## 模型与成本视角（重要背景）

相当一部分用户跨工具混用的动因是**成本**而非能力偏好：Codex 走官方模型，Claude Code 则常被接入低成本第三方/国产模型（kimi / deepseek / glm / qwen…）来跑可控任务。本 skill 已采集相应信号，分析时不要默认两个工具都跑官方高价模型：

- `models`：每会话的实际模型分布（Claude 取 `assistant.message.model`——接国产模型时记录的就是真实模型名；Codex 取 `turn_context.model`）。
- `reasoning_effort`：Codex 每轮的推理强度（low/medium/high/xhigh）。
- `thinking_turns/thinking_total`：Claude 侧带 thinking 块的轮次占比，作为推理深度近似。

洞察层（`tool_comparison`）会基于这些信号评估**任务-模型/推理强度匹配度**：简单任务是否开了过高强度（浪费时间）、复杂任务是否用了弱模型/低强度（返工风险），并给出调档建议。

## 隐私红线

- 原始会话文件只读；所有产物落在本地 `~/.agent-insights/`（权限 0600）。
- 报告含项目路径与会话摘要，**不要主动建议用户分享报告文件**；如用户要求归档到团队仓库，先提醒内含个人工作数据。

## 已知边界（与源码的有意差异）

- **历史窗口不对称**：Claude Code 默认自动清理约 30 天前的会话记录（`cleanupPeriodDays`），Codex 全量保留。跨工具对比时看"使用模式"而非绝对数量；洞察提示词中已要求 LLM 注意此口径。建议用户在 Claude `settings.json` 中调大 `cleanupPeriodDays` 以积累数据。
- 长会话不做 LLM 分块摘要，改为 120k 字符头尾截断（子 agent 上下文足够大，没必要多付一层摘要成本）。
- Edit 行数统计用 `difflib`（对齐 `diffLines` 语义）；Codex 行数从 apply_patch 的 patch 文本解析。
- Codex 的 token 口径取 `input_tokens - cached_input_tokens`，对齐 Claude 的"不含缓存读取"口径。
- 会话时长有两个口径：`duration_minutes`（首尾跨度，源码兼容）与 `active_minutes`（事件间隔求和、单段 gap 封顶 15 分钟）。聚合统计用后者——Codex 会话常被跨天/跨周 resume，跨度口径会把一个会话算成上百小时。
- Claude 的 `/command` 本地执行记录（`<command-name>`、`<local-command-stdout>` 等）不计入人类消息。
- Codex 工具报错统计豁免 `rg`/`grep`/`diff`/`test` 等命令的退出码 1（无匹配/有差异是预期语义，不算失败），避免报错数虚高误导摩擦分析。
- 跨工具项目对齐用路径尾部两段作为键（同一项目在不同根路径下也能关联接力）。
- **内部会话过滤**：Codex 的 spawn_agent 子会话（`thread_source=subagent`）和纯自动评审会话（仅 `codex-auto-review` 轮次）标记为 `is_internal`，统计/facet/并行检测默认排除并在报告中单独计数——否则会话数、low 档位占比和"并行多开"信号都会被内部执行拓扑严重虚高。混在用户会话里的 auto-review 轮次也不计入模型/强度分布。旧版本 Codex 会话无 `thread_source` 字段，保守按用户会话处理。
- facet 提示词新增 `user_instructions_to_agent`（源码类型里有但从未填充），用于支撑 CLAUDE.md/AGENTS.md 配置建议。
- 跨工具部分（overlap 区分跨工具并行、同项目 45 分钟接力检测、项目×工具矩阵、`tool_comparison` 与 `cross_tool_workflows` 两个 section、at_a_glance 的 `tool_division`）为本 skill 新增能力。

## 扩展新工具适配器

在 `collect.py` 中实现 `{tool}_scan()`（返回 agent/session_id/path/mtime/size）与 `{tool}_parse()`（解析为统一事件流：user / assistant_text / tool_use / tool_result / interrupt / tokens），并在 `CODEX_TOOL_CATEGORY` 旁补一张工具名→类别映射表，其余层零改动。详见 `reference/codex-session-schema.md` 的映射方法示范。
