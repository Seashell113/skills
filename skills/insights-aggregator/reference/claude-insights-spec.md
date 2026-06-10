# insights-aggregator

## 跨 Agent 会话洞察采集与聚合分析 Skill

**版本**：v2.0（基于 Claude Code CLI 源码对齐）
**核心设计**：本地统计 + 两层 LLM 分析（Session Facet 提取 → Cross-Session 洞察生成）

---

## 1. 定位与目标

**目标**：为任意 AI 交互 Agent 建立统一的会话数据采集规范，以及跨 Agent 聚合分析的完整逻辑链路。

**设计原则**：
1. **本地优先**：原始 transcript 只读、不离开本地机器。
2. **LLM 驱动语义分析**：会话目标、满意度、摩擦等推断类任务交由 LLM 处理，而非硬编码规则。
3. **增量可缓存**：会话元数据和提取的 Facets 均本地缓存，支持增量分析。
4. **跨 Agent 聚合**：单 Agent 内输出标准化 JSON，聚合器消费多源 JSON 输出全局报告。

---

## 2. 核心概念

| 术语 | 定义 |
|------|------|
| **Session（会话）** | 一次完整的用户-Agent 交互周期，持久化为本地 `.jsonl` 文件。 |
| **Transcript** | 会话的完整消息序列，包含 user / assistant / system / attachment 消息。 |
| **Facet** | 从单个会话中提取的结构化语义数据（目标、结果、满意度、摩擦等）。 |
| **SessionMeta** | 从单个会话中计算的确定性统计数据（工具频次、代码行数、响应时间等）。 |
| **AggregatedData** | 跨会话聚合后的全局统计数据。 |
| **InsightSection** | 跨会话洞察的一个分析维度（如交互风格、摩擦分析、领域聚类等）。 |

---

## 3. 数据层：本地会话存储规范

### 3.1 存储路径约定

各 Agent 必须将会话数据持久化到标准化路径：

```
{CLAUDE_CONFIG_HOME}/
  projects/
    {sanitized_project_dir}/
      {session_id}.jsonl          # 主会话 transcript
      {session_id}/
        subagents/
          agent-{agent_id}.jsonl  # 子 Agent transcript
        remote-agents/
          remote-agent-{task_id}.meta.json
```

- `CLAUDE_CONFIG_HOME`：Agent 配置目录（如 `~/.claude`）。
- `session_id`：UUID 格式，作为会话唯一标识。
- `.jsonl` 格式：每行一个 JSON 对象，按时间顺序追加。

### 3.2 Transcript 消息格式（JSONL 单条 Schema）

每条消息必须包含以下字段：

```typescript
interface TranscriptMessage {
  uuid: string
  parentUuid: string | null        // 用于构建对话链
  type: 'user' | 'assistant' | 'system' | 'attachment'
  timestamp: string                // ISO 8601
  sessionId: string
  version: string                  // Agent 版本
  gitBranch?: string
  cwd?: string                     // 工作目录（用于识别项目）

  // 消息内容
  message: {
    content: string | Array<ContentBlock>
    usage?: {
      input_tokens?: number
      output_tokens?: number
    }
  }

  // 仅 assistant 消息
  isSidechain?: boolean
  agentId?: string
  teamName?: string
  agentName?: string
}

interface ContentBlock {
  type: 'text' | 'tool_use' | 'tool_result' | 'image' | 'document'
  // tool_use
  name?: string                    // 工具名称（Bash/Read/Write/Edit...）
  input?: Record<string, unknown>  // 工具参数
  // tool_result
  is_error?: boolean
  content?: string
  // text
  text?: string
}
```

### 3.3 消息类型处理规则

| 消息类型 | 处理方式 |
|---------|---------|
| `user` | 提取用户输入文本、检测打断信号、计算响应时间 |
| `assistant` | 提取工具调用（`tool_use`）、token 消耗 |
| `system` | compact boundary、turn_duration 等元数据 |
| `attachment` | 可忽略或计入文件引用 |
| `progress` | **不持久化**，UI 状态不进入 transcript |

**对话链构建**：通过 `parentUuid` 从 leaf 消息回溯到 root，构建完整对话序列。

