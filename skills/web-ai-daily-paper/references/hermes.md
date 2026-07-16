# Hermes 适配与部署

核心筛选、证据、Review 和反馈协议与平台无关。本文件只描述 Hermes 的薄适配。

## 工具依赖

frontmatter 声明 `requires_toolsets: [web, file]`：

- `web_search` 用于发现候选。
- `web_extract` 用于打开网页和 PDF 正文。
- file toolset 用于 runtime home、状态和 run 产物。

浏览器不是默认依赖。只有重要候选无法通过正文提取读取时，才在具备 browser toolset 的环境降级使用。

AnySearch 是可选 provider：优先使用已配置 MCP 或官方 AnySearch Skill；没有时使用 Hermes 原生搜索。不要让 `web-ai-daily-paper` 硬依赖另一个 Skill。

## Config 与密钥

非敏感设置使用 `skills.config.web_ai_daily_paper.*`：

- `timezone`
- `search_mode`
- `review_shortlist_size`

BestBlogs 和 AnySearch 都是可选增强，缺失时不阻止 Skill 加载和运行。为保持通用 Agent Skills frontmatter 兼容，本 Skill 不声明 Hermes 专属的顶层 `required_environment_variables`；部署者应通过 Hermes 本机 `.env` 或等价安全注入配置 `BESTBLOGS_API_KEY`、`ANYSEARCH_API_KEY`，并按 Hermes sandbox env passthrough 规则传递。

生产 Skill、cron prompt、profile、run 产物和消息中均不得出现 Key。

## Blueprint

Skill frontmatter 提供工作日 08:28 的 blueprint：

```yaml
metadata:
  hermes:
    blueprint:
      schedule: "28 8 * * 1-5"
      deliver: origin
      prompt: 生成今天的 AI/Web 早报，完成证据核验、自主 Review 和运行产物留档；只返回正式早报正文。
      no_agent: false
```

Blueprint 是安装建议，不应静默创建 cron。部署者接受后再显式设置目标平台、provider 和 model。

## Cron 部署建议

- schedule：`28 8 * * 1-5`
- timezone：`Asia/Shanghai`
- attached skill：`web-ai-daily-paper`
- prompt：保持任务说明简短，不复制整个 Skill。
- provider/model：显式固定，避免无人值守任务因全局模型切换失败关闭。
- delivery：生产使用 `dingtalk:<chat_id>`；chat id 不写入仓库。
- `wrap_response=false`：让正式群只收到早报正文。

Cron 在 fresh session 中运行。所有跨天信息来自 runtime home，不依赖聊天历史。

## 状态与投递边界

Hermes 在 Agent 最终响应后执行 delivery，因此 Skill 只能在响应前记录 `report_committed`。不要写 `delivered=true`。

投递失败时：

1. 保留 cron 输出和 Skill run。
2. 从 `report.txt` 手动重发。
3. 不重新采集、不新增 event milestone。

## 交互式 Review 和反馈

用户可以在任意 Hermes 会话中说：

- “查看今天的早报 Review。”
- “为什么 Review 第 4 条没入选？”
- “这条太水，以后类似的不要补位。”
- “根据最近反馈优化早报 Skill。”

Agent 从 runtime home 解析最近 run 和 feedback case。DingTalk 不可靠地提供 thread 上下文时，用标题、URL 或最近 run 自动定位；仍有歧义再追问。

## 通用 Agent 使用

忽略 Hermes 专属 frontmatter 的 Agent 仍可执行核心流程，只需具备：

- 网页搜索或等价发现能力。
- 网页正文提取。
- 持久文件读写。

调度、投递和密钥注入由宿主平台负责。若宿主没有 post-response delivery，仍保持“先 commit run，再调用平台发送”的顺序，并诚实记录发送状态。
