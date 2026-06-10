# Codex Session Schema → 统一事件流映射表

基于本机真实数据验证（Codex CLI 0.137.x，2025-12 至 2026-06 的 rollout 文件）。`collect.py` 的 `codex_parse()` 按此表实现。

## 存储布局

```
~/.codex/sessions/YYYY/MM/DD/rollout-{ISO时间戳}-{uuid}.jsonl
```

- `session_id` = 文件名末尾的 uuid（与首行 `session_meta.payload.id` 一致）。
- 每行一个 JSON 对象：`{timestamp, type, payload}`，timestamp 为 ISO 8601 UTC。

## 顶层 type 与映射

| 顶层 type | payload 关键字段 | 映射到统一事件 |
|---|---|---|
| `session_meta` | `id, cwd, originator, source, cli_version` | `project_path`、`source`、会话起点 |
| `turn_context` | `cwd, model?, approval_policy, sandbox_policy` | 兜底 `project_path` |
| `event_msg` | 见下表 | 见下表 |
| `response_item` | 见下表 | 见下表 |
| `compacted` / 其他 | — | 忽略 |

## event_msg.payload.type

| type | 映射 | 说明 |
|---|---|---|
| `user_message` | `user` 事件，text=`payload.message` | **用户输入的权威来源**（干净文本）。需过滤以 `<environment_context>`、`<user_instructions>`、`<permissions` 开头的注入消息 |
| `token_count` | `tokens` 事件 | 取 `info.last_token_usage`（per-call 增量；`total_token_usage` 是累计值不要累加）。`info` 可为 null。口径对齐：`input = input_tokens - cached_input_tokens` |
| `turn_aborted` (reason=`interrupted`) | `interrupt` 事件 | 用户打断 |
| `web_search_end` | `tool_use(web_search)` | 置 uses_web_search |
| `agent_message` | 忽略 | 与 `response_item.message(assistant)` 重复 |
| `task_started/task_complete/context_compacted/thread_rolled_back/patch_apply_end/mcp_tool_call_end/item_completed/image_generation_end` | 忽略 | UI/状态事件 |

## response_item.payload.type

| type | 映射 | 说明 |
|---|---|---|
| `message` role=`assistant` | `assistant_text`，拼接 content 里 `output_text` 块 | |
| `message` role=`user`/`developer` | 忽略 | user 文本走 event_msg.user_message；developer 是注入的系统内容 |
| `reasoning` | 忽略 | 思维链不参与统计 |
| `function_call` | `tool_use(name, JSON.parse(arguments))` | 工具调用主来源 |
| `custom_tool_call` | `tool_use(name)` | 主要是 `apply_patch`，patch 文本在 `payload.input` |
| `function_call_output` | `tool_result` | `output` 含 `"exited with code N"`，N≠0 → is_error（Command Failed）|

## 工具名 → 行为类别（与 Claude 对齐用）

| Codex 工具 | 类别 | Claude 对应 |
|---|---|---|
| `exec_command` / `shell` / `local_shell` / `write_stdin` / `read_thread_terminal` | shell | Bash |
| `apply_patch` | edit | Edit/Write |
| `view_image` | read | Read |
| `web_search` | web | WebSearch |
| `update_plan` | plan | TodoWrite/TaskCreate |
| `spawn_agent` / `wait_agent` / `close_agent` | agent | Task/Agent |
| `click` / `navigate_page` / `take_screenshot` / `evaluate_script` 等 | browser | （Claude 侧通常走 mcp__) |
| `mcp__*` | mcp | mcp__* |

## apply_patch 文本解析

```
*** Begin Patch
*** Add File: path/to/file.md      ← 文件 + 语言（扩展名）
+新增行                             ← 行首 + 计 lines_added
*** Update File: src/x.py
-删除行                             ← 行首 - 计 lines_removed
*** Delete File: old.txt
*** End Patch
```

排除 `+++`/`---`/`*** ` 前缀的行。文件路径计入 files_modified，扩展名映射语言。

## 其他信号

- **git commit/push**：`exec_command.arguments.cmd`（string 或 list）含 `git commit` / `git push` 子串。
- **响应时间**：上一个 assistant_text/tool_use 时间戳 → 下一个 user_message 时间戳，2s–1h 有效（与 Claude 口径一致）。
- **first_prompt**：第一条非注入 user_message 前 200 字符。
- **会话摘要**：Codex 无内置 summary 行（Claude 有 `type:summary`），留空由 facet 提取补足。
- **分支**：rollout 文件是线性追加（含 `thread_rolled_back` 事件但无树状分支），不需要 Claude 那套 parentUuid 分支去重。