**分支去重**：同一 `session_id` 可能因 retry/branch 产生多个 leaf，保留 **user_message_count 最多** 的分支，其余丢弃。

---

## 4. 采集层：本地统计（SessionMeta）

### 4.1 采集原则

1. **只读**：不修改原始 `.jsonl`。
2. **确定性计算**：所有 SessionMeta 指标由本地代码精确计算，不依赖 LLM。
3. **增量缓存**：计算结果写入 `session-meta/{session_id}.json`，下次直接读取。

### 4.2 核心指标计算

遍历会话的每条消息，按类型统计：

#### 4.2.1 工具调用统计

```typescript
toolCounts: Record<string, number>   // 各工具调用次数
languages: Record<string, number>    // 文件操作涉及的语言频次

// 扩展名映射表
const EXTENSION_TO_LANGUAGE: Record<string, string> = {
  '.ts': 'TypeScript', '.tsx': 'TypeScript',
  '.js': 'JavaScript', '.jsx': 'JavaScript',
  '.py': 'Python', '.rb': 'Ruby', '.go': 'Go',
  '.rs': 'Rust', '.java': 'Java',
  '.md': 'Markdown', '.json': 'JSON',
  '.yaml': 'YAML', '.yml': 'YAML',
  '.sh': 'Shell', '.css': 'CSS', '.html': 'HTML',
}
```

- 工具名从 `tool_use.name` 提取。
- 语言从 `tool_use.input.file_path` 的扩展名映射。
- `Edit` / `Write` 工具的文件路径计入 `filesModified`。

#### 4.2.2 代码行变更统计

| 操作 | 计算方式 |
|------|---------|
| `Edit` | 对 `old_string` 和 `new_string` 执行 `diffLines()`，统计 `added` / `removed` 行数 |
| `Write` | 统计 `content` 中 `\n` 数量 + 1（作为新增行数） |

#### 4.2.3 Git 操作统计

- 检测 Bash 命令字符串中是否包含子串 `git commit` / `git push`。

#### 4.2.4 Token 消耗统计

- 从 `assistant` 消息的 `message.usage.input_tokens` / `output_tokens` 累加。

#### 4.2.5 用户响应时间

```
responseTime = userMessageTimestamp - lastAssistantTimestamp
```

- 只统计**真实人类消息**（排除纯 tool_result 消息）。
- 过滤条件：`2s < responseTime < 1h`，超出范围视为无效数据。

#### 4.2.6 用户打断检测

- 检测消息内容是否包含子串 `[Request interrupted by user`。
- 每出现一次，打断计数 +1。

#### 4.2.7 消息时段分布

- 从真实人类消息的时间戳提取小时（0-23，本地时区）。
- 用于生成时段分布图。

#### 4.2.8 工具错误分类

当 `tool_result.is_error === true` 时，根据 `content` 内容分类：

| 分类关键词 | 错误类型 |
|-----------|---------|
| `exit code` | Command Failed |
| `rejected` / `doesn't want` | User Rejected |
| `string to replace not found` / `no changes` | Edit Failed |
| `modified since read` | File Changed |
| `exceeds maximum` / `too large` | File Too Large |
| `file not found` / `does not exist` | File Not Found |
| 其他 | Other |

#### 4.2.9 特殊能力标记

布尔标志，会话中只要出现一次即标记为 true：

| 标记 | 检测条件 |
|------|---------|
| `uses_task_agent` | 工具名为 `spawn_agent` 或 `legacy_spawn_agent` |
| `uses_mcp` | 工具名以 `mcp__` 前缀开头 |
| `uses_web_search` | 工具名为 `WebSearch` |
| `uses_web_fetch` | 工具名为 `WebFetch` |

### 4.3 SessionMeta 输出 Schema

