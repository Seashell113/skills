# Seashell's Skills

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Public Skills](https://img.shields.io/badge/public_skills-8-brightgreen.svg)](#skill-清单)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-orange.svg)](CONTRIBUTING.md)

可复用的 AI Agent 技能（Skill）集合，面向 Claude Code、Codex 以及其他支持技能机制的 Agent 工具。

## 什么是 Skill

Skill 是给 AI Agent 读的能力说明书：每个技能以一份 `SKILL.md` 为核心，定义触发条件、工作流程、行为边界和输出约定，并可附带脚本、提示词、参考材料和评估用例。安装到 Agent 工具后，Agent 会在匹配的任务场景中自动加载并按其执行。

本仓库收录的技能来自日常真实工作流：代码审查、技术方案制定、文档治理、阅读交付和使用分析。所有技能的指令和输出默认为**中文**。

## Skill 清单

| Skill | 说明 | 适用范围 |
| --- | --- | --- |
| [codex-thread-organizer](skills/codex-thread-organizer/) | 维护 Codex 会话标题、收口摘要、handoff 和回溯索引 | 个人工作流 |
| [human-html-artifact](skills/human-html-artifact/) | 将复杂 Markdown 或多文档材料转为自包含 HTML 阅读页 | 通用 |
| [invoice-reimbursement-bundler](skills/invoice-reimbursement-bundler/) | 扫描、查重、组合发票 PDF，生成报销目录 | 通用（需 Python 3 + pdfplumber） |
| [skill-creator](skills/skill-creator/) | 创建、改造、评估和优化 skill 的标准流程与配套脚本 | 通用（第三方固定快照，需 Python 3.10+） |
| [tech-plan-pairing](skills/tech-plan-pairing/) | 技术方案结对制定，从模糊问题多轮收敛到可落地方案 | 通用 |
| [project-knowledge-manager](skills/project-knowledge-manager/) | 项目知识沉淀、目录规范化、信息归位和文档审计 | 通用 |
| [insights-aggregator](skills/insights-aggregator/) | 汇总 Claude Code 与 Codex 本地会话，生成跨工具使用洞察 HTML 报告 | 通用（需 Python 3） |
| [fe-code-review](skills/fe-code-review/) | 前端版本级代码审查：回归风险、影响面与合并建议 | 团队定制 |

适用范围说明：

- **通用**：开箱即用，不依赖特定团队或环境。
- **团队定制**：审查口径、输出结构按特定团队习惯设计，可借用框架后按需调整。
- **特定环境**：依赖特定服务或私有约定（如企业邮箱、内部模板），更适合作为参考实现。

公开清单只列出适合复用或参考的 skills；少量个人环境专用目录仅用于多设备同步，不作为公开推荐。多数自研技能目录内的 `README.md` 有面向使用者的详细介绍（前置条件、使用示例、目录说明）。第三方固定快照以保留上游目录为优先，来源和更新规则见 `docs/contributing/`。

## Skill 简介与示例

### codex-thread-organizer

整理 Codex 会话标题、收口摘要、交接包和回溯索引。适合长期主题被拆成多个线程后，快速区分主线、测试、安装、回归和历史会话。

示例：

```text
codex-thread-organizer:closeout
按命名规则收口这个会话，并给出下一会话交接包
```

### human-html-artifact

把长篇 Markdown、方案、调研、review 或状态报告重构成自包含 HTML 阅读页。适合信息层级多、字段交叉、需要筛选/对比/下钻/复制的材料。

示例：

```text
把这份 MR review 整理成一个给团队评审用的 HTML 页面
```

### invoice-reimbursement-bundler

处理本地发票 PDF：扫描金额、按发票号去重、组合出接近目标金额的报销包，并复制或移动选中的发票。

示例：

```text
帮我从这个目录里凑一组 3000 元左右的发票，要求不要重复报销
```

### skill-creator

创建或改造 skill 的标准流程。它会帮助澄清触发场景、编写 `SKILL.md`、设计真实测试 prompt、组织评测和人工审阅。

示例：

```text
我想做一个处理本地发票报销的 skill，帮我从需求开始一起设计
```

### tech-plan-pairing

用于技术方案结对制定。适合从模糊问题、分歧方案或初稿出发，逐步收敛目标、约束、风险、取舍和落地计划。

示例：

```text
我们团队想统一前端请求层，先别写方案，先和我一起把问题想清楚
```

### project-knowledge-manager

用于项目知识沉淀和文档治理。适合初始化或审计 README、AGENTS、CLAUDE、docs、模块 README 等长期知识入口。

示例：

```text
/pkm:init
帮这个仓库建立一套清晰的项目知识入口
```

### insights-aggregator

分析本地 Claude Code 与 Codex 使用记录，生成跨工具使用洞察 HTML 报告。适合复盘 agent 使用习惯、任务类型、协作模式和改进空间。

示例：

```text
分析一下我最近 Claude Code 和 Codex 的使用情况，生成一份 insights 报告
```

### fe-code-review

前端版本级代码审查入口，重点看功能正确性、整体影响面、回归风险和合并建议。该 skill 带有团队审查口径，公开使用时可借用框架后按需调整。

示例：

```text
帮我 review 这个前端分支相对 master 的改动，重点看回归风险
```

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
