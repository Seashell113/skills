---
name: codex-quota-inspector
description: Use this skill whenever the user asks to check local Codex quota, Codex rate limits, ChatGPT reset credits, free reset chances, 5-hour or 7-day usage, or asks for a combined quota snapshot. It provides safe read-only workflows with separate entrypoints for Codex rate limits and ChatGPT reset credits, and it must avoid printing access_token, refresh_token, account_id, id_token, or other credential values.
---

# Codex 额度查询

用这个 skill 从用户本机只读查询 Codex/ChatGPT 额度信息，并避免暴露凭据。

这个 skill 有三个入口：

- `quota`：读取 `~/.codex/sessions` 下最新的 Codex `rate_limits` 事件。
- `credits`：只在内存中读取 `~/.codex/auth.json` 的必要认证字段，并请求 ChatGPT 免费重置机会接口。
- `all`：同时执行 `quota` 和 `credits`，输出聚合快照。

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
```

可选参数：

```bash
python3 scripts/codex_quota_probe.py all --timezone Asia/Shanghai
python3 scripts/codex_quota_probe.py quota --json
```

## 输出规范

`quota` 输出：

- `plan_type`
- 5 小时额度：used、remaining、reset_at
- 7 天额度：used、remaining、reset_at
- 来源 session 文件路径

`credits` 输出：

- `available_count`
- 每个 credit 的 `status`、`granted_at`、`expires_at`、`used_at`
- 接口名称，但不输出请求 header 或认证字段

`all` 同时输出以上两部分。

如果 session 事件只提供 `used_percent`，就按百分比输出 used 和 remaining。不要编造绝对次数。

## 手动兜底流程

如果内置脚本无法运行：

1. 按 JSON Lines 解析 `~/.codex/sessions/**/*.jsonl`。
2. 选择最新一条包含 `payload.rate_limits` 的事件。
3. 提取 `plan_type`、`primary` 和 `secondary`。
4. 将 `primary.window_minutes == 300` 识别为 5 小时窗口，将 `secondary.window_minutes == 10080` 识别为 7 天窗口。
5. 将 `resets_at`、`reset_at` 或等价时间字段转换为本地时间。
6. 查询免费重置机会时，只把 `tokens.access_token` 和 `tokens.account_id` 读入变量，然后请求：

```text
GET https://chatgpt.com/backend-api/wham/rate-limit-reset-credits
Authorization: Bearer <access_token>
OpenAI-Account: <account_id>
```

7. 只输出 `available_count`，以及每个 credit 的 `status`、`granted_at`、`expires_at`、`used_at`。

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
- 普通额度：`...` 最新 `payload.rate_limits` 事件
- 免费重置机会：`~/.codex/auth.json` 中必要认证字段 + `rate-limit-reset-credits` 接口

未输出 `access_token`、`refresh_token`、`account_id` 等敏感值。
```