```typescript
interface SessionMeta {
  session_id: string
  project_path: string           // 从 firstMessage.cwd 提取
  start_time: string             // ISO 8601
  duration_minutes: number       // (modified - created) / 60000

  user_message_count: number     // 真实人类消息数（排除纯 tool_result）
  assistant_message_count: number

  tool_counts: Record<string, number>
  languages: Record<string, number>

  git_commits: number
  git_pushes: number
  input_tokens: number
  output_tokens: number

  first_prompt: string           // 第一条有意义用户消息的摘要（200字符截断）
  summary?: string               // 会话摘要（如有）

  // 新增统计
  user_interruptions: number
  user_response_times: number[]  // 秒为单位
  tool_errors: number
  tool_error_categories: Record<string, number>

  uses_task_agent: boolean
  uses_mcp: boolean
  uses_web_search: boolean
  uses_web_fetch: boolean

  lines_added: number
  lines_removed: number
  files_modified: number         // Set.size

  message_hours: number[]        // 0-23 小时数组
  user_message_timestamps: string[]  // ISO 时间戳数组（用于多会话并行检测）
}
```

### 4.4 缓存策略

```
{CLAUDE_CONFIG_HOME}/
  usage-data/
    session-meta/
      {session_id}.json    // SessionMeta 缓存
    facets/
      {session_id}.json    // SessionFacets 缓存（见第 5 章）
```

- 缓存文件权限：`0o600`（仅用户可读）。
- 加载时校验 schema，损坏则删除重建。

---

## 5. 分析层 A：Session Facet 提取（LLM 驱动）

### 5.1 设计目标

将会话的自然语言 transcript 转换为**结构化语义数据**。这一步是系统的核心——用 LLM 的语义理解能力替代硬编码规则。

### 5.2 输入准备

#### 5.2.1 Transcript 格式化

将消息序列转换为 LLM 可读文本格式：

```
Session: {session_id前8位}
Date: {start_time}
Project: {project_path}
Duration: {duration_minutes} min

[User]: {内容前500字符}
[Assistant]: {文本内容前300字符}
[Tool: {工具名}]
...
```

- 用户消息保留前 500 字符。
- Assistant 文本保留前 300 字符。
- 工具调用只记录名称，不记录参数详情。

#### 5.2.2 长会话摘要

当 transcript 超过 30,000 字符时：
1. 按 25,000 字符分块。
2. 并行调用 LLM 对每个块生成摘要（提示词见下）。
3. 将多个摘要拼接作为 facet 提取的输入。

**摘要提示词**：
```
Summarize this portion of a session transcript. Focus on:
1. What the user asked for
2. What the agent did (tools used, files modified)
3. Any friction or issues
4. The outcome
Keep it concise - 3-5 sentences. Preserve specific details like file names, error messages, and user feedback.
```

### 5.3 Facet 提取提示词

使用 LLM（建议用最强模型，如 Opus）执行提取。提示词结构：

```
Analyze this session and extract structured facets.

CRITICAL GUIDELINES:

1. **goal_categories**: Count ONLY what the USER explicitly asked for.
   - DO NOT count the agent's autonomous exploration
   - DO NOT count work the agent decided to do on its own
   - ONLY count when user says "can you...", "please...", "I need...", "let's..."

2. **user_satisfaction_counts**: Base ONLY on explicit user signals.
   - "Yay!", "great!", "perfect!" → happy
   - "thanks", "looks good", "that works" → satisfied
   - "ok, now let's..." (continuing without complaint) → likely_satisfied
   - "that's not right", "try again" → dissatisfied
   - "this is broken", "I give up" → frustrated

3. **friction_counts**: Be specific about what went wrong.
   - misunderstood_request: agent interpreted incorrectly
   - wrong_approach: Right goal, wrong solution method
   - buggy_code: Code didn't work correctly
   - user_rejected_action: User said no/stop to a tool call
   - excessive_changes: Over-engineered or changed too much

4. If very short or just warmup, use warmup_minimal for goal_category

SESSION:
{formatted_transcript}

RESPOND WITH ONLY A VALID JSON OBJECT matching this schema:
{
  "underlying_goal": "What the user fundamentally wanted to achieve",
  "goal_categories": {"category_name": count, ...},
  "outcome": "fully_achieved|mostly_achieved|partially_achieved|not_achieved|unclear_from_transcript",
  "user_satisfaction_counts": {"level": count, ...},
  "claude_helpfulness": "unhelpful|slightly_helpful|moderately_helpful|very_helpful|essential",
  "session_type": "single_task|multi_task|iterative_refinement|exploration|quick_question",
  "friction_counts": {"friction_type": count, ...},
  "friction_detail": "One sentence describing friction or empty",
  "primary_success": "none|fast_accurate_search|correct_code_edits|good_explanations|proactive_help|multi_file_changes|good_debugging",
  "brief_summary": "One sentence: what user wanted and whether they got it",
  "user_instructions_to_claude": ["specific instruction user gave to agent", ...]
}
```

