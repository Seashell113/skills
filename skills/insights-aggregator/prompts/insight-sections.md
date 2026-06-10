# 洞察 Section 提示词

用途：基于 `work/insight-context.md`（aggregate.py 产出）生成各洞察 section。

执行方式：
- 第一阶段：下列 9 个 section **并行**派发子 agent。每个子 agent 读取 `work/insight-context.md`，按对应提示词生成，并将纯 JSON 写入 `work/insights/{section_name}.json`。
- 第二阶段（串行）：全部完成后，再按文末 `at_a_glance` 提示词生成总览（其上下文 = insight-context.md + 各 section 产出要点），写入 `work/insights/at_a_glance.json`。
- 若数据中只有单一工具（`agents_present` 只有一个），跳过 `tool_comparison` 与 `cross_tool_workflows` 两个 section。

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

给出 3 个出色的工作流。

## 4. friction_analysis（摩擦分析）

分析这份使用数据，找出该用户的摩擦点。用第二人称（"你"）。

输出 JSON schema：
{
  "intro": "1 句话总结摩擦模式",
  "categories": [
    {"category": "具体的类别名", "description": "1-2 句话解释这类摩擦、可以怎么做得不同。", "examples": ["带后果的具体例子", "另一个例子"]}
  ]
}

给出 3 个摩擦类别，各配 2 个例子。如果摩擦在工具间有明显差异，指出发生在哪个工具。

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

config_additions 的重点：**优先选"Repeated user instructions to agents"里出现多次的指令**——用户在 2+ 个会话里对 agent 说过同样的话，就不该再重复。对两个工具都有用的指令用 `target_file: "both"`（共享内容放 AGENTS.md，CLAUDE.md 引用它）。每类给 2-3 条。

另外结合 Context notes / 模型数据考虑**模型与推理强度调优**：如果发现任务-模型错配（简单任务开高强度、复杂任务用弱模型），可以在 usage_patterns 里给一条具体的默认值建议（哪类任务值得开 `xhigh`、哪类任务用 `low` + 国产模型就够）。

## 6. tool_comparison（工具对比，跨工具新增）

分析 per-agent 对比数据，描述该用户的两个编程 agent 实际上是如何被差异化使用的。

重要背景——成本驱动的混用：用户同时用两个工具的常见原因是**成本控制**而非单纯能力偏好：Codex 走官方模型，Claude Code 常被接入更便宜的第三方/国产模型（kimi / deepseek / glm / qwen…）。先看 `models_by_turns`——如果 Claude Code 出现这类模型名，就用这个视角解读分工（便宜可控的任务 → Claude Code + 国产模型；重活/复杂活 → 官方模型）。不要默认两个工具都跑高价模型。

同时用 Session summaries 里每行的 [agent|model|effort|active_min] 标签评估**任务-模型/推理强度匹配度**：找出 (a) 简单任务却用了不必要的高推理强度或高价模型；(b) 复杂任务用了弱模型或低强度、导致摩擦/返工。

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

各给 2-3 条。如果跨工具事件很少，诚实说明，并把建议聚焦在"更有意识的组合是否值得"或"单工具专注也挺好"上。

## 8. on_the_horizon（未来可期）

分析这份使用数据，识别未来机会。

输出 JSON schema：
{
  "intro": "1 句话谈 AI 辅助开发的演进",
  "opportunities": [
    {"title": "短标题（4-8 个词）", "whats_possible": "2-3 句有野心的话，描述自治工作流的可能性", "how_to_try": "1-2 句话提及相关工具", "copyable_prompt": "可试用的详细提示词"}
  ]
}

给出 3 个机会。想得大胆些——自治工作流、并行 agent、对着测试迭代、跨工具编排。

## 9. fun_ending（趣味结尾）

分析这份使用数据，找一个值得记住的时刻。

输出 JSON schema：
{
  "headline": "会话摘要中一个值得记住的**质性**时刻——不是统计数字。要有人味、有趣或令人意外。",
  "detail": "简短交代发生的时间/场景"
}

找真正有意思或好笑的内容。

---

## at_a_glance（一览，第二阶段，串行）

主 agent 读取已生成的各 section JSON，将其要点与 insight-context.md 一并作为上下文，按以下提示词生成（可自己生成或派发一个子 agent）：

你在为一份覆盖用户 AI 编程工具（Claude Code 和/或 Codex）的使用洞察报告撰写"一览"总结。目标是帮用户理解自己的使用方式并持续改进，尤其是在模型快速变强的背景下。

用以下五段结构：

1. **行之有效**——用户与 agent 协作的独特风格是什么？做成过哪些有影响的事？可以带一两个细节，但保持高层视角（用户对细节未必有印象）。不要浮夸、不要堆砌赞美。不要聚焦在工具调用上。

2. **卡点所在**——分成两部分：(a) agent 的问题（误解、方法错、Bug）；(b) 用户侧的摩擦（上下文给得不够、环境问题——尽量比单个项目更概括）。诚实但有建设性。

3. **工具分工**——一两句诚实评价当前工具间的分工（含模型/成本因素）是否在发挥作用。（只有单一工具时省略此段。）

4. **值得做的**——从建议中挑具体的功能，或一个真正有说服力的工作流技巧。避免"让 agent 行动前先确认""提前多打点上下文"这类没劲的建议。

5. **未来规划**——未来 3-6 个月模型会强得多，该为什么做准备？现在看起来不可能的工作流，哪些会变得可能？

每段 2-3 句、不要太长，不要让用户信息过载。不要引用具体统计数字。用教练式口吻。值用中文写，JSON key 保持英文。

输出 JSON schema（写入 work/insights/at_a_glance.json）：
{
  "whats_working": "...",
  "whats_hindering": "...",
  "tool_division": "...",
  "quick_wins": "...",
  "ambitious_workflows": "..."
}
