# 报告、事故复盘与定制编辑器材料

> 目标：把一周运营状态、一次事故复盘和三个需要人参与调整的配置/文本任务整理成可供周会讨论和后续执行的材料。
> 背景：周会前，团队需要快速看状态；事故复盘后，需要跟踪 action；同时 PM 想亲手拖 ticket、调 feature flags、改 prompt，而不是把需求描述给 agent 猜。
> 受众：工程 manager、SRE、PM、客服运营。

## 1. Weekly status

周期：2026-05-04 至 2026-05-10。

| Workstream | Status | Shipped | Slipped | Next |
|---|---|---|---|---|
| Checkout recovery | yellow | 退款失败重试上线 | 自动补发延后 | 灰度 10 个门店 |
| Order exception workbench | green | 异常队列和详情抽屉 | 无 | 接入处理动作 |
| Observability | red | 新增 429 dashboard | SLA 告警误报仍多 | 修正窗口和静默规则 |
| Data contract | yellow | v1.6 字段台账 | user_phone 权限策略未定 | 安排治理评审 |

指标：

| Metric | Current | Previous | Target |
|---|---:|---:|---:|
| checkout recovery success | 92.4% | 88.1% | 95% |
| manual exception backlog | 318 | 451 | < 250 |
| p95 exception detail load | 780ms | 940ms | < 700ms |
| false positive alerts | 17 | 21 | < 8 |

## 2. Incident timeline

事故：2026-05-09 订单异常详情加载大量 500。

影响：

- 09:18-10:02，约 21% 异常详情请求失败。
- 6 个门店无法处理退款失败异常。
- 客服手工记录 47 单。

分钟级时间线：

| Time | Event |
|---|---|
| 09:18 | p95 latency 超 2s，error rate 到 8% |
| 09:21 | 告警触发，但误标为 warning |
| 09:27 | On-call 发现 `exception_detail_view` 500 激增 |
| 09:34 | 初步定位为 `orderSnapshot` 字段缺失导致 JSON parse 失败 |
| 09:41 | 回滚 `detail-panel-v2` feature flag |
| 09:47 | error rate 下降到 1.2% |
| 10:02 | backlog 恢复，事故关闭 |

日志摘录：

```log
09:27:11 ERROR detail-panel failed order_id=O-8731 err=Unexpected token u in JSON
09:31:42 WARN missing orderSnapshot fallback tenant=T-19 store=S-04
09:40:58 INFO feature_flag detail-panel-v2 changed true -> false by oncall
```

Follow-up checklist：

- [ ] JSON parse 增加空值 fallback。
- [ ] feature flag 回滚写入审计。
- [ ] 告警从 warning 调整为 critical。
- [ ] 事故模板增加 customer-impact 字段。

## 3. Ticket triage board

下面 ticket 需要在周会里重新排序到 Now / Next / Later / Cut，并在会后复制最终 Markdown 排序。

| ID | Title | Impact | Effort | Suggested |
|---|---|---|---|---|
| T-101 | 修复 orderSnapshot 空值 fallback | high | S | Now |
| T-102 | 告警 critical 阈值调整 | high | S | Now |
| T-103 | detail-panel-v2 审计日志 | medium | M | Next |
| T-104 | 异常详情骨架屏 | medium | M | Later |
| T-105 | 门店维度 backlog 图 | high | M | Next |
| T-106 | 客服复制话术优化 | medium | S | Now |
| T-107 | feature flag 依赖检查 | high | M | Now |
| T-108 | 导出事故时间线 CSV | low | S | Later |
| T-109 | 自动补发动作接入 | high | L | Next |
| T-110 | QuickBI 周报截图嵌入 | low | M | Cut |
| T-111 | 429 dashboard 误报修复 | high | M | Now |
| T-112 | user_phone 权限策略文档 | medium | M | Next |

## 4. Feature flag editor

当前 flags：

```json
{
  "detail-panel-v2": false,
  "exception-action-refund": true,
  "exception-action-reship": false,
  "audit-log-write": true,
  "flag-dependency-warning": false,
  "critical-alert-window-v2": false,
  "customer-copy-template-v2": true
}
```

依赖规则：

- `exception-action-reship` 依赖 `audit-log-write`。
- `detail-panel-v2` 依赖 `audit-log-write` 和 `flag-dependency-warning`。
- `critical-alert-window-v2` 应该和 `429 dashboard` 修复一起启用。
- 关闭 `audit-log-write` 时，所有处理动作都应警告。

需要能切换 flag，看到依赖警告，并复制只包含 changed keys 的 diff。

## 5. Prompt tuner

客服话术 prompt 模板：

```txt
你是 {brand} 的客服助手。
订单号：{order_id}
异常类型：{exception_type}
用户情绪：{customer_mood}
请用 {tone} 的语气解释当前处理进展，并给出下一步。
限制：不要承诺具体到账时间；不要泄露内部系统字段。
```

样例输入：

| brand | order_id | exception_type | customer_mood | tone |
|---|---|---|---|---|
| Gancao Mall | O-8731 | 退款失败 | 焦急 | 安抚但明确 |
| Gancao Mall | O-8738 | 库存不足 | 生气 | 道歉并给选择 |
| Gancao Mall | O-8742 | 物流延迟 | 平静 | 简洁 |

需要能看清变量槽位，并基于三个样例判断模板效果；最后能复制更新后的提示词包。

## 6. 阅读、编辑与交接难点

这份材料不是单纯报告，还包含需要人参与调整和导出的工作：

- 周状态需要快速判断 shipped / slipped / next，而不是读流水账。
- 事故复盘需要把分钟级时间线、log excerpts 和 follow-up checklist 放在一起看。
- ticket 需要会议中调整优先级，并在会后导出 Markdown。
- feature flags 有依赖关系，切换时要看到风险和只包含 changed keys 的 diff。
- 提示词模板需要结合三个样例预览，避免只靠抽象描述判断质量。
