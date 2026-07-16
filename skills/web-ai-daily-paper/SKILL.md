---
name: web-ai-daily-paper
description: >-
  搜集、核验、筛选、审查并生成面向 AI/Web 从业者的中文行业早报，同时维护事件级去重、证据包、人工反馈 case 和受控改进记录。用户提到 AI/Web 早报、技术资讯日报、每日新闻筛选、今日 AI 动态、前端资讯、查看早报 Review、哪些新闻未入选、反馈某条太水或漏选、根据反馈优化早报时，都应使用此 skill。普通的单篇网页总结、纯教程检索或任意领域新闻摘要不要触发。
compatibility: 需要网页搜索、网页正文提取和持久文件读写；BestBlogs 与 AnySearch API Key 均为可选增强。
metadata:
  hermes:
    tags: [research, ai, web, frontend, daily-brief, blueprint]
    requires_toolsets: [web, file]
    config:
      - key: web_ai_daily_paper.timezone
        description: 早报日期、时间窗口和调度使用的时区
        default: Asia/Shanghai
        prompt: 早报时区
      - key: web_ai_daily_paper.search_mode
        description: 搜索 provider 策略，可选 auto、native、anysearch、hybrid
        default: auto
        prompt: 搜索策略
      - key: web_ai_daily_paper.review_shortlist_size
        description: 人工 Review 默认展示的高排名未入选候选数
        default: 10
        prompt: Review 候选数
    blueprint:
      schedule: "28 8 * * 1-5"
      deliver: origin
      prompt: 生成今天的 AI/Web 早报，完成证据核验、自主 Review 和运行产物留档；只返回正式早报正文。
      no_agent: false
---

# Web AI Daily Paper

把公开信息整理成可追溯的 AI/Web 行业早报。早报用于补充行业视野：行业重要性高或工作相关度高，满足任一项即可进入候选。搜索和聚合摘要只负责发现；最终事实必须回到具体原文核验。

## 先判断任务模式

- 用户要“生成今天早报”“跑一次 dry-run”“回放某日”：走生成模式。
- 用户要“看 Review”“哪些没入选”“为什么选这条”：走审阅模式。
- 用户指出“漏选”“太水”“事实不对”或提出偏好：走反馈模式。
- 用户要“根据最近反馈优化”：走改进模式，提出并验证修改，不直接改生产规则。

如果用户只是总结一篇文章、搜索教程或做其他领域资讯汇总，不要套用本流程。

## 按需读取参考

- 生成或回放前读取 `references/editorial-policy.md`、`references/source-strategy.md` 和 `references/evidence-contract.md`。
- 首次落盘、读写历史或恢复失败运行时读取 `references/runtime-and-state.md`。
- 查看 Review、记录反馈或改进时读取 `references/feedback-and-improvement.md`。
- 在 Hermes 配置 cron、工具、密钥或 DingTalk 投递时读取 `references/hermes.md`。

## 生成模式

### 1. 建立运行上下文

1. 解析当前时区、运行时间、模式和目标日期；默认时区为 `Asia/Shanghai`。
2. 按 `references/runtime-and-state.md` 解析 runtime home，读取 profile、最近成功运行和近 30 天事件历史。
3. 默认从上次成功运行时间开始；普通候选最多回看 96 小时。未报过的 A 级重大事件和延伸阅读可回看 7 天，并标明实际日期。
4. `dry-run` 和 `replay` 生成完整 run 产物，但不更新正式事件历史。

### 2. 并行发现候选

始终覆盖三类入口：

1. 精选发现层：aihot、front-end-rss、BestBlogs。
2. 官方巡检层：AI 工具/模型、Web 平台、框架/运行时、工程化、安全公告。
3. Search Router：按主题 lane 做中英文补漏，使用宿主原生搜索或可用的 AnySearch。

记录每个候选的发现来源、原始 URL、query、初步时间和主题。精选源失败时继续其他入口，不把单源失败当作全局失败。

### 3. 打开原文并建立证据

对可能进入报告或 Review shortlist 的候选打开具体页面，建立 `claims[]` 与 `evidence[]`。区分事件发生时间和页面发布时间。产品发布、API、价格、版本、安全和政策等关键事实优先使用官方或一手来源。

以下内容不能单独支撑最终条目：搜索 snippet、聚合摘要、转载链、个人社媒、来源不明的公众号。无法解决的证据冲突直接拒绝。

### 4. 事件归并与准入

使用 `event_key + milestone` 合并同一事件。URL 是证据属性，不是事件身份。已报事件只有出现 GA、重大版本、补丁、官方回应、定价变化等新 milestone 才能再次进入。

按以下栏目选择：

