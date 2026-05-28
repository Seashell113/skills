# PR Review：结算优惠链路重构

> 评审对象：`feature/checkout-discount-pipeline`  
> 目标：判断是否可以进入灰度  
> 结论：暂不建议合并。两个 P1 会改变线上结算行为，一个 P2 会影响监控连续性。

## 1. 总体判断

本 PR 试图把优惠计算从“过程式顺序调用”改成“pipeline 规则链”。方向合理，但当前 diff 中有三类风险：

1. 灰度开关缺省值从保守变成激进，配置缺失时会默认开启新链路。
2. 会员折扣和满减的计算顺序发生变化，现有测试未覆盖叠加场景。
3. 日志字段命名改成驼峰，旧 dashboard 依赖下划线字段。

## 2. 关键 diff 摘录

### 2.1 灰度开关缺省值

文件：`src/checkout/discountFlag.ts`

```diff
 export function enableNewDiscountFlow(config: RemoteConfig): boolean {
-  return config.getBoolean('checkout.new_discount_flow') ?? false
+  return config.getBoolean('checkout.new_discount_flow') ?? true
 }
```

评审意见：

- 这会让配置中心读取失败、配置未发布、key 拼写错误时都进入新链路。
- 灰度开关缺省值应保持 `false`，除非有明确的全量切换计划。
- 需要新增“配置缺失”和“配置读取失败”测试。

### 2.2 优惠计算顺序变化

文件：`src/checkout/calculate.ts`

```diff
 export function calculatePayable(order: Order, ctx: CheckoutContext) {
-  const afterMember = applyMemberDiscount(order.total, ctx.member)
-  const afterCampaign = applyCampaignDiscount(afterMember, ctx.campaigns)
-  return applyCoupon(afterCampaign, ctx.coupon)
+  const pipeline = createDiscountPipeline([
+    campaignRule(ctx.campaigns),
+    memberRule(ctx.member),
+    couponRule(ctx.coupon)
+  ])
+  return pipeline.run(order.total)
 }
```

评审意见：

- 旧顺序是“会员折扣 -> 满减 -> 优惠券”。
- 新顺序变成“满减 -> 会员折扣 -> 优惠券”。
- 对同时命中会员折扣和满减的订单，实付金额可能变化。
- PR 中没有看到产品规则确认，也没有叠加优惠测试。

### 2.3 测试覆盖缺口

文件：`src/checkout/calculate.test.ts`

```diff
 describe('calculatePayable', () => {
   it('applies coupon discount', () => {
     expect(calculatePayable(orderWithCoupon, ctx)).toBe(8800)
   })
+
+  it('applies campaign discount', () => {
+    expect(calculatePayable(orderWithCampaign, ctx)).toBe(9000)
+  })
 })
```

评审意见：

- 新增测试只覆盖单一优惠。
- 缺少“会员折扣 + 满减 + 优惠券”组合场景。
- 缺少新旧链路对同一组样例输出一致的对比测试。

### 2.4 日志字段命名变化

文件：`src/checkout/logger.ts`

```diff
 checkoutLogger.info('discount_applied', {
-  discount_flow: flowName,
+  discountFlow: flowName,
   order_id: order.id,
   discount_amount: discountAmount
 })
```

评审意见：

- 旧 dashboard 使用 `discount_flow` 做筛选维度。
- 直接替换会导致监控断点。
- 建议至少保留一版双写，或先改 dashboard 后切换字段。

## 3. 风险分层

### P1：阻塞合并

#### P1-1：灰度开关默认开启

影响：

- 配置缺失时新链路全量生效。
- 灰度发布无法保证只影响目标门店。

建议：

- 缺省值恢复为 `false`。
- 补充配置缺失、读取失败、显式开启、显式关闭四类测试。

#### P1-2：优惠计算顺序改变

影响：

- 同一订单在新旧链路下实付金额可能不同。
- 如果产品未确认规则变化，这属于线上金额风险。

建议：

- 产品确认叠加顺序。
- 添加新旧链路 golden cases。
- 灰度前用历史订单样本跑离线对账。

### P2：合并前建议处理

#### P2-1：日志字段改名导致 dashboard 断点

影响：

- 监控看板和告警查询可能丢失新链路数据。
- 不直接影响交易主流程，但影响灰度观察。

建议：

- 临时双写 `discount_flow` 和 `discountFlow`。
- 或在 dashboard 迁移完成后再删除旧字段。

## 4. 回归面

| 模块 | 受影响点 | 当前覆盖 | 缺口 |
|---|---|---|---|
| 灰度配置 | 新链路开关 | 无配置缺失测试 | 缺省值风险 |
| 结算金额 | 多优惠叠加 | 单一优惠测试 | 无组合场景 |
| 日志监控 | 灰度观察字段 | 本地未验证 dashboard | 字段兼容风险 |
| 离线对账 | 历史订单样本 | 未提供 | 无金额差异基线 |

## 5. 作者需要确认的问题

1. 产品是否确认优惠叠加顺序从“会员 -> 满减”变为“满减 -> 会员”？
2. 配置中心读取失败时，平台默认行为是什么？是否会返回 `undefined`？
3. 灰度期间 dashboard 是否必须同时看到新旧链路数据？
4. 是否已有历史订单样本可用于离线对账？

## 6. 建议合并条件

合并前至少满足：

- 灰度开关缺省值恢复保守。
- 多优惠叠加测试补齐。
- 金额规则由产品确认。
- 日志字段兼容方案明确。
