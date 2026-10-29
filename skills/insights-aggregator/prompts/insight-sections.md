# 洞察 Section 提示词

用途：基于 `work/insight-context.md`（aggregate.py 产出）生成各洞察 section。

执行方式：
- 第一阶段：下列 9 个 section **并行**派发子 agent。每个子 agent 读取 `work/insight-context.md`，按对应提示词生成，并将纯 JSON 写入 `work/insights/{section_name}.json`。
- 第二阶段（串行）：全部完成后，再按文末 `at_a_glance` 提示词生成总览（其上下文 = insight-context.md + 各 section 产出要点），写入 `work/insights/at_a_glance.json`。
- 以主控确定的本期分析范围为准。仅有零星残留记录的工具不强行分析；输入只保留本期分析工具，`agents_present` 只有一个时跳过 `tool_comparison`、`cross_tool_workflows` 和总览的工具分工。

统计范围与语义读取范围可能不同：样本中的频率、任务类别、满意度不能外推到全部会话。保留原有分析章节和阅读节奏；独立知识盘点按 [盘点协议](../reference/knowledge-inventory.md) 输出，报告只选有启发且有据的条目，不承担穷举和入库管理。

正文先给判断，再用具体事件说明它为什么成立、对下一次工作有什么用。成果写实际改善，摩擦说明原因和后果，基建分析说明已经解决什么及仍需验证什么；避免同一案例在各节反复得出相同结论。统计方法集中交代，影响某条结论的条件留在该条。已采用的机制不再当作新建议；建议写清下一次试做及观察结果，由主控沿用已有上下文承担执行责任，不把它改成要求用户重复声明的提示词。篇幅按信息价值决定，不凑条数、不用泛泛赞美替代判断。

整合时按章节职责检查信息增量：亮点呈现结果与关键取舍，摩擦解释返工机制，建议说明现在优先改变的动作，未来部分提出跨场景的新认识。重复使用案例时只补新的关系，已交代的背景用来源或章节链接承接。未来方向可以是有依据的候选解释，不写成个人画像或已证明的因果，也不把每节都收尾成“下一次自然任务再验证”。

知识精选保留能改变判断的辨识细节，例如真实 API 的缺失、分母变化、诊断数值和后续纠正；泛化成“注意验收、完善上下文”会丢失经验。已有独立盘点时填写对应条目身份，供读者直接下钻。基建评价给出当前取舍：照常使用、修正具体缺口、保持暂停或暂不改变；未知长期收益不抹去已确认的局部交付，也不自动产生新待办。图表回答工作重心或配置分布等可观测问题，不承担没有结果链支撑的效果排名。

每个子 agent 的统一收尾要求（附加到每个提示词之后）：

> 先用 Read 工具读取使用数据：{{context_path}}。然后用 Write 工具将**纯 JSON 对象**（不带 markdown 代码块标记）写入 {{output_path}}。所有叙述性文字（narrative/description/title 等的值）用中文写，JSON 的 key 保持英文。写完后最终回复只需：`done {{section_name}}`。

---

## 1. project_areas（项目领域）

分析这份 AI 编程助手使用数据，识别用户的项目领域。

输出 JSON schema：
{
  "areas": [
    {"name": "领域名", "session_count": 数字, "tools_used": ["claude-code", "codex"], "description": "2-3 句话：做了什么、agent 是怎么被使用的。"}
  ]
}

给出 4-5 个领域。跳过 agent 的内部操作类会话。标注每个领域用了哪些工具。

## 2. interaction_style（交互风格）

分析这份使用数据，描述用户与 AI 编程工具的交互风格。

输出 JSON schema：
{
  "narrative": "2-3 段，分析用户是**如何**与 agent 协作的。用第二人称'你'。描述模式：是快速迭代还是先写详细规格？频繁打断还是放手让 agent 跑？不同工具间风格是否有差异？给出具体例子。关键洞察用 **加粗**。",
  "key_pattern": "一句话总结最有辨识度的交互模式"
}

