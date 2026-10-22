# Facet 提取提示词

用途：对单个会话 transcript 提取结构化语义 facets。由主 agent 为每个待提取会话派发一个子 agent（并行），子 agent 读取 transcript 文件后按本提示词分析，并将结果 JSON 直接写入指定的 facet 缓存路径。

对 Claude 官方 /insights 源码的有意增强（非偏差）：
- `claude_helpfulness` 改名 `agent_helpfulness`（工具中立）；
- 新增 `user_instructions_to_agent` 字段（源码类型里有但提示词未要求，导致从未被填充；这里补上，使配置建议有据可依）；
- 新增 `agent` 字段标记来源工具。

---

## PROMPT（向子 agent 下发时，替换 {{...}} 占位符）

分析这份 AI 编程助手的会话记录，提取结构化 facets。

先用 Read 工具读取 transcript 文件：{{transcript_path}}

关键准则：

1. **goal_categories**（目标类别）：只统计**用户明确要求**的事。
   - 不要统计 agent 自主探索的工作
   - 不要统计 agent 自己决定做的事
   - 只在用户说"帮我…""请…""我需要…""我们来…"（中英文均算）时计数
   - 允许的类别 key：debug_investigate（调试排查）, implement_feature（实现功能）, fix_bug（修Bug）, write_script_tool（写脚本/工具）, refactor_code（重构）, configure_system（配置系统）, create_pr_commit（提交PR）, analyze_data（数据分析）, understand_codebase（理解代码库）, write_tests（写测试）, write_docs（写文档）, deploy_infra（部署运维）, warmup_minimal（预热/极简会话）

2. **user_satisfaction_counts**（满意度）：只依据用户的**显式信号**判断。
   - "太棒了""perfect!" → happy；"可以""没问题""thanks""looks good" → satisfied
   - 不抱怨直接继续下一件事（"好，接下来…"）→ likely_satisfied
   - "不对""重新来""that's not right" → dissatisfied；"算了""this is broken" → frustrated
   - 允许的 key：frustrated, dissatisfied, likely_satisfied, satisfied, happy, unsure, neutral, delighted

3. **friction_counts**（摩擦）：具体指出哪里出了问题。
   - misunderstood_request：误解了需求；wrong_approach：目标对但方法错
   - buggy_code：代码跑不对；user_rejected_action：用户拒绝了某次工具调用
   - excessive_changes：过度工程/改动范围过大
   - 其余允许的 key：claude_got_blocked, user_stopped_early, wrong_file_or_location, slow_or_verbose, tool_failed, user_unclear, external_issue

4. 如果会话非常短或只是预热，goal_category 用 warmup_minimal。

5. **user_instructions_to_agent**：捕捉用户对 agent **工作方式**提出的可复用指令（如"先不要改代码""用中文回复""写完先跑测试"），跳过一次性的任务内容本身。没有则给空数组。

分析完成后，用 Write 工具将**纯 JSON 对象**（不带 markdown 代码块标记、不带任何解释文字）写入：{{facet_path}}

JSON 必须严格符合以下 schema：

{
  "agent": "{{agent}}",
  "session_id": "{{session_id}}",
  "_user_message_count": {{user_message_count}},
  "_parser_schema_version": {{parser_schema_version}},
  "underlying_goal": "用户根本上想达成什么（中文）",
  "goal_categories": {"类别key": 次数},
  "outcome": "fully_achieved|mostly_achieved|partially_achieved|not_achieved|unclear_from_transcript",
  "user_satisfaction_counts": {"等级key": 次数},
  "agent_helpfulness": "unhelpful|slightly_helpful|moderately_helpful|very_helpful|essential",
  "session_type": "single_task|multi_task|iterative_refinement|exploration|quick_question",
  "friction_counts": {"摩擦key": 次数},
  "friction_detail": "一句话描述摩擦（中文），无则空字符串",
  "primary_success": "none|fast_accurate_search|correct_code_edits|good_explanations|proactive_help|multi_file_changes|good_debugging",
  "brief_summary": "一句话（中文）：用户想要什么、是否得到了",
  "user_instructions_to_agent": ["具体指令（保留用户原话语言）", ...]
}

注意：JSON 的 key 和枚举值保持英文（供程序消费）；`underlying_goal`、`friction_detail`、`brief_summary` 等自由文本字段用中文写。`_user_message_count` 和 `_parser_schema_version` 原样填入给定数字（用于检测会话续写和解析口径升级后的 facet 过期），不要自己数或猜版本。

写完文件后，你的最终回复只需：`done {{session_id}}`（若 transcript 不可读则回复 `failed {{session_id}}: 原因`）。

## 可选：历史知识与基建效果候选

仅在本轮范围包含知识提取或基建效果分析时，在上述原有 facet 上追加下列可选字段；不替代任何原字段，不为缺少新字段而重跑旧 facet。已有任务证据可以通过 evidence bundle 进入聚合，直接阅读不伪装成 facet。

```json
{
  "knowledge_candidates": [
    {"title": "业务/项目/技术/组织经验", "finding": "有来源的事实或判断", "evidence": ["source_id"], "reuse": "适用场景", "status": "候选/已采纳/已验证等实际状态", "limits": "证据边界"}
  ],
  "infrastructure_observations": [
    {"name": "实际使用的 Agent/subagent/Skill/model/tool", "purpose": "为何使用", "observed_result": "可观察的结果", "alternative_and_cost": "可比方案及实际成本；不足写未知", "decision": "保留/调整/待验证的建议", "next_check": "需要补什么证据", "evidence": ["source_id"], "limits": "归因限制"}
  ],
  "sources": [{"id": "source_id", "title": "来源标题", "session_id": "原会话ID", "locator": "已给定片段或原文行号", "summary": "支持的事实"}]
}
```

来源 id 应含 session_id 或其他稳定身份，避免跨会话重名。记录出处与采纳状态是两件事：指令被读取不证明已使用，出现工具调用不证明有效，完成测试不证明生产验收，建议不等于用户决定。模型、推理强度和 subagent 数量本身不能证明成本收益。没有价格、token、时长、返工或同条件替代证据时，相关成本与因果写未知。

只读取已给定 transcript 或冻结证据包。摘要不足以支撑关键判断时，先按 session_id 与 locator 只下钻相关原文片段；注明本轮读取范围，不能据局部片段声称完整复核了长会话。原文不可达时保留候选与未知，不能自行扩大到全历史扫描。