### 5.4 Facet 输出 Schema

```typescript
interface SessionFacets {
  session_id: string

  underlying_goal: string        // 用户根本目标
  goal_categories: Record<string, number>
    // 可选值：debug_investigate, implement_feature, fix_bug,
    //   write_script_tool, refactor_code, configure_system,
    //   create_pr_commit, analyze_data, understand_codebase,
    //   write_tests, write_docs, deploy_infra, warmup_minimal

  outcome: string
    // 可选值：fully_achieved, mostly_achieved, partially_achieved,
    //   not_achieved, unclear_from_transcript

  user_satisfaction_counts: Record<string, number>
    // 可选值：frustrated, dissatisfied, likely_satisfied,
    //   satisfied, happy, unsure, neutral, delighted

  claude_helpfulness: string
    // 可选值：unhelpful, slightly_helpful, moderately_helpful,
    //   very_helpful, essential

  session_type: string
    // 可选值：single_task, multi_task, iterative_refinement,
    //   exploration, quick_question

  friction_counts: Record<string, number>
    // 可选值：misunderstood_request, wrong_approach, buggy_code,
    //   user_rejected_action, claude_got_blocked, user_stopped_early,
    //   wrong_file_or_location, excessive_changes, slow_or_verbose,
    //   tool_failed, user_unclear, external_issue

  friction_detail: string        // 一句话描述摩擦
  primary_success: string        // 主要成功因素
  brief_summary: string          // 一句话摘要
  user_instructions_to_claude?: string[]  // 用户给 Agent 的具体指令
}
```

### 5.5 过滤规则

提取后过滤低质量会话：

1. **最小会话过滤**：`user_message_count < 2` 或 `duration_minutes < 1` → 排除。
2. **预热会话过滤**：`goal_categories` 只有一个且为 `warmup_minimal` → 排除。
3. **元会话过滤**：前 5 条消息中包含 `RESPOND WITH ONLY A VALID JSON OBJECT` 或 `record_facets` → 排除（防止 facet 提取本身被计入）。

---

## 6. 分析层 B：数据聚合（AggregatedData）

### 6.1 聚合逻辑

将多个会话的 `SessionMeta` 和 `SessionFacets` 合并为全局统计：

```typescript
interface AggregatedData {
  total_sessions: number
  total_sessions_scanned?: number   // 扫描总数（含被过滤的）
  sessions_with_facets: number
  date_range: { start: string; end: string }

  total_messages: number
  total_duration_hours: number
  total_input_tokens: number
  total_output_tokens: number

  tool_counts: Record<string, number>
  languages: Record<string, number>
  git_commits: number
  git_pushes: number
  projects: Record<string, number>   // project_path → session_count

  goal_categories: Record<string, number>
  outcomes: Record<string, number>
  satisfaction: Record<string, number>
  helpfulness: Record<string, number>
  session_types: Record<string, number>
  friction: Record<string, number>
  success: Record<string, number>

  session_summaries: Array<{
    id: string
    date: string
    summary: string
    goal?: string
  }>

  total_interruptions: number
  total_tool_errors: number
  tool_error_categories: Record<string, number>

  user_response_times: number[]
  median_response_time: number
  avg_response_time: number

  sessions_using_task_agent: number
  sessions_using_mcp: number
  sessions_using_web_search: number
  sessions_using_web_fetch: number

  total_lines_added: number
  total_lines_removed: number
  total_files_modified: number

  days_active: number
  messages_per_day: number
  message_hours: number[]

  multi_clauding: {
    overlap_events: number
    sessions_involved: number
    user_messages_during: number
  }
}
```

### 6.2 多会话并行检测（Multi-clauding）

**算法**：滑动窗口（30 分钟窗口）