## 3. what_works（做得好的地方）

分析这份使用数据，找出该用户用得好的地方。用第二人称（"你"）。

输出 JSON schema：
{
  "intro": "1 句话铺垫",
  "impressive_workflows": [
    {"title": "短标题（3-6 个词）", "description": "2-3 句话描述这个出色的工作流或方法。用'你'而不是'用户'。"}
  ]
}

给出 3-4 个出色的工作流，以数据支撑为准。

## 4. friction_analysis（摩擦分析）

分析这份使用数据，找出该用户的摩擦点。用第二人称（"你"）。

输出 JSON schema：
{
  "intro": "1 句话总结摩擦模式",
  "categories": [
    {"category": "具体的类别名", "description": "1-2 句话解释这类摩擦、可以怎么做得不同。", "examples": ["带后果的具体例子", "另一个例子"]}
  ]
}

给出 3-5 个摩擦类别、各配 2-3 个例子——条数按数据实际支撑量伸缩：摩擦信号多就充分展开（这是本报告对用户最有价值的部分），信号少就少写，**宁缺毋滥、不为凑数编造**。如果摩擦在工具间有明显差异，指出发生在哪个工具。

## 5. suggestions（改进建议）

分析这份使用数据并给出改进建议。

功能参考（features_to_try 从中选取，标注适用工具）：
1. **MCP Servers**（双工具通用）：把 agent 接到外部工具/API。Claude Code：`claude mcp add <name> -- <cmd>`；Codex：`~/.codex/config.toml` 的 `[mcp_servers]`
2. **自定义 Skills / 斜杠命令**（Claude Code）：把可复用工作流写成 `.claude/skills/<name>/SKILL.md`，用 /name 调用
3. **Hooks**（Claude Code）：在 `.claude/settings.json` 配置生命周期事件自动执行的 shell 命令
4. **Headless / 非交互模式**（双工具通用）：`claude -p "..."` / `codex exec "..."`，用于 CI 和脚本化
5. **Task agents / 子代理**（双工具通用）：并行探索与实现的扇出
6. **AGENTS.md / CLAUDE.md**（双工具通用）：项目级持久指令——Codex 读 AGENTS.md，Claude Code 读 CLAUDE.md（可 @引用 AGENTS.md）

输出 JSON schema：
{
  "config_additions": [
    {"addition": "建议追加的具体规则文本", "target_file": "CLAUDE.md|AGENTS.md|both", "why": "1 句话，基于真实会话数据说明为什么", "prompt_scaffold": "加到哪里，如'加到 ## 测试 小节下'"}
  ],
  "features_to_try": [
    {"feature": "功能名", "applies_to": "claude-code|codex|both", "one_liner": "它是做什么的", "why_for_you": "基于你的会话说明为什么对你有用", "example_code": "可复制的命令或配置"}
  ],
  "usage_patterns": [
    {"title": "短标题", "suggestion": "1-2 句总结", "detail": "3-4 句话说明如何应用到你的工作", "copyable_prompt": "可直接复制试用的提示词"}
  ]
}

config_additions 的重点：**优先选"Repeated user instructions to agents"里出现多次的指令**——用户在 2+ 个会话里对 agent 说过同样的话，就不该再重复。对两个工具都有用的指令用 `target_file: "both"`（共享内容放 AGENTS.md，CLAUDE.md 引用它）。条数按数据伸缩：config_additions 3-6 条（重复指令有多少条值得沉淀就给多少条）、features_to_try 2-4 条、usage_patterns 3-5 条；建议是本报告的核心价值，有据可依时尽量充分，但不为凑数编造。

模型/强度数据只是配置分布：没有逐轮阶段和结果归因时，不要写“max 导致慢/过度设计”或某档位导致返工。若给默认档位建议，明确它是待验证的工作约定，不是由当前统计证明的因果结论。

## 6. tool_comparison（工具对比，跨工具新增）

