---
name: codex-quota-inspector
description: Use this skill whenever the user asks to check local Codex quota, Codex rate limits, ChatGPT reset credits, free reset chances, 5-hour or 7-day usage, or asks for a combined quota snapshot. It provides safe read-only workflows with separate entrypoints for Codex rate limits and ChatGPT reset credits, and it must avoid printing access_token, refresh_token, account_id, id_token, or other credential values.
---

# Codex 额度查询

用这个 skill 从用户本机只读查询 Codex/ChatGPT 额度信息，并避免暴露凭据。

这个 skill 有四个入口：

- `quota`：默认先请求 ChatGPT/Codex usage API 查询普通额度；API 失败才回落到本地 `~/.codex/sessions` 快照。
- `credits`：只在内存中读取 `~/.codex/auth.json` 的必要认证字段，并请求 ChatGPT 免费重置机会接口。
- `all`：同时执行 `quota` 和 `credits`，输出聚合快照。
- `diagnose`：只读本地 `~/.codex/sessions`，输出最近 `rate_limits` 事件的非敏感原始字段。

## 安全规则

- 把 `~/.codex/auth.json` 当作敏感文件处理。不要打印 `access_token`、`refresh_token`、`id_token`、`account_id`、Authorization header、cookie 或原始 auth JSON。
- 如果 `auth.json` 结构不符合预期，只打印 JSON 顶层字段名和 `tokens` 子字段名，不打印字段值。
- 不要对整个 `~/.codex` 做宽泛 `rg` 或全文 grep。使用结构化 JSON 解析，并且只定向遍历 `~/.codex/sessions`。
- 不要写入 `~/.codex`，不要修改 session 或 auth 文件。
- 时间按用户本地时区输出；如果时区不明确，使用系统本地时区并说明。
- 除非用户明确要求英文，最终答复使用简短中文。

## 推荐命令

在当前 skill 目录下运行内置脚本：

```bash
python3 scripts/codex_quota_probe.py all
```

支持的模式：

```bash
python3 scripts/codex_quota_probe.py quota
python3 scripts/codex_quota_probe.py credits
python3 scripts/codex_quota_probe.py all
python3 scripts/codex_quota_probe.py diagnose --json
```

可选参数：

```bash
python3 scripts/codex_quota_probe.py all --timezone Asia/Shanghai
python3 scripts/codex_quota_probe.py quota --json
python3 scripts/codex_quota_probe.py quota --source live
python3 scripts/codex_quota_probe.py quota --source local
```

## 输出规范

`quota` 输出：

- 来源类型：`live_api` 或 `local_snapshot`
- `plan_type`
- live API 查询时间，或 local 最新 `rate_limits` 事件时间和来源 session 文件路径
- 5 小时额度：used、remaining、reset_at
- 7 天额度：used、remaining、reset_at

`credits` 输出：

- `available_count`
- 每个 credit 的 `status`、`granted_at`、`expires_at`、`used_at`
- 接口名称，但不输出请求 header 或认证字段

`all` 同时输出以上两部分。

`diagnose` 输出最近几条 `payload.rate_limits` 事件的非敏感字段：

- 事件时间和来源 session 文件路径
- 每个窗口的 `window_minutes`
- 原始 `used_percent` / `remaining_percent` / reset 字段
- 当前脚本解析后的 5 小时和 7 天结果

如果只提供 `used_percent`，就按百分比输出 used，并用 `100 - used_percent` 计算 remaining。不要编造绝对次数。
如果缺少真实 `used_percent` 或 `resets_at/reset_at`，必须输出“无法确认”和缺失原因，不要用 `0%/100%` 或 `当前时间 + window_minutes` 兜底。

## 手动兜底流程

如果内置脚本无法运行：

1. 普通额度优先请求：

```text
GET https://chatgpt.com/backend-api/wham/usage
Authorization: Bearer <access_token>
OpenAI-Account: <account_id>
```

2. 从 live 响应提取 `plan_type`、`rate_limit.primary_window`、`rate_limit.secondary_window`，将 `limit_window_seconds` 转为分钟，将 `reset_at` 转成本地时间。
3. live API 失败时，才按 JSON Lines 解析 `~/.codex/sessions/**/*.jsonl`。
4. local 选择最新一条包含 `payload.rate_limits` 的事件。
5. local 提取 `plan_type`、`primary` 和 `secondary`；也兼容 `payload.type == "codex.rate_limits"` 时 `plan_type` 在 `payload` 顶层。
6. 优先按 `window_minutes` 识别窗口：`300` 是 5 小时，`10080` 是 7 天；不要假设 `primary` 一定是 5 小时、`secondary` 一定是 7 天。
7. 如果只有 `used_percent`，用 `100 - used_percent` 计算 remaining；如果用户反馈与 UI 不一致，先运行 `diagnose` 查看原始 `used_percent` / `remaining_percent`，不要凭猜测改单位。
8. 将 `resets_at`、`reset_at` 或等价时间字段转换为本地时间；字段缺失时输出未知，不要自行推导。
9. 如果结果和 Codex UI 侧边栏不一致，默认信 live API/UI；local 只作为历史快照和排障证据。
10. 查询免费重置机会时，只把 `tokens.access_token` 和 `tokens.account_id` 读入变量，然后请求：

```text
GET https://chatgpt.com/backend-api/wham/rate-limit-reset-credits
Authorization: Bearer <access_token>
OpenAI-Account: <account_id>
```

11. 只输出 `available_count`，以及每个 credit 的 `status`、`granted_at`、`expires_at`、`used_at`。

## 回复模板

```markdown
当前结果：

**Codex 普通额度**
- 套餐类型：`...`
- 5 小时额度：已用 `...`，剩余 `...`，重置时间 `...`
- 7 天额度：已用 `...`，剩余 `...`，重置时间 `...`

**免费重置机会**
- 当前可用次数：`...`
- 明细：
  - 状态 `...`，发放时间 `...`，过期时间 `...`，使用时间 `...`

数据来源：
- 普通额度：live API `...`，或 local snapshot `...`
- 免费重置机会：`~/.codex/auth.json` 中必要认证字段 + `rate-limit-reset-credits` 接口

未输出 `access_token`、`refresh_token`、`account_id` 等敏感值。
```
