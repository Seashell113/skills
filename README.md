# AI Skills

可复用的 AI Agent 技能集合，主要沉淀我在代码审查、技术方案协作、项目知识管理、文档阅读页生成和周报处理中的稳定工作流。

每个技能都是一个独立目录，核心入口是 `SKILL.md`。不同 Agent 工具对技能目录的加载方式可能不同，本仓库优先保证技能内容本身清晰、可复制、可审查。

## 适用场景

- 想把反复出现的 Agent 工作流沉淀为可复用技能。
- 想参考现成的中文技能写法、触发描述、边界声明和执行流程。
- 想直接复用某个技能到自己的 Claude Code、Codex 或其他支持技能机制的 Agent 环境。

## Skills

| Skill | 说明 |
| --- | --- |
| `fe-code-review` | 团队前端代码审查入口，聚焦版本级审查、回归风险和合并建议 |
| `human-html-artifact` | 将复杂 Markdown 或多文档材料转为自包含 HTML 阅读页 |
| `project-knowledge-manager` | 项目知识沉淀、目录规范化、信息归位和文档审计 |
| `tech-plan-pairing` | 技术方案结对制定，适合从模糊问题逐步收敛到可落地方案 |
| `weekly-report-summary` | 从周报邮件中提取信息，支持团队汇总和个人周报归档 |

## 使用方式

1. 选择需要的技能目录，例如 `skills/project-knowledge-manager/`。
2. 按你的 Agent 工具要求，将该目录复制、软链接或安装到对应的技能目录。
3. 在对话中使用技能描述里的触发词，或直接点名技能名称。
4. 如果技能依赖脚本、模板或参考材料，保持整个技能目录一起迁移。

## 目录结构

```text
.
├── README.md
├── AGENTS.md
├── CLAUDE.md
└── skills/
    └── <skill-name>/
        ├── SKILL.md
        ├── references/
        ├── scripts/
        └── assets/
```

其中 `references/`、`scripts/`、`assets/` 都是按需存在的可选目录。

## 维护约定

- `SKILL.md` 是每个技能的主要真源。
- 新增、删除或重命名技能时，同步更新本 README 的技能清单。
- 技能应写清楚触发场景、适用边界、执行流程和安全约束。
- 脚本、模板、参考材料应放在对应技能目录内，避免依赖仓库外的隐式文件。

## Agent 入口

- `AGENTS.md`：Agent 修改本仓库前的项目级约束。
- `CLAUDE.md`：Claude Code 适配入口，薄引用 `AGENTS.md`。

## 许可证

当前仓库尚未声明开源许可证。正式开源发布前，请根据预期授权方式补充 `LICENSE` 文件。
