# 探索、原型与执行计划材料

> 目标：把一组尚未定型的产品/技术想法，整理成一个可以在评审会上直接比较、试用和交接的材料。
> 背景：团队要为「订单异常处理台」选择缓存方案、页面视觉方向、关键交互动效，并把最终选择转成执行计划。
> 受众：产品负责人、前端负责人、后端接口 owner、交互设计师。

## 1. 用户问题

我们需要在 2 周内把「订单异常处理台」从只读列表升级成可处理工作台。现在大家对方案没有共识：

- 技术侧争论缓存放在服务端、边缘 KV，还是浏览器侧 stale-while-revalidate。
- 设计侧争论页面应该偏「密集运营台」「审批流工作台」还是「轻量看板」。
- 交互侧争论异常详情抽屉应该快进快出，还是保留较慢的确认感。
- PM 需要下周一拿一份能给老板和实现同学都看懂的执行计划。

请不要把下面材料线性重排成普通会议纪要；评审会需要比较、试用和交接。

## 2. 三种代码方案

### 方案 A：服务端聚合缓存

适用条件：订单异常列表需要严格遵守权限过滤，业务域后端已经有聚合服务。

```ts
export async function listOrderExceptions(ctx: RequestContext) {
  const cacheKey = `order-exceptions:${ctx.tenantId}:${ctx.role}:${ctx.filterHash}`;
  return cache.remember(cacheKey, 30, async () => {
    const rows = await orderService.queryExceptions(ctx);
    return rows.map(maskSensitiveFields);
  });
}
```

优点：

- 权限和脱敏逻辑集中。
- 前端接口简单。
- 对旧浏览器无额外要求。

缺点：

- 缓存 key 容易膨胀。
- 过滤条件变多后命中率下降。
- 后端发布节奏会影响体验迭代。

### 方案 B：边缘 KV 热列表

适用条件：只缓存门店级、租户级热门队列，不缓存强个人化视图。

```ts
export async function getHotExceptionQueue(tenantId: string, storeId: string) {
  const key = `hot-exception-queue:${tenantId}:${storeId}`;
  const cached = await edgeKV.get(key);
  if (cached) return JSON.parse(cached);
  const rows = await rebuildHotQueue(tenantId, storeId);
  await edgeKV.set(key, JSON.stringify(rows), { ttl: 20 });
  return rows;
}
```

优点：

- 首屏快。
- 适合跨区域门店运营。
- 可以给 dashboard 和工作台复用。

缺点：

- 不能直接缓存个人权限视图。
- 失效策略复杂。
- 边缘 KV 故障时需要回源策略。

### 方案 C：浏览器 stale-while-revalidate

适用条件：接口已经能返回用户权限后的数据，且列表允许短时间陈旧。

```ts
const exceptions = useSWR(
  ['order-exceptions', filters],
  () => api.orderExceptions.list(filters),
  {
    revalidateOnFocus: true,
    dedupingInterval: 10_000,
    keepPreviousData: true
  }
);
```

优点：

- 交互体验好，切筛选不闪烁。
- 前端可独立调优。
- 对后端侵入最小。

缺点：

- 首屏性能仍依赖接口。
- 需要处理陈旧数据提示。
- 多标签页状态一致性需要额外约束。

## 3. 视觉方向备选

### 方向 1：密集运营台

- 适合客服主管和门店运营每天高频处理。
- 首屏信息密度高，左侧为筛选，主体是异常队列，右侧是处理摘要。
- 主色建议：暖白底、深灰字、橙色风险、绿色恢复。

### 方向 2：审批流工作台

- 适合异常需要多角色确认的阶段。
- 队列按「待领取 / 处理中 / 待复核 / 已关闭」组织。
- 每条异常显示责任人、SLA、最近动作和阻塞原因。

### 方向 3：轻量看板

- 适合老板看趋势和异常分布，不适合一线密集处理。
- 卡片区展示异常类型、门店排名、趋势线和本周目标。
- 交互重点是 drill-down，而不是逐条处理。

## 4. 交互动效待调

异常详情抽屉从右侧进入，承载订单信息、风险证据、处理动作和评论。

候选参数：

| 参数 | 选项 |
|---|---|
| duration | 180ms / 240ms / 320ms |
| easing | ease-out / cubic-bezier(0.2, 0.8, 0.2, 1) / ease-in-out |
| overlay | 0.16 / 0.24 / 0.32 |
| width | 420px / 520px / 640px |

需要能直接试调，否则设计评审只能靠想象。

## 5. 四屏点击流

1. 异常队列：查看全部异常，按风险和 SLA 筛选。
2. 异常详情：查看订单、支付、库存、履约证据。
3. 处理动作：选择「退款」「补发」「转人工复核」「关闭」。
4. 处理结果：展示已执行动作、待同步系统、可复制给客服的说明。

## 6. 实施计划素材

### 里程碑

| 周期 | 目标 | 交付 |
|---|---|---|
| W1D1-W1D2 | 方案确认 | 选择缓存策略、视觉方向、抽屉动效默认值 |
| W1D3-W1D5 | 列表和详情 | 异常队列、详情抽屉、基础筛选 |
| W2D1-W2D3 | 处理动作 | 退款/补发/复核/关闭动作接入 |
| W2D4-W2D5 | 灰度和复盘 | 5 个门店灰度、SLA 与误操作复盘 |

### 数据流

```
Order Service -> Exception Aggregator -> Workbench API -> Web UI -> Action API -> Audit Log
```

### 风险代码

```ts
// 风险：当前实现只校验订单存在，没有校验异常处理权限。
export async function closeException(id: string, user: User) {
  const item = await exceptionRepo.get(id);
  await exceptionRepo.close(item.id, user.id);
}
```

### 风险表

| 风险 | 影响 | 缓解 |
|---|---|---|
| 权限校验不完整 | 非责任门店关闭异常 | Action API 必须校验租户、门店和角色 |
| 缓存陈旧 | 已处理异常仍显示待处理 | 显示更新时间和重新验证状态 |
| 动作不可回滚 | 误操作导致资金损失 | 高风险动作增加复核和审计日志 |

## 7. 会议输出需要

- 评审会希望能横向比较三种代码方案，而不是读三段长说明。
- 设计师希望看到三个方向的实际渲染草图。
- 交互设计师希望能调抽屉参数。
- PM 希望一键切到 5 页以内的 slide mode 讲给老板。
- 实现同学希望会后能复制选定方案、风险代码和执行计划。
- 视觉风格按工作区 `DESIGN.md` 执行：近白画布、ink 主对比、细 hairline、Inter/Geist 风格 sans、mono 技术标签、克制圆角和极轻阴影；不要使用旧的暖色 serif briefing 模板。
- 中文阅读优先：导航、按钮、区块标题、状态和反馈用中文；英文只保留代码、字段、产品名和必要技术术语。