分析 per-agent 对比数据，描述该用户的两个编程 agent 实际上是如何被差异化使用的。

先依据用户说明、任务流向与结果解释分工。成本、环境和习惯都可能影响工具选择；模型名称不能单独证明成本动机、价格或任务难度。没有实质使用样本时不生成本节。

Session summaries 的 [agent|model|effort|active_min] 仅支持人工查看配置分布。不要把档位与设计、执行、审查阶段或结果建立未经采集的连接，也不要因 active_min 较长就归因给 max/ultra。

输出 JSON schema：
{
  "narrative": "2-3 段对比：什么任务流向哪个工具、模型构成及其原因（成本？）、会话长度/摩擦/满意度/结果/时段/项目的差异。用第二人称'你'。关键对比用 **加粗**。每个论断都要有数据支撑。",
  "division_of_labor": [
    {"tool": "claude-code|codex", "models": "观察到的主力模型", "best_at_for_you": "1-2 句：这个工具+模型组合在你的使用中实际擅长什么", "watch_out": "1 句：它在你数据里的主要摩擦"}
  ],
  "model_fit_observations": [
    {"observation": "1-2 句：从会话中发现的一个具体的任务-模型/强度匹配或错配", "suggestion": "1 句：建议把什么调高/调低（模型档位或推理强度），针对哪类任务"}
  ],
  "recommendation": "2-3 句：当前分工或模型/强度默认值要不要变？要具体、要诚实——数据支持的话'维持现状'也是合法结论。"
}

给出 2-3 条 model_fit_observations。如果数据里没有明显错配，诚实地在一条 observation 里说明，不要编造问题。

## 7. cross_tool_workflows（跨工具组合，跨工具新增）

分析跨工具信号（concurrent_multitasking、same-project handoffs、project_tool_matrix、handoff_examples），刻画用户是如何组合使用工具的。

输出 JSON schema：
{
  "intro": "1-2 句话总结组合使用的整体形态",
  "observed_patterns": [
    {"title": "短标题", "description": "2-3 句话描述一个观察到的跨工具模式（如接力方向、什么会触发切换），要落在 handoff 实例上", "evidence": "1 句话引用数据中的具体证据"}
  ],
  "combination_suggestions": [
    {"title": "短标题", "suggestion": "2-3 句话提议一个有意识的跨工具工作流（如一个规划/另一个执行、共享 AGENTS.md 让上下文在交接中存活、独立任务并行双开）", "copyable_prompt": "让交接更顺滑的提示词或配置片段"}
  ]
}

条数按证据伸缩。没有可支持的跨工具协作时简短说明，不为了填满章节推荐组合使用；本期只分析单工具时跳过本节。

## 8. on_the_horizon（未来可期）

分析这份使用数据，识别未来机会。

输出 JSON schema：
{
  "intro": "1 句话谈 AI 辅助开发的演进",
  "opportunities": [
    {"title": "短标题（4-8 个词）", "whats_possible": "2-3 句有野心的话，描述自治工作流的可能性", "how_to_try": "1-2 句话提及相关工具", "copyable_prompt": "可试用的详细提示词"}
  ]
}

按证据给出值得探索的机会，区分未来方向与当前可执行的建议；不重复 suggestions，也不为凑数引入新平台或跨工具编排。

## 9. fun_ending（趣味结尾）

分析这份使用数据，找一个值得记住的时刻。

输出 JSON schema：
{
  "headline": "会话摘要中一个值得记住的**质性**时刻——不是统计数字。要有人味、有趣或令人意外。",
  "detail": "简短交代发生的时间/场景"
}

找真正有意思或好笑的内容。概括写成叙述；仅在有逐字来源时使用引号，避免把转述写成用户原话。

---

## at_a_glance（一览，第二阶段，串行）

主 agent 读取已生成的各 section JSON，将其要点与 insight-context.md 一并作为上下文，按以下提示词生成（可自己生成或派发一个子 agent）：

