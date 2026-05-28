# CheckoutBanner 重构评审材料：代码理解、PR 评审与设计系统

> 背景：团队把散落的 banner 逻辑迁移到统一组件，同时要确认设计 token、组件 variants 和调用链影响。
> 受众：PR reviewer、组件库维护者、业务接入方、设计系统负责人。

## 1. PR 背景

当前 checkout 页顶部有三套 banner：

- `PromoBanner`：营销活动提示。
- `RiskBanner`：风控拦截提示。
- `InventoryBanner`：库存不足提示。

重构目标是合并成 `CheckoutBanner`，减少重复样式和重复埋点。

## 2. 关键 diff

文件：`src/checkout/components/RiskBanner.tsx`

```diff
- export function RiskBanner({ reason, onAppeal }) {
-   return (
-     <div className="risk-banner">
-       <strong>Payment blocked</strong>
-       <span>{reason}</span>
-       <button onClick={onAppeal}>Appeal</button>
-     </div>
-   )
- }
+ export function RiskBanner({ reason, onAppeal }) {
+   return (
+     <CheckoutBanner
+       tone="critical"
+       title="Payment blocked"
+       description={reason}
+       action={{ label: 'Appeal', onClick: onAppeal }}
+     />
+   )
+ }
```

文件：`src/checkout/components/CheckoutBanner.tsx`

```diff
+ export function CheckoutBanner({ tone, title, description, action }) {
+   const icon = tone === 'critical' ? AlertTriangle : Info;
+   return (
+     <section className={`checkout-banner checkout-banner--${tone}`}>
+       {icon}
+       <div>
+         <h3>{title}</h3>
+         <p>{description}</p>
+       </div>
+       {action ? <button onClick={action.onClick}>{action.label}</button> : null}
+     </section>
+   )
+ }
```

评审关注：

- `icon` 当前是组件引用，不是 JSX 节点，可能渲染失败。
- `section` 没有 `aria-live`，风险 banner 变更时读屏器可能不提示。
- `action` 只支持单按钮，库存场景需要「查看替代商品」和「继续购买」两个动作。

## 3. 作者需要的 PR 说明

需要补齐一段 reviewer 可直接读的 PR 说明，包含：

- Motivation：三套 banner 样式和埋点重复，修改成本高。
- Before / After：从三个业务组件内联样式，变成统一 `CheckoutBanner`。
- File tour：
  - `CheckoutBanner.tsx`：新增统一组件。
  - `RiskBanner.tsx`：迁移到 critical tone。
  - `PromoBanner.tsx`：迁移到 promo tone。
  - `InventoryBanner.tsx`：迁移到 warning tone。
  - `checkoutBanner.css`：新增 token 驱动样式。
- Review focus：
  - icon 渲染是否正确。
  - accessibility 是否足够。
  - 多 action 场景是否应该现在支持。
  - 旧埋点字段是否保留。

## 4. 模块地图素材

```
CheckoutPage
  -> CheckoutSummary
  -> PromoBanner
  -> RiskBanner
  -> InventoryBanner
  -> CheckoutBanner
      -> checkoutBanner.css
      -> design tokens
      -> analytics.track('checkout_banner_view')
```

热路径：

`CheckoutPage -> RiskBanner -> CheckoutBanner -> action click -> appeal modal`

入口点：

- `src/checkout/CheckoutPage.tsx`
- `src/checkout/components/RiskBanner.tsx`
- `src/checkout/components/PromoBanner.tsx`
- `src/checkout/components/InventoryBanner.tsx`

## 5. 设计 token

| Token | Value | Usage |
|---|---|---|
| `color.banner.info.bg` | `#EEF5FF` | 默认提示背景 |
| `color.banner.info.text` | `#1E3A5F` | 默认提示正文 |
| `color.banner.warning.bg` | `#FFF7E6` | 库存提醒背景 |
| `color.banner.warning.text` | `#7A4A00` | 库存提醒正文 |
| `color.banner.critical.bg` | `#FDECEC` | 风控拦截背景 |
| `color.banner.critical.text` | `#7F1D1D` | 风控拦截正文 |
| `space.banner.x` | `16px` | 横向内距 |
| `space.banner.y` | `12px` | 纵向内距 |
| `radius.banner` | `8px` | 圆角 |
| `font.banner.title` | `14px / 600` | 标题 |
| `font.banner.body` | `13px / 400` | 描述 |

## 6. Component variants

需要评审 `CheckoutBanner` 所有状态：

| Size | Tone | State | Action |
|---|---|---|---|
| compact | info | default | none |
| compact | warning | default | single |
| compact | critical | loading | single |
| regular | info | default | single |
| regular | warning | default | two actions |
| regular | critical | error | single |
| regular | critical | disabled | single disabled |

## 7. 埋点兼容

旧字段：

```json
{
  "event": "risk_banner_view",
  "risk_reason": "payment_blocked",
  "order_id": "O-10091"
}
```

新字段：

```json
{
  "event": "checkout_banner_view",
  "banner_tone": "critical",
  "banner_source": "risk",
  "order_id": "O-10091"
}
```

风险：旧 dashboard 依赖 `risk_banner_view`。建议至少双写一版。

## 8. 阅读与评审难点

这份材料同时包含代码风险、模块关系、设计 token、组件状态和埋点兼容。线性阅读时有几个问题：

- diff 风险、模块路径和组件状态分散在不同小节，reviewer 很难快速建立主路径。
- token 表和 variants 表只靠文字不容易比较状态覆盖。
- 旧埋点和新埋点需要并排看，才能判断 dashboard 兼容风险。
- 文件路径、token 名、JSON 和 diff 后续都可能被复制到 review 评论、修复任务或设计系统记录中。
