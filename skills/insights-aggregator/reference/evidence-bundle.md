# 复用已准备的证据

已有任务摘要、有限原文核验和确定性统计时，可绕开 collect 与 facet 重提，继续使用原 aggregate / section / render 流程。它是有选择的证据输入，不代表全量采集或新完成的 facet。

使用独立的 `--home`，避免混入上一轮的 section JSON；聚合不读取会话缓存，不调用模型，不自动删除旧 section：

```bash
python3 scripts/aggregate.py --evidence-bundle /private/path/bundle.json --home /private/path/run
# 按 prompts/insight-sections.md 生成原 7/9 个 section，以及请求范围内的两个可选 section
python3 scripts/render.py --home /private/path/run
```

`--evidence-bundle` 模式以 bundle 的冻结时间和范围为准，不使用 `--days` 或 `--as-of` 重筛。标准缓存流程的窗口语义不变。

最小结构（仅演示结构，非真实数据）：

```json
{
  "schema_version": 1,
  "generated_at": "2026-10-01T00:00:00+00:00",
  "window": {"days": 30, "cutoff": "2026-09-01T00:00:00Z", "as_of": "2026-10-01T00:00:00Z"},
  "selection": {
    "method": "按任务主题选择并核验相关片段",
    "selected_sessions": 1,
    "facets_extracted": 0,
    "direct_read_sessions": 1,
    "limits": "目的性选样；不推断全量频率",
    "scope_note": "可补充助手消息数、统计口径与冻结范围"
  },
  "metrics": {
    "combined": {"total_sessions": 1, "sessions_with_facets": 0, "total_messages": 3, "git_commits": null},
    "by_agent": {"codex": {"total_sessions": 1, "sessions_with_facets": 0, "total_messages": 3}}
  },
  "sources": [{"id": "S1", "title": "合成任务", "session_id": "example", "locator": "冻结片段 L10-L20", "summary": "片段支持的事实"}],
  "knowledge_candidates": [],
  "infrastructure_observations": []
}
```

`metrics.combined` 与每个 `by_agent` 组接受原 `aggregate_group` 的字段子集；常用字段：`date_range:{start,end}`、`total_sessions`、`sessions_with_facets`、`total_messages`（仅用户消息）、`total_duration_hours`、`days_active`、`git_commits`、`total_lines_added`、`total_lines_removed`、`tool_counts`、`tool_category_counts`、`models`、`reasoning_effort`。模型/强度计数必须沿用原单位，不能由任务标签猜测。

未知数值省略或填 `null`，显式 `0` 仅表示已核实为零。未知字典/列表用空显示容器，但输出的 `available_metrics` 只记录输入中非 null 的字段；分析时必须看这份清单，不能把空显示容器当零。满意度未知不补 0%；没有时长/commits/模型记录就显示未知或暂无数据。`sessions_with_facets` 只计真实完成的原 facet；直接阅读计入 `selection.direct_read_sessions`，顶部显示直接阅读任务数。

若有可靠跨工具统计，可选传 `metrics.cross_tool`（沿用原 `overlap`、`handoffs:{direction_counts,examples}`、`project_tool_matrix` 结构）。未提供时 `cross_tool_metrics_available:false`，不据空容器推断无接力/并行。单一工具不生成跨工具对比。

知识候选与基建观察沿用两个可选 section 的条目结构，见 [section 提示词](../prompts/insight-sections.md)。`sources[].id` 必须唯一，每个来源必须带 `locator`。来源是可定位证据，`status` 是采纳/验证状态，两者独立；读取某份材料不能自动成为已采纳或已验证。报告将 source id 链接到本页来源区，locator 作为文本显示，不执行文件协议或外链。

输入和报告留在私密本地目录，权限由聚合/渲染设为 0600。公开源码只保留合成测试，不能带入真实会话、公司内容或报告。

正常 facet 缓存路径在聚合时将本地 source id 转为 `facet/<agent>/<session_id>/<local_id>`（各部分 URL 编码），并同步候选条目的 evidence 引用；缓存文件保持原样。同一 facet 内重复 id 会明确拒绝，两个会话各自的 `S1` 不会误链。bundle 的 source id 已要求全局唯一，沿用原值。
