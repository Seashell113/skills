# Runtime Home 与状态协议

## 路径解析

持久数据不得写回 Skill 安装目录。

1. 如果设置 `GANCAO_SKILLS_HOME`，使用其值作为根目录。
2. 否则 macOS/Linux 使用 `~/.gancao-skills`，Windows 使用 `%USERPROFILE%\.gancao-skills`。
3. Skill 目录固定为 `<skills-home>/web-ai-daily-paper/`。

标准结构：

```text
web-ai-daily-paper/
├── config/
│   └── profile.yaml
├── state/
│   ├── events.jsonl
│   ├── feedback-inbox.jsonl
│   ├── feedback-cases.jsonl
│   └── last-run.json
├── cache/
└── runs/
    └── <run-id>/
```

首次运行时可从 bundled `templates/profile.yaml` 复制默认 profile。不要覆盖用户已经修改的配置。

## Run ID 与目录

使用含时区的 ISO 时间生成 run id，并替换不适合作为文件名的冒号，例如 `2026-07-16T082800+0800`。

每次 run 写入：

- `candidates.json`
- `evidence.json`
- `selected.json`
- `rejected.json`
- `review.json`
- `review.md`
- `report.txt`
- `run-summary.json`

先写本次 run 的完整产物，再更新全局状态。中途失败的目录保留并标记 `incomplete`，便于复盘。

## 模式与状态写入

| 模式 | 写 runs | 更新 events | 更新 last-run | 自动投递 |
| --- | --- | --- | --- | --- |
| `dry-run` | 是 | 否 | 否 | 否 |
| `replay` | 是 | 否 | 否 | 否 |
| 手动正式生成 | 是 | 报告 commit 后 | 是 | 仅用户明确授权 |
| cron 正式生成 | 是 | 报告 commit 后 | 是 | 由平台在最终响应后执行 |

`last-run.json` 保存的是 `report_committed`，不是 `delivered`。Hermes cron 在 Agent 返回最终响应后投递，Skill 无法事务式确认最终发送。

## Event history

`events.jsonl` 每行一个已报道 event/milestone，至少包含：

- `event_key`、`milestone`、标题和主 URL。
- `event_time`、`first_reported_at`、`last_reported_at`。
- `run_id` 和栏目。

保留至少 30 天。清理时按事件时间和 milestone 保留最近记录，不删除仍可能产生后续进展的安全/政策事件。

## Feedback state

- `feedback-inbox.jsonl`：只追加原始反馈、最小定位上下文和接收时间。
- `feedback-cases.jsonl`：结构化归因、状态、回归测试、解决方案和版本。

用户原话不可被结构化字段覆盖。需要修正归因时追加新版本或状态变化。

## 完整性与恢复

- `run-summary.json` 包含模式、时间窗口、来源成功/失败、候选数、入选数、Review 状态和 `status`。
- 只有 candidates、evidence、selected、rejected、review、report 均已生成，`status` 才能为 `report_committed`。
- runtime home 不可写时，允许在当前会话返回草稿，但不得更新历史、不得声称完成正式运行，也不得触发自动投递。
- 手动重发使用已有 `report.txt`，不重新采集，不新增 event milestone。

## 凭据和隐私

- profile、state、runs 和 cache 均不得包含 API Key、Token、DingTalk chat id 等凭据。
- 请求/错误记录应删除认证 Header 和带密钥的 query 参数。
- `BESTBLOGS_API_KEY`、`ANYSEARCH_API_KEY` 只从安全环境变量读取；缺失时走降级路径。
