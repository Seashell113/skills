# AGENTS.md

## 项目说明

- 本仓库是个人 Claude Code / OMC skill 集合仓库。
- 根目录 `README.md` 是人类入口，维护当前 skill 清单和项目入口信息。
- 每个 skill 以 `skills/<skill-name>/SKILL.md` 为主要真源；如存在脚本、模板或参考材料，应放在对应 skill 目录内。

## 修改边界

- 修改 skill 行为前，先阅读目标 skill 的 `SKILL.md`，再检查其相邻的 `references/`、`scripts/`、`assets/` 或模板文件。
- 不要把全局 Agent 规则、当前会话指令或用户长期偏好整段复制进单个 skill；skill 只沉淀该能力本身可复用的触发、流程和边界。
- 新增或重命名 skill 时，同步更新根 `README.md` 的 skill 清单。
- `.claude/`、`.omc/`、`.obsidian/` 是本地工具状态或适配目录，不作为项目知识主真源。
- 保留用户已有未跟踪或未提交改动；只修改当前任务明确覆盖的文件。

## Agent 扩展索引

- `.agents/README.md`：如存在，先阅读；用于索引项目本地 rules、skills、hooks、commands、templates、scripts 和 adapters。
- `.agents/` 只在确有项目本地 Agent 扩展材料时创建，不为空目录占位。

## 验证要求

- 只改 Markdown 文档时，至少检查文档链接、路径和 skill 清单是否与当前目录一致。
- 修改 skill 脚本时，优先运行该 skill 自带的验证命令或最小可复现实例。
- 修改打包、安装或分发相关内容时，补充验证所依赖的命令、路径和产物位置。
