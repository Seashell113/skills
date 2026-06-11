# Seashell's Skills

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Skills](https://img.shields.io/badge/skills-6-brightgreen.svg)](#skill-清单)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-orange.svg)](CONTRIBUTING.md)

可复用的 AI Agent 技能（Skill）集合，面向 Claude Code、Codex 以及其他支持技能机制的 Agent 工具。

## 什么是 Skill

Skill 是给 AI Agent 读的能力说明书：每个技能以一份 `SKILL.md` 为核心，定义触发条件、工作流程、行为边界和输出约定，并可附带脚本、提示词、参考材料和评估用例。安装到 Agent 工具后，Agent 会在匹配的任务场景中自动加载并按其执行。

本仓库收录的技能来自日常真实工作流：代码审查、技术方案制定、文档治理、阅读交付、使用分析、周报自动化。所有技能的指令和输出默认为**中文**。

## Skill 清单

| Skill | 说明 | 适用范围 |
| --- | --- | --- |
| [human-html-artifact](skills/human-html-artifact/) | 将复杂 Markdown 或多文档材料转为自包含 HTML 阅读页 | 通用 |
| [tech-plan-pairing](skills/tech-plan-pairing/) | 技术方案结对制定，从模糊问题多轮收敛到可落地方案 | 通用 |
| [project-knowledge-manager](skills/project-knowledge-manager/) | 项目知识沉淀、目录规范化、信息归位和文档审计 | 通用 |
| [insights-aggregator](skills/insights-aggregator/) | 汇总 Claude Code 与 Codex 本地会话，生成跨工具使用洞察 HTML 报告 | 通用（需 Python 3） |
| [fe-code-review](skills/fe-code-review/) | 前端版本级代码审查：回归风险、影响面与合并建议 | 团队定制 |
<!-- | [weekly-report-summary](skills/weekly-report-summary/) | 从周报邮件提取信息，团队汇总出 Word / 个人归档出 Markdown | 特定环境（阿里企业邮箱） | -->

适用范围说明：

- **通用**：开箱即用，不依赖特定团队或环境。
- **团队定制**：审查口径、输出结构按特定团队习惯设计，可借用框架后按需调整。
- **特定环境**：依赖特定服务或私有约定（如企业邮箱、内部模板），更适合作为参考实现。

每个技能目录内的 `README.md` 有面向使用者的详细介绍（前置条件、使用示例、目录说明）。

## 安装

### 方式一：npx skills（推荐）

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

### 方式二：手动复制

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

[MIT](LICENSE)
