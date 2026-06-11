# project-knowledge-manager

> 团队项目知识沉淀与文档治理：让每类重要信息都有唯一、可信、可维护的归属。**通用 skill**，不依赖特定环境。

## 是什么

帮助项目把长期有效的信息放到正确位置的 skill。它维护一套目录职责模型（`README.md` / `AGENTS.md` / `CLAUDE.md` / `openspec/` / `docs/` / `.agents/` / 模块 README），并提供三条工作流：

- **初始化 / 规范化**（`/pkm:init`）：检查项目现状，输出写入计划，确认后落盘
- **对话信息提取**（`/pkm:collect`）：把讨论内容拆成事实 / 判断 / 待决问题 / 行动项，逐条归位
- **文档审计**（`/pkm:audit`）：用自带脚本 + 语义审查检测双写、过期、职责不清等问题，按 P0–P3 分级输出报告

默认"先计划、确认后写入"，不创建空目录占位，不把全局规则复制进项目。

## 何时用

- 新项目要初始化文档结构，或老项目文档混乱想规范化
- 一轮讨论结束，想"把刚才的内容沉淀到项目文档里"
- 怀疑项目文档有双写、过期或归位错误，想做一次审计

## 安装

```bash
npx skills add https://github.com/Seashell113/skills.git -g --skill project-knowledge-manager
```

## 使用示例

```text
/pkm:init
/pkm:collect 把刚才关于部署流程的讨论整理到项目文档
/pkm:audit
```

短触发词不被工具识别时，直接说"项目知识管理 skill"或完整名称 `project-knowledge-manager`。

## 目录说明

| 路径 | 用途 |
| --- | --- |
| `SKILL.md` | skill 主体指令（给 agent 读） |
| `references/directory-model-v1.1.md` | 目录职责模型完整定义 |
| `references/templates.md` | 各类文档的起草模板 |
| `references/commands.md` | `/pkm:*` 命令说明 |
| `assets/commands/` | `/pkm:*` 命令模板（可选适配材料） |
| `scripts/project_knowledge_audit.py` | 结构审计脚本（Python 3） |
| `evals/evals.json` | 评估用例 |
