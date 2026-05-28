# 研究讲解、概念模拟与图示材料

> 目标：把 rate limiting 和 consistent hashing 的学习材料做成一个适合内部技术分享和写作复用的学习材料。
> 背景：新同学要理解 Gateway repo 的限流链路、部署流程和一致性哈希概念。Markdown 里线性解释太长，读者很难建立路径感。
> 受众：新加入的后端同学、SRE、技术写作者。

## 1. Feature explainer：Gateway rate limiting

### TL;DR

Gateway 的限流分两层：

1. Edge 层按 IP 和 tenant 做粗粒度限流，保护入口。
2. Service 层按 API key、route 和 plan 做精细限流，返回可解释的 429。

### Request path

```
Client
  -> CDN edge
  -> Gateway ingress
  -> RateLimitMiddleware
  -> TokenBucketStore
  -> RouteHandler
  -> UsageReporter
```

### 关键配置

`gateway/rate-limit.yml`

```yaml
plans:
  free:
    requests_per_minute: 120
    burst: 40
  pro:
    requests_per_minute: 1200
    burst: 300
routes:
  /v1/search:
    weight: 3
  /v1/export:
    weight: 10
```

`gateway/middleware.ts`

```ts
export async function rateLimit(ctx: GatewayContext, next: Next) {
  const policy = resolvePolicy(ctx.apiKey, ctx.route);
  const decision = await bucket.take(policy.key, policy.weight);
  if (!decision.allowed) {
    throw new RateLimitError(decision.retryAfterMs);
  }
  await next();
}
```

### FAQ

- 为什么导出接口 weight 更高？因为它会触发异步任务和对象存储写入。
- 为什么不能只在 CDN 限流？因为 plan、route、API key 等业务上下文在服务层才完整。
- 429 是否计入 usage？不计入 billable usage，但计入 abuse monitoring。

## 2. Concept explainer：consistent hashing

### 为什么需要

普通取模：

```
node = hash(key) % nodeCount
```

当节点数从 3 变成 4，大量 key 会移动，缓存命中率崩掉。

一致性哈希：

1. 把节点放到 hash ring 上。
2. 把 key 也映射到 ring 上。
3. key 顺时针找到第一个节点。
4. 增删节点时，只影响相邻区间。

### 节点样例

| Node | Virtual nodes | Capacity |
|---|---:|---:|
| gateway-a | 64 | 1x |
| gateway-b | 64 | 1x |
| gateway-c | 96 | 1.5x |

### 需要交互说明的概念

- 用户应该能 add/remove node。
- 应该能看到哪些 keys 被移动。
- glossary 里要解释 ring、virtual node、hot key、rebalance、replica。
- hover glossary 时，正文相关词也应能突出或定位。

## 3. Inline SVG figure sheet

写博客时需要三张图：

1. Token bucket：令牌进入桶、请求消耗令牌、超限返回 429。
2. Consistent hash ring：节点、key、移动区间。
3. Failure fanout：Gateway、bucket store、usage reporter 任一失败时的降级路径。

每张图都要是 inline SVG，可以复制单张 SVG，不依赖 Mermaid/CDN。

## 4. Annotated flowchart：deploy pipeline

部署流程：

1. `lint`：约 40s。失败路径：代码风格、未使用变量。
2. `unit-test`：约 3m。失败路径：rate limit middleware、policy resolver。
3. `integration-test`：约 8m。失败路径：Redis bucket store、429 headers。
4. `build-image`：约 2m。失败路径：Docker layer cache miss。
5. `deploy-canary`：约 5m。失败路径：health check 失败。
6. `observe`：30m。失败路径：429 spike、latency p95 超阈值。
7. `rollout`：约 10m。失败路径：error budget burn。

希望点击任意步骤时能看到：

- 该步骤跑什么命令。
- 典型耗时。
- 失败时看哪个日志。
- 谁应该处理。

## 5. Glossary

| Term | Meaning |
|---|---|
| token bucket | 用固定速率补充令牌，请求消耗令牌的限流算法 |
| retry-after | 告诉客户端多久后重试的响应头 |
| virtual node | 一个真实节点在 hash ring 上的多个位置，用来平衡分布 |
| hot key | 访问量异常高的 key |
| rebalance | 增删节点后 key 迁移的过程 |
| fail open | 限流系统故障时放行请求 |
| fail closed | 限流系统故障时拒绝请求 |

## 6. 阅读、模拟与复用难点

这份材料同时服务学习、图示复用和部署流程理解，线性文档会遇到几个问题：

- rate limiting 的请求路径、配置和 FAQ 分散在不同位置，读者很难从结论跳到证据。
- consistent hashing 的 key movement 只用文字难以理解。
- 三张图需要后续复制到博客或文档里复用。
- 部署 pipeline 既有顺序，又有命令、耗时、失败路径和 owner 等细节。
- glossary 里的概念需要和正文、图示互相定位。
