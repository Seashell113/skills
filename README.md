# Seashell's Skills

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Public Skills](https://img.shields.io/badge/public_skills-11-brightgreen.svg)](#skill-清单)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-orange.svg)](CONTRIBUTING.md)

可复用的 AI Agent 技能（Skill）集合，面向 Claude Code、Codex 以及其他支持技能机制的 Agent 工具。

这些 skill 不是一套强行完整的开发方法论，而是从真实工作场景里沉淀出来的可复用能力：有的用于阅读交付，有的用于技术讨论，有的用于项目知识治理、代码审查或个人自动化。这个 README 帮你快速判断每个 skill 的定位、适用场景、使用方式和预期产出。

## 什么是 Skill

Skill 是给 AI Agent 读的能力说明书：每个技能以一份 `SKILL.md` 为核心，定义触发条件、工作流程、行为边界和输出约定，并可附带脚本、提示词、参考材料和评估用例。安装到 Agent 工具后，Agent 会在匹配的任务场景中自动加载并按其执行。

本仓库收录的技能来自日常真实工作流：代码审查、技术方案制定、文档治理、阅读交付和使用分析。所有技能的指令和输出默认为**中文**。

## Skill 清单

| 场景 | Skill | 适合什么时候用 | 典型产出 |
| --- | --- | --- | --- |
| 会话治理 | [codex-thread-organizer](skills/codex-thread-organizer/) | Codex 会话需要命名、收口、handoff 或回溯 | 会话标题、收口摘要、交接包 |
| 模型协作 | [codex-chatgpt-dispatch](skills/codex-chatgpt-dispatch/) | 需要把 Codex 本地现场交给 ChatGPT 网页指定档位完成复审或生图 | handoff、文本或图片结果、本地核验结论 |
| 阅读交付 | [human-html-artifact](skills/human-html-artifact/) | 长文档、方案、review 或多文档摘录难以线性阅读 | 自包含 HTML 阅读页 |
| 本地自动化 | [codex-quota-inspector](skills/codex-quota-inspector/) | 查询 Codex 普通额度和 ChatGPT 免费重置机会 | 脱敏额度快照 |
| 本地自动化 | [invoice-reimbursement-bundler](skills/invoice-reimbursement-bundler/) | 本地发票 PDF 需要统计、查重、凑金额和打包 | 报销组合、结果目录 |
| Skill 建设 | [skill-creator](skills/skill-creator/) | 创建、改造、评估或优化一个 skill | `SKILL.md`、测试 prompt、评测结果 |
| 技术决策 | [tech-plan-pairing](skills/tech-plan-pairing/) | 技术方向还模糊，需要多轮澄清和方案取舍 | 技术方案、决策记录、待验证项 |
| 知识治理 | [project-knowledge-manager](skills/project-knowledge-manager/) | 项目 README、AGENTS、docs、模块知识需要归位或审计 | 初始化计划、文档更新、审计报告 |
| 使用复盘 | [insights-aggregator](skills/insights-aggregator/) | 想分析 Claude Code 与 Codex 的本地使用情况 | 跨工具洞察 HTML 报告 |
| 行业资讯 | [web-ai-daily-paper](skills/web-ai-daily-paper/) | 生成 AI/Web 早报、审阅入选与落选候选、用人工理由持续校准策略 | 中文早报、Review、证据包、反馈 case |
| 代码审查 | [fe-code-review](skills/fe-code-review/) | 前端分支、PR 或版本实现需要版本级审查 | 中文 review 报告、风险与合并建议 |

适用范围说明：

- **通用**：开箱即用，不依赖特定团队或环境。
- **团队定制**：审查口径、输出结构按特定团队习惯设计，可借用框架后按需调整。
- **特定环境**：依赖特定服务或私有约定（如企业邮箱、内部模板），更适合作为参考实现。

公开清单只列出适合复用或参考的 skills；少量个人环境专用目录仅用于多设备同步，不作为公开推荐。每个 skill 以 `SKILL.md` 作为 agent 主真源；目录内 `README.md` 面向人类使用者，说明前置条件、使用示例和目录结构。第三方固定快照以保留上游目录为优先，来源和更新规则见 `docs/contributing/`。

## Skill 简介与示例

### codex-chatgpt-dispatch

**定位**：Codex 到 ChatGPT 网页的证据化调度协议。

**适合场景**：需要把当前会话、仓库与验证现场交给用户指定且页面实际可用的 ChatGPT 档位完成评审，或通过同一网页调度链生成图片，再回到本地核验结果。

**你可以这样说**：

```text
$codex-chatgpt-dispatch 把当前方案和关键证据交给 Pro 做一次独立审查，拿到结果后回来核验
$codex-chatgpt-dispatch 用新增 Spike 结果在原对话继续讨论一轮
$codex-chatgpt-dispatch 用页面当前非 Pro 档位生成一张配图，保存后在本地检查
```

**产出效果**：按任务需要准备直接提示词、`handoff.txt` 或续评证据桥；附件任务开始时静默核对官方 IAB 能力边界和本机版本，当前仍不支持时给出按目录分组、可直接复制选择的上传卡并保留侧栏标签页，用户上传一次后由 Browser 核对；随后在普通 ChatGPT 网页只提交一次并同页等待，最终取得文本回复或本地图片文件并完成核验。

**依赖与边界**：真实提交只支持 ChatGPT 桌面中的 Codex + 内置 Browser；当前 IAB 不自动上传附件，人工上传完成的调度单独标记为“人工辅助调度成功”。静默预检仅在实际附件任务开始时运行，版本变化不等于能力恢复；发现官方恢复信号后仍需用户授权一次无敏感探测。显式触发不等于发送授权。目标档位不可用、Browser 主链不可用或发送状态不唯一时停止，不静默降级、重发或切换链路。侧栏优先可见，但显隐不作为成功判据。

详情：[README](skills/codex-chatgpt-dispatch/README.md) / [SKILL.md](skills/codex-chatgpt-dispatch/SKILL.md)

### codex-thread-organizer

整理 Codex 会话标题、连续编号、收口摘要、交接包和回溯索引。默认先扫描最近 10 个线程的标题、预览和项目，只有异常项才限量补读；主题、类别、关联或编号不确定时会进入 `needs-review`。

示例：

```text
scan
先预览最近 10 个会话的高置信改名建议，跳过 Automation 和 needs-review
```

### human-html-artifact

**定位**：复杂 Markdown 材料的 HTML sidecar 视图生成器。

**适合场景**：技术方案、调研材料、PR/MR review、状态报告、设计说明、多文档摘录。原文通常有多阶段、多风险、多方案对比、多字段或多角色视角，直接读 Markdown 成本高。

**你可以这样说**：

```text
把这份 MR review 整理成一个给团队评审用的 HTML 页面
把这份技术方案做成一个老板和研发都能快速审阅的 HTML 报告
```

**产出效果**：单文件 `.html`，可离线打开；按内容形状组织导航、重点、风险、证据、对照、筛选和复制能力。

**边界**：不适合普通 Markdown 预览、README 维护、纯文本 diff 或长期维护的前端应用。

详情：[README](skills/human-html-artifact/README.md) / [SKILL.md](skills/human-html-artifact/SKILL.md)

### codex-quota-inspector

只读查询本机 Codex 普通额度、5 小时/7 天窗口和 ChatGPT 免费重置机会。适合需要快速了解当前额度状态，同时避免泄露 `access_token`、`refresh_token`、`account_id` 等敏感值的场景。

示例：

```text
帮我查一下当前 Codex 额度和免费重置机会，注意不要输出任何 token 或 account_id
```

### invoice-reimbursement-bundler

**定位**：本地发票 PDF 的报销打包助手。

**适合场景**：统计发票总额、按发票号查重、凑一个不低于目标金额且超出最少的报销组合，把选中的 PDF 复制或移动到结果目录。

**你可以这样说**：

```text
帮我从这个目录里凑一组 3000 元左右的发票，要求不要重复报销
/invoice-bundle
帮我统计 ~/Documents/发票 里一共有多少钱
```

**产出效果**：先给扫描预览和组合方案；你确认后再复制或移动文件。默认不删除、不清理旧目录。

**依赖与边界**：需要 Python 3 + `pdfplumber`；只读 PDF 文本，不做 OCR、税务查验或真伪校验。

详情：[README](skills/invoice-reimbursement-bundler/README.md) / [SKILL.md](skills/invoice-reimbursement-bundler/SKILL.md)

### skill-creator

**定位**：创建、改造、评估和优化 skill 的标准流程。

**适合场景**：你想把一个重复工作流沉淀成 skill，或希望改进已有 skill 的触发描述、结构、测试 prompt 和评测口径。

**你可以这样说**：

```text
我想做一个处理本地发票报销的 skill，帮我从需求开始一起设计
帮我评估这个 skill 的触发是否准确，并给出改进建议
```

**产出效果**：更清晰的 `SKILL.md`、真实测试 prompt、评测或人工审阅建议；适合把经验从“一段提示词”升级为可复用能力。

**边界**：这是第三方固定上游快照，本仓库保留其原始结构；仓库内的个人定制规则不写入该目录。

详情：[SKILL.md](skills/skill-creator/SKILL.md) / [来源与更新规则](docs/contributing/skill-creator-upstream.md)

### tech-plan-pairing

**定位**：技术方案结对制定，从模糊问题多轮收敛到可落地方案。

**适合场景**：工具链选型、架构设计、技术迁移、流程规范、技术债治理；也适合拿到一版初稿后，先回到问题定义重新校准。

**你可以这样说**：

```text
我们团队想统一前端请求层，先别写方案，先和我一起把问题想清楚
有人建议我们迁移到 monorepo，你先帮我一起判断约束和取舍
```

**产出效果**：问题定义、约束清单、备选方案对比、风险和验证项，必要时落成分层技术方案。

**边界**：不适合纯 code review、成熟方案的执行跟踪、单一明确问题的快速问答。

详情：[README](skills/tech-plan-pairing/README.md) / [SKILL.md](skills/tech-plan-pairing/SKILL.md)

### project-knowledge-manager

**定位**：项目知识沉淀与文档治理，让长期有效的信息有明确归属。

**适合场景**：新项目初始化 README / AGENTS / CLAUDE / docs；老项目文档混乱、双写、过期；一轮讨论结束后需要把有效信息沉淀到项目文档。

**你可以这样说**：

```text
/pkm:init
帮这个仓库建立一套清晰的项目知识入口
/pkm:audit
审计一下这个项目的 README、AGENTS 和 docs 是否职责清晰
```

**产出效果**：初始化或规范化计划、候选写入项、确认后的文档更新、P0-P3 文档审计报告。

**边界**：默认先计划、确认后写入；不创建空目录占位，不把全局 Agent 规则或用户长期偏好整段复制进项目。

详情：[README](skills/project-knowledge-manager/README.md) / [SKILL.md](skills/project-knowledge-manager/SKILL.md)

### insights-aggregator

**定位**：跨工具 AI 编程助手使用洞察分析。

**适合场景**：想复盘 Claude Code 与 Codex 的使用习惯、任务类型、项目分布、工具分工、接力模式和改进空间。

**你可以这样说**：

```text
分析一下我最近 Claude Code 和 Codex 的使用情况，生成一份 insights 报告
/insights
生成最近一个月的跨工具使用洞察
```

**产出效果**：本地自包含 HTML 报告，包含统计、语义 facets、跨工具对比和阶段性建议。

**依赖与边界**：需要 Python 3；只读本地会话记录，报告会包含项目路径和会话摘要，分享前需要自行检查敏感信息。

详情：[README](skills/insights-aggregator/README.md) / [SKILL.md](skills/insights-aggregator/SKILL.md)

### web-ai-daily-paper

**定位**：面向 AI/Web 从业者的行业早报采集、核验、筛选和持续校准流程。

**适合场景**：生成工作日 AI/Web 早报，补充模型、AI 编程工具、Web 平台、前端框架、工程化、安全和行业事件视野；查看最终入选、自主 Review 变化与高排名未入选候选；反馈漏选、内容太水、事实边界或判断理由。

**你可以这样说**：

```text
生成今天的 AI/Web 早报，完成证据核验和自主 Review
查看今天的 Review，我想知道哪些候选没入选以及原因
第 3 条结论对，但真正值得关注的是行业热度，不是和当前项目相关；其余认可
```

**产出效果**：带具体原文的中文早报，以及候选、证据、入选、拒绝、Review 和反馈 case。Review 使用连续编号，并把人工对“结论”和“理由”的校准分开保存。

**依赖与边界**：需要宿主具备网页搜索、正文读取和持久文件写入能力；BestBlogs 与 AnySearch Key 都是可选增强。聚合源只负责发现，最终事实回到具体原文；生产规则不会根据单次反馈自动改写。Skill 带 Hermes blueprint，可配置工作日调度和原会话投递，也可被其他支持 Agent Skills 的工具复用。

详情：[SKILL.md](skills/web-ai-daily-paper/SKILL.md)

### fe-code-review

**定位**：前端版本级代码审查入口，重点看整体影响、回归风险和合并建议。

**适合场景**：审查前端分支、PR、MR、版本实现或相对 `master` 的改动，需要给出非作者也能读懂的风险判断。

**你可以这样说**：

```text
帮我 review 这个前端分支相对 master 的改动，重点看回归风险
review 一下这个 PR 的整体影响和合并风险
```

**产出效果**：中文审查报告，包含决策摘要、P0-P3 findings、置信度、阻塞性、四档合并建议和建议回归路径。

**边界**：审查口径按特定前端团队习惯设计；其他团队可借用框架，但建议调整严重级别和合并建议规则。

详情：[README](skills/fe-code-review/README.md) / [SKILL.md](skills/fe-code-review/SKILL.md)

## 安装

### 方式一：让 Agent 辅助安装（推荐）

最推荐的方式是直接让当前 Agent 帮你安装或更新。这样 Agent 可以根据你的工具环境选择合适的目标 agent，执行安装命令，并把结果和失败原因反馈给你。

示例：

```text
请帮我从 https://github.com/Seashell113/skills.git 安装 human-html-artifact skill
```

```text
请先列出 https://github.com/Seashell113/skills.git 里可安装的 skills，再帮我安装 tech-plan-pairing
```

```text
请帮我更新这个仓库里已经安装过的 skills
```

Agent 通常会在后台使用 `npx skills add ...` 完成安装。你可以要求它先列出计划和命令，再确认执行。

### 方式二：npx skills

查看可安装的技能：

```bash
npx skills add https://github.com/Seashell113/skills.git --list
```

安装单个技能：

```bash
npx skills add https://github.com/Seashell113/skills.git -g --skill human-html-artifact
```

安装全部技能：

```bash
npx skills add https://github.com/Seashell113/skills.git -g --all
```

查看已安装技能：

```bash
npx skills list -g
```

更新时重新执行对应的 `npx skills add ...` 命令即可。

### 方式三：手动复制

把整个技能目录复制到 Agent 工具的技能目录，例如 Claude Code：

```bash
cp -r skills/human-html-artifact ~/.claude/skills/
```

注意保留完整目录——部分技能依赖目录内的 `scripts/`、`references/`、`prompts/` 等材料。

## 触发方式

安装后，可以直接在对话里点名技能名称，也可以用自然语言描述任务：

```text
tech-plan-pairing
帮我做一次前端版本级 review
/pkm:init
把这份方案做成 HTML 阅读页
```

不同 Agent 工具对斜杠命令和技能触发的支持不完全一致。`npx skills` 安装的是技能主体，不保证自动注册所有工具的 slash command；如果短触发词无效，直接输入完整技能名称更稳定。

## 仓库结构

```text
skills/
├── README.md                  # 本文件：项目入口与 skill 清单
├── LICENSE                    # MIT
├── CONTRIBUTING.md            # 贡献指南与 skill 编写规范
├── AGENTS.md                  # Agent 修改本仓库时的约束
├── docs/
│   └── contributing/          # 贡献流程、第三方快照来源和更新规则
├── templates/
│   └── skill-template/        # 新 skill 起步模板
└── skills/
    └── <skill-name>/
        ├── SKILL.md           # 主真源：给 agent 读的指令
        ├── README.md          # 给人读的介绍
        ├── references/        # 按需加载的细则材料（可选）
        ├── scripts/           # 可执行脚本（可选）
        ├── prompts/           # 子 agent 提示词（可选）
        ├── assets/            # 模板等静态材料（可选）
        └── evals/             # 触发与行为评估用例（可选）
```

## 贡献

如有改进意见，欢迎提 Issue 反馈。

## License

本仓库自研内容默认使用 [MIT](LICENSE)。第三方固定快照保留其目录内自带许可证；例如 `skills/skill-creator/` 随目录保留 Apache License 2.0 的 `LICENSE.txt`。