```
1. 收集所有会话的所有用户消息时间戳
2. 按时间排序
3. 滑动窗口内检测模式：session1 → session2 → session1
   （即同一 session_id 在窗口内出现两次，中间穿插了其他 session）
4. 统计：overlap_events（配对数）、sessions_involved（涉及会话数）、
   user_messages_during（重叠期间的消息数）
```

---

## 7. 分析层 C：跨会话洞察生成（Insight Generation）

### 7.1 设计目标

基于聚合数据 + Facet 摘要，生成面向用户的叙事性洞察报告。

### 7.2 执行策略

**并行 + 串行两阶段**：

1. **第一阶段（并行）**：7 个 InsightSection 同时调用 LLM。
2. **第二阶段（串行）**：基于第一阶段结果，生成 `at_a_glance` 概览。

### 7.3 数据上下文构建

将所有聚合数据和 facet 摘要拼接为 LLM 上下文：

```
DATA:
{aggregated_data_json}

SESSION SUMMARIES:
- {brief_summary} ({outcome}, {helpfulness})
...

FRICTION DETAILS:
- {friction_detail}
...

USER INSTRUCTIONS TO AGENT:
- {user_instructions_to_claude}
...
```

限制：
- Session summaries 最多 50 条。
- Friction details 最多 20 条。
- User instructions 最多 15 条。

### 7.4 Insight Section 定义

#### Section 1: project_areas

```
分析使用数据，识别项目领域。

RESPOND WITH ONLY A VALID JSON OBJECT:
{
  "areas": [
    {"name": "Area name", "session_count": N, "description": "2-3 sentences"}
  ]
}

Include 4-5 areas. Skip internal operations.
```

#### Section 2: interaction_style

```
分析使用数据，描述用户的交互风格。

RESPOND WITH ONLY A VALID JSON OBJECT:
{
  "narrative": "2-3 paragraphs analyzing HOW the user interacts. Use second person 'you'. Describe patterns: iterate quickly vs detailed upfront specs? Interrupt often or let agent run? Include specific examples. Use **bold** for key insights.",
  "key_pattern": "One sentence summary of most distinctive interaction style"
}
```

#### Section 3: what_works

```
识别用户使用 Agent 时做得好的方面。使用第二人称 ("you")。

RESPOND WITH ONLY A VALID JSON OBJECT:
{
  "intro": "1 sentence of context",
  "impressive_workflows": [
    {"title": "Short title (3-6 words)", "description": "2-3 sentences"}
  ]
}

Include 3 impressive workflows.
```

#### Section 4: friction_analysis

```
识别用户的摩擦点。使用第二人称 ("you")。

RESPOND WITH ONLY A VALID JSON OBJECT:
{
  "intro": "1 sentence summarizing friction patterns",
  "categories": [
    {"category": "Concrete category name", "description": "1-2 sentences", "examples": ["Specific example", "Another example"]}
  ]
}

Include 3 friction categories with 2 examples each.
```

#### Section 5: suggestions

```
分析使用数据并建议改进。

包含以下功能参考（供 features_to_try 选择）：
1. MCP Servers - 通过 MCP 连接外部工具和 API
2. Custom Skills - 以 Markdown 文件定义可复用提示词
3. Hooks - 生命周期事件触发的 Shell 命令
4. Headless Mode - 非交互式脚本执行
5. Task Agents - 子 Agent 并行处理

RESPOND WITH ONLY A VALID JSON OBJECT:
{
  "claude_md_additions": [
    {"addition": "具体规则文本", "why": "基于会话数据的解释", "prompt_scaffold": "建议插入位置"}
  ],
  "features_to_try": [
    {"feature": "功能名", "one_liner": "一句话描述", "why_for_you": "个性化理由", "example_code": "可复制的配置/命令"}
  ],
  "usage_patterns": [
    {"title": "短标题", "suggestion": "1-2句总结", "detail": "详细解释", "copyable_prompt": "可直接粘贴的提示词"}
  ]
}

IMPORTANT for claude_md_additions: PRIORITIZE instructions that appear MULTIPLE TIMES in the user data.
```

#### Section 6: on_the_horizon

