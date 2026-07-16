# 信源与搜索策略

## 原则

将“发现候选”和“证明事实”分开。聚合源、搜索结果、RSS 标题和社交媒体适合发现；最终摘要需要打开具体原文并建立 claim-level evidence。

## 精选发现层

每次运行都采样三类精选源，不等候选不足才启用：

| 来源 | 默认入口 | 主要价值 | 边界 |
| --- | --- | --- | --- |
| aihot | `https://aihot.virxact.com/api/public/items` | 中文 AI 事件密度高、发现快 | X、公众号或聚合摘要不能直接作为证据 |
| front-end-rss | `https://fed.chanceyu.com/atom.xml` | 中文前端社区和周刊覆盖 | 教程、观点和旧文比例高，需新闻性筛选 |
| BestBlogs | OpenAPI v2 | AI 筛选与人工精选后的高质量内容池 | “值得读”不等于当天新闻 |

BestBlogs 优先使用当前 OpenAPI v2 的 `resources`、`brief`、`sources` 能力；接口位于 `/openapi/v2/*`。只有安全注入 `BESTBLOGS_API_KEY` 且宿主具备带 Header 的 HTTP 能力时才调用认证接口。否则由搜索定位 BestBlogs 公共页面及其原始来源。不得把 Key 写进 URL、日志、报告或模板。

三个来源统一生成 discovery candidate，记录聚合来源与原始来源。若链接是转载或聚合页，继续追溯具体首发页。

## 官方巡检层

精选源之外，按 topic profile 巡检一手来源：

- AI coding：OpenAI/Codex、Anthropic/Claude Code、Cursor、GitHub Copilot、Kimi Code 等。
- Web platform：Chrome、WebKit、Mozilla、W3C、WHATWG。
- Framework/runtime：React、Vue、Angular、Svelte、Node.js、Deno、Bun。
- Tooling：TypeScript、Vite、Next.js、Nuxt、Astro、npm 生态。
- Security：厂商 advisory、项目公告、CVE 和权威研究机构。

“巡检”表示检查时间窗口内的 release/news/advisory 页面，不要求为所有品牌做无边界全站搜索。

## Search Router

支持四种配置：

| 模式 | 行为 |
| --- | --- |
| `auto` | 优先宿主原生搜索；不可用或覆盖明显不足时使用 AnySearch |
| `native` | 只用宿主的搜索与正文提取 |
| `anysearch` | AnySearch 负责发现，仍回到原文核验 |
| `hybrid` | 只对 P0 缺口、争议事件或评测 query 双路搜索并去重 |

AnySearch 可以通过宿主已安装 MCP、官方 AnySearch Skill 或当前官方 API 使用。优先复用现有集成，不复制其代码，也不在 Skill 中固化可能变化的 endpoint。需要密钥时只从 `ANYSEARCH_API_KEY` 环境变量读取。

默认不对全部 query 双跑。以下情况才启用 AnySearch 回退或混合：

- 宿主原生搜索失败、结果明显陈旧或无官方来源。
- P0 lane 全空。
- 需要 `cn` / `intl` 分区补漏。
- 对争议事实做独立发现路径复核。
- shadow run 比较搜索策略。

## 主题 lane

每个 lane 至少考虑一条英文事件查询和一条中文补充查询，必要时增加官方域名限制：

1. AI coding tools
2. models and AI products
3. Web platform and browsers
4. frontend frameworks and runtimes
5. tooling and package ecosystem
6. security and policy
7. industry events and frontend horizon

查询应包含实体、动作和时间意图，例如 release、launch、GA、security advisory、pricing、acquisition、new Web API。避免只用“今日 AI Web 最新动态”这类宽泛 query。

## 来源等级与核验

- **P / Primary**：官方公告、release、规范、代码仓库、安全公告、监管文件。
- **A / Authoritative**：具备原创采编或专业研究能力的权威媒体与机构。
- **B / Specialist**：高质量垂直媒体、周刊和可信技术作者。
- **C / Community**：社区、公众号、论坛、个人社媒。

产品发布、版本、价格、API 和规范优先要求 P。安全事件要求厂商/项目公告、CVE/权威研究，或两家独立高可信来源。重大商业和政策要求官方文件或两家独立权威媒体。C 级不能单独支撑最终条目。

多个页面引用同一篇原始报道不算独立来源。判断独立性时追溯信息源，而非只比较域名。

## 失败与停止

- 单个精选源失败：记录并继续其他来源。
- 搜索 provider 失败：切换可用 provider；不要反复重试相同 query。
- 动态网页无法提取：候选足够重要时才使用浏览器；否则寻找官方替代页。
- 完成一次定向补漏后停止扩张。候选丰富不等于继续搜索一定能提高质量。

## Review 信号回流

采集策略只消费与发现和取证有关的 Review 信号：`discovery_miss`、`lane_gap`、`source_failure`、`query_blind_spot`、`evidence_path_failure` 和重复 `source_noise`。候选已经进入池内但被误拒、误分级或表达不佳时，修正编辑策略，不扩大搜索。

本轮 P0 lane 为空时允许一次定向补漏。跨轮信号先进入反馈 case 和改进提案；只有在历史回放没有造成明显召回或噪声退化、且人工确认后，才调整 topic profile、query family、官方巡检入口、精选源优先级或 Search Router。不要根据单次 API 故障永久降权信源，也不要根据一条个人偏好缩窄行业视野。