你在为一份覆盖用户 AI 编程工具（Claude Code 和/或 Codex）的使用洞察报告撰写"一览"总结。目标是帮用户理解自己的使用方式并持续改进，尤其是在模型快速变强的背景下。

用以下五段结构：

1. **行之有效**——用户与 agent 协作的独特风格是什么？做成过哪些有影响的事？可以带一两个细节，但保持高层视角（用户对细节未必有印象）。不要浮夸、不要堆砌赞美。不要聚焦在工具调用上。

2. **卡点所在**——分成两部分：(a) agent 的问题（误解、方法错、Bug）；(b) 用户侧的摩擦（上下文给得不够、环境问题——尽量比单个项目更概括）。诚实但有建设性。

3. **工具分工**——一两句诚实评价当前工具间的分工（含模型/成本因素）是否在发挥作用。（只有单一工具时省略此段。）

4. **值得做的**——从建议中挑具体的功能，或一个真正有说服力的工作流技巧。避免"让 agent 行动前先确认""提前多打点上下文"这类没劲的建议。

5. **未来规划**——从本期已显现的能力与未解决问题出发，下一步有哪些值得试做的工作方式？不把未来模型进步当成已知前提。

每段 2-3 句、不要太长，不要让用户信息过载。不要重复顶部统计。语气直接自然，像熟悉工作的同事回顾事实和判断。值用中文写，JSON key 保持英文。

输出 JSON schema（写入 work/insights/at_a_glance.json）：
{
  "whats_working": "...",
  "whats_hindering": "...",
  "tool_division": "...",
  "quick_wins": "...",
  "ambitious_workflows": "..."
}

## 可选 10. knowledge_findings（历史知识与经验）

当用户要求从历史会话提取业务、项目、技术或组织经验，或本轮复盘材料确有可复用经验时启用；原有 7/9 个使用洞察 section 继续保留。读取 context 中来源与候选，按需要对已授权 locator 做有限原文核验。

输出 `work/insights/knowledge_findings.json`：

```json
{"intro":"覆盖范围与限制","findings":[{"title":"经验标题","finding":"可复用的小结论","evidence":["source_id"],"reuse":"适用场景","status":"候选/已采纳/已验证等实际状态","limits":"来源与适用边界"}]}
```

优先保留能在后续工作中复用的经验，区分事实、判断和建议。证据不足保留候选，不把用户要求当成已完成、不把报告建议当作已采纳规则。无支持材料时给空 findings 并在 intro 说明缺口。

## 可选 11. infrastructure_effectiveness（Agent 与基建效果）

当用户要求判断 Agent、subagent、Skill、模型和工具是否有效，或本轮复盘材料确有基建效果问题时启用。可分析单工具内部基建；只有单一工具时仍跳过原跨工具对比 section。

输出 `work/insights/infrastructure_effectiveness.json`：

```json
{"intro":"分析范围与限制","assessments":[{"name":"具体机制/工具","purpose":"使用目的","observed_result":"实际使用及观察到的结果","alternative_and_cost":"替代方案与成本，证据不足写未知","decision":"保留/调整/待验证的建议","next_check":"下一次如何验证","evidence":["source_id"],"limits":"归因与样本限制"}]}
```

沿“实际使用 → 结果 → 替代与成本 → 保留/调整”分析，不按出现频率为基建辩护。读取 Skill/规则只证明加载，不证明执行和收益；模型配置不证明阶段效果；subagent 多不等于效率高。列出可观察的节省、返工或阻塞，区分实测、估计、建议与未知。没有同条件对照或实际费用记录，不编价格、节省时长、满意度、模型收益或因果结论。

这两个可选 section 可与原 section 并行生成；at_a_glance 在它们完成后综合要点。所有 evidence 必须引用 context 中存在的 source id；缺关键依据时按已给定 locator 有限下钻并补来源，不能扩大为全历史重提。selection 的选样、直接阅读与 facet 数量必须如实说明，不能把样本结论外推到全量。