```
识别未来机会。

RESPOND WITH ONLY A VALID JSON OBJECT:
{
  "intro": "1 sentence about evolving AI-assisted development",
  "opportunities": [
    {"title": "Short title", "whats_possible": "2-3 ambitious sentences", "how_to_try": "1-2 sentences mentioning tooling", "copyable_prompt": "Detailed prompt to try"}
  ]
}

Include 3 opportunities. Think BIG.
```

#### Section 7: fun_ending

```
从会话摘要中找一个值得记忆的时刻。

RESPOND WITH ONLY A VALID JSON OBJECT:
{
  "headline": "A memorable QUALITATIVE moment - not a statistic. Something human, funny, or surprising.",
  "detail": "Brief context about when/where this happened"
}
```

### 7.5 At a Glance 生成（串行第二阶段）

基于前 7 个 section 的结果，生成 4 段式概览：

```
You're writing an "At a Glance" summary.

Use this 4-part structure:
1. **What's working** - User's unique style and impactful things done
2. **What's hindering you** - Split into (a) agent's fault and (b) user-side friction
3. **Quick wins to try** - Specific features or workflow techniques
4. **Ambitious workflows for better models** - What will become possible in 3-6 months

Keep each section to 2-3 not-too-long sentences. Use a coaching tone.

RESPOND WITH ONLY A VALID JSON OBJECT:
{
  "whats_working": "...",
  "whats_hindering": "...",
  "quick_wins": "...",
  "ambitious_workflows": "..."
}
```

### 7.6 输出 Schema

```typescript
interface InsightResults {
  at_a_glance?: {
    whats_working?: string
    whats_hindering?: string
    quick_wins?: string
    ambitious_workflows?: string
  }
  project_areas?: { areas?: Array<{ name: string; session_count: number; description: string }> }
  interaction_style?: { narrative?: string; key_pattern?: string }
  what_works?: { intro?: string; impressive_workflows?: Array<{ title: string; description: string }> }
  friction_analysis?: { intro?: string; categories?: Array<{ category: string; description: string; examples?: string[] }> }
  suggestions?: {
    claude_md_additions?: Array<{ addition: string; why: string; where?: string; prompt_scaffold?: string }>
    features_to_try?: Array<{ feature: string; one_liner: string; why_for_you: string; example_code?: string }>
    usage_patterns?: Array<{ title: string; suggestion: string; detail?: string; copyable_prompt?: string }>
  }
  on_the_horizon?: { intro?: string; opportunities?: Array<{ title: string; whats_possible: string; how_to_try?: string; copyable_prompt?: string }> }
  fun_ending?: { headline?: string; detail?: string }
}
```

---

## 8. 报告渲染层

### 8.1 HTML 报告生成

将 `AggregatedData` + `InsightResults` 渲染为自包含 HTML 文件：

- **纯字符串拼接**，不依赖模板引擎。
- **内联 CSS**：所有样式写死在 `<style>` 标签中。
- **内联 JS**：时区选择器、复制按钮等交互逻辑内联。
- **图表**：纯 CSS 条形图（`div` + 百分比宽度），不依赖图表库。

### 8.2 输出路径

```
{CLAUDE_CONFIG_HOME}/
  usage-data/
    report.html              # 最新报告（固定路径，覆盖写入）
    report-{timestamp}.html  # 历史报告（可选）
    facets/                  # Facet 缓存目录
    session-meta/            # SessionMeta 缓存目录
```

### 8.3 图表固定顺序

部分图表需要固定顺序（而非按数量排序）：

```typescript
const SATISFACTION_ORDER = [
  'frustrated', 'dissatisfied', 'likely_satisfied', 'satisfied', 'happy', 'unsure'
]

const OUTCOME_ORDER = [
  'not_achieved', 'partially_achieved', 'mostly_achieved', 'fully_achieved', 'unclear_from_transcript'
]
```

---

## 9. 跨 Agent 聚合规范

### 9.1 单 Agent 输出格式

每个 Agent 分析完成后，输出标准化 JSON 文件：

```typescript
interface AgentInsightsExport {
  metadata: {
    agent_type: string           // claude-code | gemini-cli | copilot | ...
    agent_version: string
    generated_at: string         // ISO 8601
    date_range: { start: string; end: string }
    session_count: number
    username?: string            // 可选，脱敏处理
  }
  aggregated_data: AggregatedData
  insights: InsightResults
  facets_summary?: {
    total: number
    goal_categories: Record<string, number>
    outcomes: Record<string, number>
    satisfaction: Record<string, number>
    friction: Record<string, number>
  }
}
```

