# AI Skills

可复用的 AI Agent 技能集合，面向 Claude Code、Codex 以及其他支持技能机制的 Agent 工具。

仓库地址：[Seashell113/skills](https://github.com/Seashell113/skills)

## 快速安装

推荐使用 `npx skills` 从 GitHub 仓库安装。

查看可安装的技能：

```bash
npx skills add https://github.com/Seashell113/skills.git --list
```

安装单个技能：

```bash
npx skills add https://github.com/Seashell113/skills.git -g --skill human-html-artifact
```

安装仓库内全部技能：

```bash
npx skills add https://github.com/Seashell113/skills.git -g --all
```

查看已安装技能：

```bash
npx skills list -g
```

更新时重新执行对应的 `npx skills add ...` 命令即可。

## 可用技能

| Skill | 说明 |
| --- | --- |
| `fe-code-review` | 团队前端代码审查入口，聚焦版本级审查、回归风险和合并建议 |
| `human-html-artifact` | 将复杂 Markdown 或多文档材料转为自包含 HTML 阅读页 |
| `project-knowledge-manager` | 项目知识沉淀、目录规范化、信息归位和文档审计 |
| `tech-plan-pairing` | 技术方案结对制定，适合从模糊问题逐步收敛到可落地方案 |
| `weekly-report-summary` | 通过IMAP从周报邮件中提取信息，支持团队汇总和个人周报归档 |

## 触发方式

安装后，可以直接在对话里点名技能名称，也可以用自然语言描述任务。例如：

```text
tech-plan-pairing
帮我做一次前端版本级 review
/pkm:init
把这份方案做成 HTML 阅读页
```

不同 Agent 工具对斜杠命令和技能触发的支持不完全一致。`npx skills` 安装的是技能主体，不保证自动注册所有工具的 slash command；如果短触发词无效，直接输入完整技能名称更稳定。

## 手动查看

每个技能都在 `skills/<skill-name>/` 目录下，核心说明文件是 `SKILL.md`。如果某个技能带有脚本、模板或参考材料，安装或复制时请保留整个技能目录。
