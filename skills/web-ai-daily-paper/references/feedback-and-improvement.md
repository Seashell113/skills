# 自主 Review、人工反馈与受控改进

## 人工 Review 视图

用户说“看今天的 Review”“哪些没入选”或指定日期时，读取对应 run，按以下顺序展示：

1. 本轮结论：是否通过、入选数、重要覆盖和争议点。
2. 全部最终入选：栏目、入选理由和证据状态。
3. 自主 Review 变化：新增、删除、升降级、合并和改写。
4. 高排名未入选：默认最多 10 条，包含原因和再次入选条件。
5. 覆盖与来源摘要：AI/Web、官方/权威/社区、主要拒绝原因。

不要倾倒全部原始候选。用户需要更多时再分页或按 lane 查看。

Review 对人使用从 1 开始的连续编号，最终入选、自主 Review 变化和未入选候选各自按展示顺序编号。用户只需回复“第 3 条”或标题。内部仍保留稳定 `item_id`，并在结构化 `review.json` 中保存 `display_number → item_id` 映射，用于跨产物定位、反馈 case 和回归测试；除非存在歧义，不向用户显示内部 ID。

Review 标题需要具备最低自解释性，优先写成“主体 + 具体动作或 milestone + 关键对象、能力或影响范围”。它可以比正式早报标题多一个关键信息点，例如版本、受影响范围、核心能力或测试状态，让用户不打开正文也能判断条目大意。标题仍保持单行，不把事实摘要、入选理由或落选原因全部塞入标题。

## Review 如何反馈采集策略

Review 会产生采集信号，但不会把所有 Review 结论都混入搜索策略：

| Review 发现 | 归属 | 可形成的后续动作 |
| --- | --- | --- |
| 重要事件根本没进入候选池 | `discovery_miss` | 补 lane query、官方巡检入口或精选源覆盖 |
| P0 lane 为空 | `lane_gap` | 本轮允许一次定向补漏；跨轮记录缺口频率 |
| 精选源或 provider 持续失败 | `source_failure` | 调整 fallback、健康检查或备用 provider |
| 候选存在但搜不到可核验证据 | `evidence_path_failure` | 增加一手来源域名、公告页或仓库 release 路径 |
| 某 query/source 长期只产生水文 | `source_noise` | 降低该 query/source 的发现优先级，仍保留事实硬门槛 |
| 已发现但误拒、误分级或写得太水 | `selection_miss` / `editorial_quality` | 修改准入、分级或表达规则，不改采集范围 |

同一次生成中，自主 Review 只在 P0 覆盖缺口时允许追加一次定向搜索，其余修正基于现有候选和证据完成。跨次运行把信号写入 `review.json.collection_signals[]`，至少记录 `signal_type`、目标 lane/source/query、证据、建议动作和状态。

单次源故障、一次低质量结果或个人偏好不自动改写长期策略。高严重度 discovery miss，或多个运行重复出现的同类信号，可进入改进提案；回放历史 case 并经人工确认后，才更新 profile、query family、官方巡检清单或 provider 路由。

## 自然语言反馈入口

用户不需要学习命令。支持标题、序号、item id、URL 和口语表达：

- “Cursor 那条应该进今日重点。”
- “第三条太水了，以后类似的别拿来补位。”
- “漏了这个：https://...”
- “第 2 条关注理由说得太满。”
- “第 3 条入选没问题，但真正原因是行业热度，不是工作相关。”
- “未入选第 1 条应该进，因为它的安全影响面更大；其余认可。”
- “只是今天不想看，不要改长期偏好。”

## 逐条结论与理由校准

人工反馈需要把两个维度分开：

1. **结论校准**：入选、落选、栏目和等级是否正确。
2. **理由校准**：即使结论正确，Agent 对新闻价值、证据边界或落选原因的理解是否正确。

“选对但理由错”是独立的高价值 case。它不应被折叠成简单认可，也不应在结论未变化时被忽略。保存 Agent 当时的结论与理由快照，再保存人工原话和派生校准：

```json
{
  "decision_calibration": "agree | disagree | unsure | not_provided",
  "rationale_calibration": "agree | corrected | supplemented | unsure | not_provided",
  "human_reason_raw": "用户原话或 null",
  "reason_codes": ["industry_significance", "adoption_signal"],
  "strategy_target": "collection | evidence | selection | ranking | editorial | preference",
  "explicitness": "explicit_item | batch_ack"
}
```

`reason_codes` 是便于聚类的派生字段，不覆盖用户表达；可以按实际语义增加，不强迫用户选择标签。常见理由包括行业重要性、工作相关性、行业热度、采用信号、信息增量、安全影响、证据强弱、新鲜度、重复、营销感和视野拓展。