### 9.2 聚合器输入

聚合器读取多个 Agent 的 `AgentInsightsExport` JSON 文件，执行合并。

### 9.3 聚合维度

| 维度 | 聚合方式 |
|------|---------|
| **全局统计** | 各 Agent 数值直接求和 |
| **领域聚类** | 按领域名称语义合并，累加 session_count |
| **工具偏好** | 各 Agent 工具使用频次合并，计算占比 |
| **时间分布** | 合并各 Agent 的 message_hours 数组 |
| **满意度** | 合并各 Agent 满意度分布 |
| **摩擦热点** | 合并摩擦类型频次，识别跨 Agent 共性 |
| **多 Agent 并行** | 检测跨 Agent 的时间重叠（同一用户同时使用多个 Agent） |

### 9.4 跨 Agent 洞察生成

基于合并后的全局数据，**重新执行第 7 章的洞察生成流程**（而非简单拼接各 Agent 报告）。

原因：跨 Agent 的数据可能揭示单 Agent 内不可见的模式（如"你在 Claude Code 中写代码，在 Claude Desktop 中审阅"）。

---

## 10. 性能与配额控制

### 10.1 限制参数

| 参数 | 值 | 说明 |
|------|-----|------|
| `MAX_SESSIONS_TO_LOAD` | 200 | 最大加载会话数（按时间倒序） |
| `MAX_FACET_EXTRACTIONS` | 50 | 最大 facet 提取数（未缓存的） |
| `META_BATCH_SIZE` | 50 | SessionMeta 加载批大小 |
| `LOAD_BATCH_SIZE` | 10 | JSONL 解析批大小 |
| `FACET_CONCURRENCY` | 50 | Facet 提取并发数 |
| `TRANSCRIPT_SUMMARY_THRESHOLD` | 30,000 字符 | 超过则分块摘要 |
| `CHUNK_SIZE` | 25,000 字符 | 摘要分块大小 |

### 10.2 LLM 调用成本估算

| 阶段 | 调用次数 | 模型 | 单次最大 Token |
|------|---------|------|--------------|
| Facet 提取 | 最多 50 次 | Opus | 4096 |
| 洞察 Section | 7 次并行 | Opus | 8192 |
| At a Glance | 1 次 | Opus | 8192 |
| **总计** | **最多 58 次** | | |

**优化**：通过缓存机制，已分析过的会话不再重复调用 LLM。

---

## 11. 隐私与安全

### 11.1 数据红线

- **原始 transcript 不上传**：所有解析在本地完成。
- **Facet 提取的输入**：transcript 文本本地格式化后传给 LLM API，属于正常 API 使用。
- **报告文件权限**：`0o600`（仅用户可读）。
- **路径脱敏**：文件路径中的用户名目录可替换为 `{USER}`。

### 11.2 内部员工特殊逻辑

仅当 `USER_TYPE === 'ant'`（Anthropic 内部）时：
- 支持从远程 homespace 通过 SCP 收集会话数据。
- 支持将 HTML 报告上传到内部 S3。
- 生成额外的 `cc_team_improvements` 和 `model_behavior_improvements` section。

普通用户不触发任何上述逻辑。

---

## 12. 附录：标签映射表

用于将内部标识符转换为人类可读标签：

