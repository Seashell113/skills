# 证据、事件和选择契约

## Candidate

每个候选至少保存：

- `item_id`：本次 run 内稳定 ID，例如 `ITEM-03`。
- `title`、`url`、`discovered_via`、`discovery_query`。
- `topic_lane`、`content_type`、`published_at_guess`。
- `original_source_url`：如果发现页是聚合或转载，记录追溯结果。
- `candidate_status`：`new`、`verified`、`rejected`、`selected`。

不要在发现阶段把 snippet 写成最终事实。

## Event identity

- `event_key`：实体 + 动作 + 产品/版本 + 事件日期的语义键。
- `milestone`：`announcement`、`beta`、`ga`、`major_release`、`patch`、`official_response`、`pricing_change`、`security_fix` 等。
- `event_time`：事件实际发生时间。
- `published_at`：当前页面发布时间。

同一事件的不同报道共享 `event_key`；只有 milestone 发生变化才允许跨天再次入选。不要只依赖 URL 或标题 hash。

## Claim-level evidence

将最终可能使用的摘要拆成原子 claim。每条 claim 保存：

- `claim_id` 和规范化文本。
- `evidence_refs[]`。
- `verification_status`：`verified`、`conflicting`、`unverified`。

每条 evidence 保存：

- 具体 URL、来源名、来源等级和是否一手。
- 页面标题、发布时间、访问时间。
- 支撑哪个 claim 的证据说明；不要大段复制原文。
- 与其他 evidence 是否独立。

## 硬门槛

最终条目必须满足：

- 能明确描述一个事件，或被明确归入前端视野/延伸阅读。
- 时间在对应窗口内，放宽时有原因。
- 行业重要性或工作相关度至少一项成立。
- 所有关键 claim 为 `verified`。
- 主链接是具体、可访问页面。
- 与近期历史相比存在新 event 或新 milestone。

事实可信度不分 A/B 降级。B级表示编辑价值较低，不表示证据较弱。

## 直接拒绝

- 个人爆料或热门传闻无法找到一手或独立权威证据。
- 日期不明且不能确认事件发生在窗口内。
- 把教程、观点或产品介绍伪装成近期新闻。
- 搜索 snippet、聚合摘要或转载是唯一证据。
- 关键数字、版本、主体或因果关系互相冲突。
- 同一 event/milestone 已在近期报告中出现。

## 关注理由

关注理由不需要逐字出现在来源中，但必须基于已核验事实。保存：

- `reason_type`：行业规模、采用信号、开发影响、安全风险、生态变化等。
- `inference`：具体一句话。
- `basis_claim_ids[]`。
- `certainty`：`direct` 或 `inferred`。

不要从下载量、star 或媒体数量直接推断质量；这些只能作为采用/热度信号之一。

## 拒绝原因码

优先使用稳定原因码，方便 Review 和反馈归因：

- `not_an_event`
- `stale`
- `unverified`
- `source_too_weak`
- `duplicate_event`
- `low_editorial_value`
- `marketing_only`
- `quota_limit`
- `superseded_source`
- `conflicting_evidence`

拒绝时同时写人类可读理由和 `counterfactual`：补充什么证据或出现什么变化后可能入选。

## 自主 Review 结果

Review 记录：

- `before_selection[]` 和 `after_selection[]`。
- `changes[]`：`restore`、`remove`、`promote`、`demote`、`rewrite`、`merge`。
- 每个 change 的对象、原因和依据。
- `near_misses[]`：高排名未入选候选，默认最多 10 条。
- 覆盖、来源和拒绝原因摘要。
- `review_status`：只有不存在未解决事实冲突时才是 `passed`。

自主 Review 可以修正选择，不得通过改写措辞掩盖证据不足。
