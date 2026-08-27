---
name: agent-usage-insights
description: >-
  基于本机 Codex 会话生成严格事件窗口的私有使用洞察报告，支持固定 HTML、机器可读指标、当前 Agent 语义分析、相邻窗口比较，以及 Codex 到 ChatGPT 的精确 task ID 调度链复盘。用户提到“看下我的使用情况”“跑 Codex insights”“上次盘点截止到什么时候”“分析最近 agent 记录”“比较两个阶段”“Codex 调度 ChatGPT 是否有效”时使用。
---

# Agent Usage Insights

生成可复现、可解释的 Codex 使用报告。默认中文、本地只读、无网络分析。

## 与 insights-aggregator 的分工

- 本 skill：单 Codex 的低成本确定性报告、严格时间窗、当前 Agent 有界语义分析、精确 ChatGPT 调度链复盘。
- `insights-aggregator`：Claude Code + Codex 的完整跨工具采集、批量 facet 与综合 HTML。

用户只需要快速盘点 Codex 或核对某个阶段时优先本 skill；需要全量 Claude Code/Codex 双工具比较时使用 `insights-aggregator`。

## 隐私与授权

- 本机历史是私人数据，只读使用，不上传原始会话或报告。
- 默认不读取、保留或输出 transcript 正文；语义分析需要下钻时只做有界抽样，不在对话中展示原话。
- 默认由当前 Agent 本地分析，不调用 OpenAI API。只有用户明确要求 API 分析，且显式确认发送范围后，才允许外发。
- 不重新下载 ChatGPT 全量导出；已有导出不覆盖、不过期假装新鲜。

## 先确定时间口径

### 查询上次盘点截止时间

优先检查既有报告中的 `analysis_window.end` 或 HTML 页首的半开窗口，不用文件 mtime 冒充截止时间。若旧报告没有显式窗口，只能说明其统计范围不可严格复现。

### 新建阶段窗口

使用 complete-day 半开区间 `[start, end)`，明确 IANA 时区。例如上海时间 42 个完整自然日：

```text
[2026-07-16T00:00:00+08:00, 2026-08-27T00:00:00+08:00)
```

两个阶段对比时使用相邻、等长窗口。当前线程在窗口终点之后仍有活动时，不计入本窗。

严格窗口规则：

- 先按 `session_meta.payload.id` 确定物理会话拥有的事件，排除 fork/subagent 导入的外来历史。
- 再按 owned event 时间戳过滤；起点纳入，终点排除。
- 读取数据库中的全部线程；`created_at/updated_at` 不用于候选预筛，也不能决定事件归属。
- 默认排除 `subagent` 与 `automation`；历史使用盘点通常加 `--include-archived`，当前归档状态不能反推历史活动。
- 窗口 Token 只使用 owned `token_count` 的累计差分。缺失时标为不可观测，不用线程全生命周期累计值或 0 替代。

## 生成固定报告

优先运行内置 helper：

```bash
bash ~/.codex/skills/agent-usage-insights/scripts/run-codex-report.sh \
  --start 2026-07-16T00:00:00 \
  --end 2026-08-27T00:00:00 \
  --timezone Asia/Shanghai \
  --include-archived \
  --output ~/.codex/insights/codex-20260716-20260827.html \
  --metrics-output ~/.codex/insights/codex-20260716-20260827.metrics.json
```

helper 按顺序定位：

1. `AGENT_USAGE_INSIGHTS_TOOL_DIR`
2. `$CODEX_HOME/tools/agent-usage-insights` 本机运行副本
3. `$HOME/workspace/ai/ai-workspace/system/tools/agent-usage-insights`
4. 旧版 `tools/agent-usage-insights` 路径

无需 `.venv`；helper 会选择可用 Python，并把工具的 `src` 加入 `PYTHONPATH`。
底层工具的主真源仍是 `ai-workspace/system/tools/agent-usage-insights`；本机安装 Skill 时可把已验证版本同步到 `$CODEX_HOME/tools/agent-usage-insights`，避免当前 `ai-workspace` 工作树停在其他分支时误用旧解析器。

可用环境变量：

- `AGENT_USAGE_INSIGHTS_SNAPSHOT_MANIFEST`
- `AGENT_USAGE_INSIGHTS_START` / `AGENT_USAGE_INSIGHTS_END` / `AGENT_USAGE_INSIGHTS_TIMEZONE`
- `AGENT_USAGE_INSIGHTS_INCLUDE_ARCHIVED=1`
- `AGENT_USAGE_INSIGHTS_ALLOW_UNFROZEN_ARCHIVED=1`：仅在 manifest 漏收归档文件且接受不可完全复现时使用
- `AGENT_USAGE_INSIGHTS_INCLUDE_INTERNAL=1`
- `AGENT_USAGE_INSIGHTS_METRICS`
- `AGENT_USAGE_INSIGHTS_CHATGPT_TASK_IDS`：仅含精确 task ID 的本地 JSON 列表
- `AGENT_USAGE_INSIGHTS_USE_ANALYSIS=1`：仅在确认分析文件属于同一窗口时启用

若有冻结 manifest，优先传入 `--snapshot-manifest`。工具会核验 schema、parser 身份、数据库与 rollout 字节前缀；已声明来源缺失或漂移时失败关闭。manifest 未覆盖的归档文件默认不读取；确需补入时同时传 `--include-archived --allow-unfrozen-archived`，并在结论中保留不可完全复现边界。

## 当前 Agent 语义洞察

需要深入洞察时：

1. 生成 `llm-context.json`，默认不含 transcript。
2. 先复用已有分类、facet、验证索引与报告，不重复阅读充分分类的会话。
3. 只为新问题、反例或精确调度链下钻高信号样本。
4. 连续两批抽样没有改变假设或结论时停止。
5. 按 `references/analysis-shape.md` 生成独立分析 JSON，再显式传给 `--analysis-input` 重渲染。

不要把会话数、Token、测试数、文档数或“调用了另一个模型”直接解释成效果。至少分别判断：

- 有效发现或已采纳结论
- 独立审查增益
- 人工注意力与转交成本
- 可复用资产的后续复利

## Codex 到 ChatGPT 的精确调度链

只接受精确 task ID 证据：

1. 从 Codex owned event 中提取 `create_thread` 的调用与结果。
2. 记录结果返回的 ChatGPT task ID。
3. 仅用同一 ID 关联后续 `read_thread`、`wait_threads` 或继续消息。
4. 标题相似、时间接近、项目相同都不能作为自动关联依据。
5. 无法观测 ChatGPT 内部模型档位、Token、独立思考过程或用户是否实际采纳时，明确列为不可观测。

## 验证与交付

- 运行仓库测试；至少覆盖微秒窗口边界、DST 歧义、跨窗会话、导入历史、旧格式 subagent、subagent live tail、归档线程、混合 Token 事件和快照数据库/rollout 完整性。
- 检查 HTML 页首的窗口、时区、Token 覆盖率、来源快照和缺失来源。
- 浏览器检查桌面与窄屏，无明显溢出；语义 prompt 的复制按钮存在。
- 最终给出报告路径、分析是否联网、验证结果、数据边界和不可观测项。

改进本 skill 或底层工具时，同时使用 `skill-creator`；先做失败测试，再实现并跑真实冻结快照烟测。