```typescript
const LABEL_MAP: Record<string, string> = {
  // Goal categories
  debug_investigate: 'Debug/Investigate',
  implement_feature: 'Implement Feature',
  fix_bug: 'Fix Bug',
  write_script_tool: 'Write Script/Tool',
  refactor_code: 'Refactor Code',
  configure_system: 'Configure System',
  create_pr_commit: 'Create PR/Commit',
  analyze_data: 'Analyze Data',
  understand_codebase: 'Understand Codebase',
  write_tests: 'Write Tests',
  write_docs: 'Write Docs',
  deploy_infra: 'Deploy/Infra',
  warmup_minimal: 'Cache Warmup',

  // Success factors
  fast_accurate_search: 'Fast/Accurate Search',
  correct_code_edits: 'Correct Code Edits',
  good_explanations: 'Good Explanations',
  proactive_help: 'Proactive Help',
  multi_file_changes: 'Multi-file Changes',
  handled_complexity: 'Multi-file Changes',
  good_debugging: 'Good Debugging',

  // Friction types
  misunderstood_request: 'Misunderstood Request',
  wrong_approach: 'Wrong Approach',
  buggy_code: 'Buggy Code',
  user_rejected_action: 'User Rejected Action',
  claude_got_blocked: 'Claude Got Blocked',
  user_stopped_early: 'User Stopped Early',
  wrong_file_or_location: 'Wrong File/Location',
  excessive_changes: 'Excessive Changes',
  slow_or_verbose: 'Slow/Verbose',
  tool_failed: 'Tool Failed',
  user_unclear: 'User Unclear',
  external_issue: 'External Issue',

  // Satisfaction
  frustrated: 'Frustrated',
  dissatisfied: 'Dissatisfied',
  likely_satisfied: 'Likely Satisfied',
  satisfied: 'Satisfied',
  happy: 'Happy',
  unsure: 'Unsure',
  neutral: 'Neutral',
  delighted: 'Delighted',

  // Session types
  single_task: 'Single Task',
  multi_task: 'Multi Task',
  iterative_refinement: 'Iterative Refinement',
  exploration: 'Exploration',
  quick_question: 'Quick Question',

  // Outcomes
  fully_achieved: 'Fully Achieved',
  mostly_achieved: 'Mostly Achieved',
  partially_achieved: 'Partially Achieved',
  not_achieved: 'Not Achieved',
  unclear_from_transcript: 'Unclear',

  // Helpfulness
  unhelpful: 'Unhelpful',
  slightly_helpful: 'Slightly Helpful',
  moderately_helpful: 'Moderately Helpful',
  very_helpful: 'Very Helpful',
  essential: 'Essential',
}
```

---

## 13. 扩展点

### 13.1 自定义 Facet 字段

可在 `SessionFacets` 中扩展自定义字段：

```typescript
interface SessionFacets {
  // ... 标准字段

  // 自定义扩展
  custom_metrics?: Record<string, number>
  tags?: string[]
}
```

自定义字段需在 Facet 提取提示词中说明，并在 `isValidSessionFacets` 校验中放行。

### 13.2 自定义 Insight Section

在 `INSIGHT_SECTIONS` 数组中追加自定义 section：

```typescript
{
  name: 'security_posture',
  prompt: `分析使用数据中的安全实践...`,
  maxTokens: 4096,
}
```

自定义 section 的结果会自动出现在 `InsightResults` 中，并在 HTML 报告中渲染（如需定制渲染，需修改 `generateHtmlReport`）。

### 13.3 Agent 适配

不同 Agent 的核心差异在于：

1. **Transcript 路径**：各 Agent 的会话存储位置不同。
2. **消息格式**：各 Agent 的 JSONL schema 可能有细微差异（如字段名、块类型）。
3. **工具名称**：各 Agent 的工具命名可能不同（如 `Bash` vs `bash`）。

适配层只需实现：
- `scanAllSessions(): LiteSessionInfo[]`
- `loadAllLogsFromSessionFile(path): LogOption[]`
- `extractToolStats(log): ToolStats`

其余逻辑（Facet 提取、洞察生成、报告渲染）完全复用。

---

## 14. 使用方式

### 14.1 作为 Skill 触发

```
/insights                    # 分析当前 Agent 的近期会话
/insights --aggregate        # 跨 Agent 聚合分析（需各 Agent 数据已采集）
/insights --period=30d       # 指定时间范围
```

### 14.2 输出产物

- **单 Agent**：`{CLAUDE_CONFIG_HOME}/usage-data/report.html`
- **跨 Agent 聚合**：`{CLAUDE_CONFIG_HOME}/usage-data/report-aggregated-{date}.html`

产物为自包含 HTML，含交互式图表和一键复制提示词功能。

---

*版本：v2.0*
*对齐源码：claude-code-main/src/commands/insights.ts*
*最后更新：2026-06-08*
