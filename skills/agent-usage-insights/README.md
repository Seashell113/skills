# agent-usage-insights

> 为 Codex 本地使用历史生成严格事件窗口的私有报告。适合快速阶段盘点，也支持当前 Agent 的有界语义分析和 Codex→ChatGPT 精确 task ID 调度链复盘。

## 特点

- 微秒精度 `[start, end)` 半开事件窗口，显式时区并拒绝 DST 歧义
- 全库候选后按 owned event 归窗，排除 fork/subagent 导入历史与旧格式内部线程
- 校验冻结数据库、parser 和 rollout；未冻结归档来源只能显式启用并披露复现边界
- 窗口 Token 使用事件累计差分和混合格式对账；缺失保持不可观测
- 默认本地、无网络、无 transcript 正文输出
- 输出自包含 HTML、机器可读指标和可选 LLM context

## 运行示例

```bash
bash ~/.codex/skills/agent-usage-insights/scripts/run-codex-report.sh \
  --start 2026-07-16T00:00:00 \
  --end 2026-08-27T00:00:00 \
  --timezone Asia/Shanghai \
  --include-archived \
  --output ~/.codex/insights/codex-20260716-20260827.html \
  --metrics-output ~/.codex/insights/codex-20260716-20260827.metrics.json
```

helper 优先使用 `AGENT_USAGE_INSIGHTS_TOOL_DIR`，其次使用 `$CODEX_HOME/tools/agent-usage-insights` 本机运行副本，再回退到个人 `ai-workspace/system/tools/agent-usage-insights`。底层工具主真源仍在 `ai-workspace`；本机运行副本用于避免当前工作树停在其他分支时误用旧解析器。

## 与 insights-aggregator 的区别

本 skill 面向单 Codex、低成本和严格窗口。需要 Claude Code + Codex 的完整跨工具 facet 与综合报告时，使用仓库中的 `insights-aggregator`。

## 目录

| 路径 | 用途 |
| --- | --- |
| `SKILL.md` | Agent 主指令 |
| `scripts/run-codex-report.sh` | 报告 helper |
| `references/analysis-shape.md` | 当前 Agent 分析 JSON 结构与质量要求 |
| `agents/openai.yaml` | Codex 展示元数据 |
