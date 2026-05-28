# 目录模型 v1.1

本文是《团队项目知识沉淀与 Agent 协作目录规范》v1.1 的执行摘要，供 skill 做目录初始化、信息归位和审计时使用。

## 目标

- 人能快速理解项目如何运行。
- Agent 能安全进入项目并避免高风险误改。
- 需求规格、长期知识、执行规则各有唯一归属。
- 目录按信息密度渐进创建，不为形式完整制造空目录。

## 最小结构

```text
.
├── README.md
├── AGENTS.md
├── CLAUDE.md
└── src/
```

`CLAUDE.md` 默认只写：

```md
@AGENTS.md
```

只有确有 Claude Code 专属要求时，才在后面追加简短补充。

最小 `AGENTS.md` 固定包含 `.agents/` 索引位：说明 `.agents/README.md` 如存在应先阅读，并说明 `.agents/` 承载项目本地 rules、skills、hooks、commands、templates、scripts 和 adapters。没有真实内容时不创建 `.agents/` 空目录。

## 可扩展结构

```text
.
├── README.md
├── AGENTS.md
├── CLAUDE.md
├── openspec/
│   ├── config.yaml
│   ├── specs/
│   └── changes/
├── docs/
│   ├── README.md
│   ├── context/
│   ├── standards/
│   ├── runbooks/
│   └── adr/
├── .agents/
│   ├── README.md
│   ├── rules/
│   ├── skills/
│   ├── hooks/
│   ├── commands/
│   ├── templates/
│   ├── scripts/
│   └── adapters/
└── src/
    └── views/
        └── SomeModule/
            ├── README.md
            └── AGENTS.md
```

除 `README.md`、`AGENTS.md`、`CLAUDE.md` 外，其余目录都按真实需要创建。

## 职责表

| 位置 | 职责 | 创建信号 |
|---|---|---|
| `README.md` | 人类项目入口：项目是什么、技术栈、启动方式、常用命令、关键链接 | 默认创建 |
| `AGENTS.md` | Agent 项目入口：项目特异上下文、硬约束、高风险区域、`.agents/` 索引和验证要求 | 默认创建 |
| `CLAUDE.md` | Claude Code 兼容适配 | 默认创建 |
| `openspec/` | 系统行为、业务能力、需求、验收标准 | 接入 OpenSpec 后创建 |
| `docs/context/` | 项目背景、业务上下文、历史约束 | README 背景变长后创建 |
| `docs/standards/` | 项目特有工程规范 | 规范超过 README 规模后创建 |
| `docs/runbooks/` | 发布、回滚、排障、环境操作 | 流程需要复用或值班使用时创建 |
| `docs/adr/` | 长期架构决策 | 决策需要追溯时创建 |
| `.agents/rules/` | 项目本地可组合 Agent 约束 | 出现路径、文件类型或任务级细规则 |
| `.agents/skills/` | 项目本地可复用工作流、经验、检查清单 | 复杂任务反复出现 |
| `.agents/hooks/` | 特定事件触发的自动检查或动作 | 需要事件自动化 |
| `.agents/commands/` | 项目本地可复用命令模板或工具适配源 | 固定提示词或命令需要共享 |
| `.agents/templates/` | 项目本地模板 | 产物格式需要统一 |
| `.agents/scripts/` | 项目本地辅助脚本 | 手工操作可脚本化 |
| `.agents/adapters/` | 从中立来源生成的工具适配层 | 多工具需要格式转换 |
| 模块 `README.md` | 模块职责、流程、关键文件、数据、权限、路由、埋点、设计原因、常见坑 | 复杂或经常被问的模块 |
| 模块 `AGENTS.md` | 模块局部高风险 Agent 约束 | 只用于高风险模块 |

## 放置信息前先问

| 问题 | 决定什么 |
|---|---|
| 谁消费它？ | 人、Agent、工具、团队公共层 |
| 它描述什么？ | 运行方式、业务规格、长期知识、执行约束、工作流 |
| 它变化频率如何？ | 稳定背景、一次变更、临时过程、可复用经验 |
| 它适用范围多大？ | 单模块、单项目、多项目、整个团队 |

## 快速规则

- `README.md` 管人如何进入项目。
- `AGENTS.md` 管 Agent 如何安全修改这个项目。
- `CLAUDE.md` 管 Claude Code 如何加载项目级 Agent 规则。
- `openspec/` 管系统行为和需求规格。
- `docs/` 管长期辅助知识。
- `.agents/` 管项目本地 Agent 扩展材料。
- `.agents/rules/` 管项目本地细规则。
- `.agents/skills/` 管项目本地可复用能力。
- `.agents/commands/` 管固定提示词和可复用命令模板；工具是否直接识别取决于对应适配。
- 工具专用目录只做适配，不做主真源。
- 团队公共层管跨项目复用内容。
- 模块 README 管模块局部长期知识。

## 模块 README 与代码注释边界

代码注释：

- 绑定具体函数、字段或调用点。
- 服务正在修改这段代码的人。
- 生命周期和代码一致。

模块 README：

- 说明跨文件或整个模块的知识。
- 服务刚进入这个模块的人。
- 跨重构、跨版本长期有效。

不要把类型签名、字段列表或参数细节复制到模块 README。

## 信息放置表

| 信息类型 | 小项目默认位置 | 长期位置 |
|---|---|---|
| 项目是什么、如何启动、常用命令 | `README.md` | `README.md` 保持入口 |
| 项目特异 Agent 约束 | `AGENTS.md` | `AGENTS.md` 或 `.agents/rules/` |
| Claude Code 加载入口 | `CLAUDE.md` | 薄适配 |
| 当前系统行为 | `README.md` 或现有文档 | 接入 OpenSpec 后进 `openspec/specs/` |
| 一次需求、改造、重构 | issue 或临时任务文档 | 接入 OpenSpec 后进 `openspec/changes/` |
| 项目业务背景、历史上下文 | README 背景小节 | `docs/context/` |
| 项目特有工程规范 | README 约定小节 | `docs/standards/` 或 `.agents/rules/` |
| 发布、回滚、排障 | README 操作小节 | `docs/runbooks/` |
| 架构决策 | README 简短说明 | `docs/adr/` |
| 本地 Agent 固定命令 | 暂不创建 | `.agents/commands/` 或工具适配目录；不假设所有工具默认扫描 |
| 本地 Agent 工作流 / 检查清单 | 暂不创建 | `.agents/skills/` |
| 团队通用规则 / 工作流 / 全局 `AGENTS.md` / 用户长期偏好 | 不复制进项目 | 团队公共层；项目内最多写简短引用 |
| 模块长期知识 | 局部注释或 README 简述 | 模块 `README.md` |
| 模块局部 Agent 约束 | 不创建 | 仅高风险模块使用模块 `AGENTS.md` |

## 合格标准

项目知识结构至少满足：

- `README.md` 能让人运行项目并理解入口。
- `AGENTS.md` 能让 Agent 知道入口、禁区、风险和验证要求。
- 每类信息有唯一真源，没有明显双写。
- `openspec/`、`docs/`、`.agents/` 按真实需要创建。
- 项目本地内容没有复制 system / developer 指令、全局 `AGENTS.md`、用户长期偏好或团队公共规则。
- 工具专用目录不维护主规则。
- 模块知识默认与代码共置，项目级规范集中维护。
- 可复用优化能回流到团队公共层或对应基建仓库。