- **今日重点**：A级，行业重要性或工作相关度高。
- **补充动态**：B级，事实可靠且近期有效，但影响范围或新闻性较低。
- **前端视野**：浏览器/API 新特性、新兴框架、工具和流行库；要求能力具体、项目可访问、维护活跃并有采用信号。
- **延伸阅读**：近期高质量解析、报告或实践文章，最多 2 条，不能伪装成当天新闻。

正常至少 5 条、通常 5-8 条；A级密集时可扩展到约 12 条。正常早报以至少 2 条 Web/前端内容为软目标。不得为条数或配比放宽事实可信度。

### 5. 自主 Review

在发布前独立审查初选结果：

- 从“为什么不该发”检查水文、旧闻、重复、营销、证据不足和过度表述。
- 从“是否漏掉”检查候选池内的高热度、高相关和 Web/前端优质候选。
- 核对分级、栏目、事实摘要、关注理由、来源和跨天 milestone。
- 记录 Review 前后的新增、删除、升降级和改写。
- 记录暴露出的 lane 空缺、来源失败、query 盲区和证据路径失败；这些是采集策略信号，不等同于立即修改生产策略。

最多修正一次。除 P0 覆盖缺口外，不重新发散搜索。未解决的真实性冲突禁止进入报告。

### 6. 写入产物并完成响应

先完整写入本次 run 的候选、证据、选择、拒绝、Review 和报告，再更新 `last-run.json`。正式模式把新事件写入历史；dry-run/replay 不写。

正式响应只返回早报正文，不混入采集日志、Review 或部署说明。Hermes cron 会在响应结束后投递，Skill 只能记录 `report_committed`，不能声称 `delivered`。

## 输出契约

```text
📰 今日AI/Web早报 — M月D日 周X

今日重点

1. 标题
事实：一句话说明发生了什么
关注：一句话说明行业意义、采用信号或潜在影响
来源 | https://具体原文

补充动态

2. ...

前端视野 / 延伸阅读（有内容时显示）
```

- 事实摘要只写证据支持的内容，目标 50-90 个中文字符。
- 关注理由可以是克制推断，但必须与事实分开，不能写成已发生结论。
- 链接指向具体可读页面，优先一手来源；完整多来源证据留在 run 产物。
- 不写情绪词、无证据趋势判断和行动指令。

若采集整体故障或连 3 条可核验内容都无法取得，允许少于 5 条；明确说明本次采集不完整，不用旧闻、传闻或重复内容补足。

## 审阅与反馈模式

读取 `references/feedback-and-improvement.md` 并遵循其交互协议：

- Review 默认展示全部入选、自主 Review 变更和最多 10 条高排名未入选候选。
- Review 对人只显示连续编号；内部稳定 `item_id` 保留在结构化产物和编号映射中，不要求用户查看或回复。
- Review 标题应让人不打开正文也能理解事件：通常包含主体、具体动作或 milestone，以及一个关键对象、能力或影响范围；比正式早报标题略具体，但不复制整段事实摘要。
- 用户可用编号、标题、URL 或自然语言反馈；只有无法消歧时才由 Agent 查询内部 `item_id`。
- 人工校准把“结论是否正确”和“理由是否正确”分开记录。支持只纠正理由、补充理由，以及用“其余认可”批量确认当前视图中未逐条反馈的项目；沉默不视为认可。
- 自动区分未发现、发现后误拒、错误入选、事实问题、编辑质量和个人偏好。
- 原始反馈只追加保存；结构化 case 不覆盖用户原话。
- 已发布报告默认不自动重发，除非用户明确要求。

## 改进模式

把人工反馈和 Review 暴露出的采集信号转成回归 case，聚类根因并生成可泛化的修改提案。只有 `discovery_miss`、lane 空缺、来源失败、query 盲区和证据路径失败进入采集策略改进；`selection_miss`、分级和表达问题留在编辑策略。对候选修改运行历史 case 回放和前后版本评测。生产 Skill 不自动改写自身规则；只有用户确认后才应用并发布修改。

## 完成判断

完成一次生成需要同时满足：

- 最终条目均有具体原文和可追溯 claim 证据。
- 无未解决的真实性冲突、无相同 event/milestone 重复。
- 已执行一次自主 Review 并记录差异。
- run 产物完整，状态更新符合正式/dry-run 边界。
- 最终响应只包含目标模式需要的人类可读结果，不回显密钥或内部配置。

## 失败处理

- 单个精选源或搜索 provider 失败：记录失败并继续其他入口。
- 原文不可访问：寻找一手替代页或独立权威来源；仍无法核验则拒绝。
- runtime home 不可写：不要假装已完成持久化；返回报告草稿并明确说明未记录历史，禁止正式自动投递。
- 凭据缺失：降级到公开 RSS、宿主原生搜索或当前允许无凭据调用的 provider，不在对话中索取或回显生产密钥。
- 投递失败：复用已保存的 `report.txt` 手动重发，不重新采集，也不把报告状态改成 delivered。
