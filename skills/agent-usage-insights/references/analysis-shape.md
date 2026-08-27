# 当前 Agent 洞察结构

固定 HTML 提供确定性统计；独立语义报告使用当前 Agent 对已有分类和有界样本做判断。推荐 JSON 结构：

```json
{
  "schema_version": "codex-insights-agent-analysis/v2",
  "model": "current-codex-agent-session",
  "evidence_scope": {
    "window": "[start, end)",
    "timezone": "Asia/Shanghai",
    "snapshot_id": "...",
    "reviewed_existing": 0,
    "new_samples": 0,
    "stop_reason": "two_batches_without_material_change"
  },
  "insights": {
    "at_a_glance": {},
    "project_areas": {},
    "interaction_style": {},
    "what_works": {},
    "friction_analysis": {},
    "suggestions": {},
    "on_the_horizon": {}
  },
  "effect_dimensions": {
    "accepted_findings": {},
    "independent_review_gain": {},
    "human_attention_cost": {},
    "reusable_asset_compounding": {}
  },
  "unobservable": []
}
```

质量要求：

- 统计、事实判断、用户明确采纳、推断和不可观测项分开。
- 推荐必须指向观察到的工作模式，不给通用“多用自动化”建议。
- 不用单一效率分数压平四个效果维度。
- 会话数、Token、工具调用数只作为活动量证据，不能直接证明价值。
- 精确 ChatGPT 调度链只用 task ID；标题或时间近似不能升级为证据。
- 抽样连续两批不再改变核心假设或结论时停止，记录停止理由。
- 不展示原始对话；必要证据用主题化摘要和聚合计数表达。