默认采用低负担交互：用户只需写需要纠正或补充的项目，其余可用一句“其余认可”批量确认。例如：

```text
第 2 条：认可
第 3 条：结论对，但原因应是行业热度高，不是与当前工作直接相关
未入选第 1 条：应该入选，原因是安全影响面比同栏另一条更大
其余认可
```

“其余认可”只作用于当前 Review 中可见且未被逐条反馈的项目，记录为 `batch_ack`；不替用户编造更具体的理由。没有任何回复的项目保持 `not_provided`，不能把沉默推断为认可。

人工理由决定改进路由，但仍需检查候选现场：事件未进入候选池才反馈采集；已发现但价值理由判断错误反馈筛选或排序；证据边界理解错误反馈证据策略；标题或关注理由问题反馈编辑；明确的个人长期取向才进入 profile 候选。

处理流程：

1. 优先从当前对话、最近 run、标题和 URL 自动定位。
2. 只有存在多个匹配对象时才追问，不要求用户补内部字段。
3. 简短复述对象、理解和预计作用域。
4. 先追加保存用户原话，再生成结构化 case。
5. 分别识别结论校准、理由校准、预计改进路由和作用域。
6. 返回简洁回执：`feedback_id`、是否影响当前报告、是否成为回归 case、下一步。

示例回执：

```text
已记录 FB-20260716-03：你认为 Review 第 4 条 “Web API 更新” 应进入前端视野。
初步判断为 selection_miss，将加入回归 case；今天的报告已发布，因此不会自动重发。
```

## 分类与根因

| 反馈 | 类型 | 需要区分 |
| --- | --- | --- |
| 应入选但未入选 | `false_negative` | `discovery_miss` 或 `selection_miss` |
| 入选太水 | `false_positive` | 准入、分级、补位、热度误判 |
| 事实/来源/摘要错误 | `factual_or_evidence` | 最高优先级，可构成硬门槛缺陷 |
| 栏目/关注理由/表达问题 | `editorial_quality` | 事实与推断是否混淆 |
| 结论正确但判断理由不准确 | `rationale_correction` | 采集、证据、筛选、排序、表达或偏好 |
| 希望多看或少看某主题 | `preference` | 单次意见或持久 profile |

漏选 URL 从未进入候选池时是 discovery miss；已发现但拒绝是 selection miss。两者需要改不同环节。

## 作用域

- **本次修正**：只改变当前 dry-run 或尚未发布的报告，可再执行一次自主 Review。
- **单次意见**：保存 case，不写长期偏好。
- **个人偏好**：属于 topic/source 权重时，先解释未来影响并获得明确确认，再更新 runtime profile。
- **Skill 缺陷**：需要修改通用规则、证据契约或流程，进入改进提案与评测。

已发布报告默认不自动重发。用户明确要求“重发/更正版”时，基于原 run 产生新版本并保留版本关系；事实纠错应在更正版中明确。

## Feedback case

每个 case 保存：

- `feedback_id`、原始反馈、接收时间和状态。
- `run_id`、`item_id`、标题、URL 和原始候选快照。
- discovery、初选、自主 Review、最终发布各阶段状态。
- 当时证据、分级、栏目和入选/拒绝理由。
- Agent 原始结论与理由，以及人工对结论、理由的独立校准。
- 人工理由原话、派生 reason codes、明确程度和预计改进路由。
- 类型、根因、作用域和严重程度。
- 关联改进提案、回归测试、验证结果和解决版本。
- 若涉及采集，关联 `collection_signal`、目标 lane/source/query family 和拟调整动作。

状态流转：

```text
received → triaged → accepted / deferred / rejected → regression_added → resolved
```

原始反馈只追加保存。自动分类错了时更新派生 case，不修改用户原话。

## 受控改进

生产 Skill 不自动修改自身规则。允许 Agent：

- 将反馈变成回归 case。
- 聚类重复失误并判断根因。
- 生成可泛化改进提案。
- 对候选版本运行历史 case 回放和前后对照。
- 汇总影响、收益、退化和待确认项。

只有用户显式要求“根据最近反馈优化”，或重复失误积累后用户接受 Agent 的建议，才进入修改流程：

1. 读取全部相关 case，不只看最近一条。
2. 区分一次性偏好与可泛化缺陷。
3. 为缺陷新增回归测试。
4. 修改 Skill 或 profile contract。
5. 运行 with-skill/baseline 或前后版本对照，并回放其他历史 case。
6. 人工确认后发布。

除明显违反事实硬门槛外，不因单个样本直接改全局规则。避免修复一个 case 后让其他主题、来源或日期退化。
