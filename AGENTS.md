# AGENTS.md

## 项目说明

- 本仓库是个人 skill 集合仓库。
- 根目录 `README.md` 是人类入口，维护当前 skill 清单和项目入口信息。
- 每个 skill 以 `skills/<skill-name>/SKILL.md` 为主要真源；如存在脚本、模板或参考材料，应放在对应 skill 目录内。
- 第三方固定快照以保留上游目录为优先，来源、版本和更新规则放在 `docs/contributing/`，不要把个人仓库规则写入快照目录。

## 修改边界

- 修改 skill 行为前，先阅读目标 skill 的 `SKILL.md`，再检查其相邻的 `references/`、`scripts/`、`assets/` 或模板文件。
- 每个 skill 目录内的 `README.md` 面向人类使用者；修改 skill 行为后检查它是否需要同步更新。
- 不要把全局 Agent 规则、当前会话指令或用户长期偏好整段复制进单个 skill；skill 只沉淀该能力本身可复用的触发、流程和边界。
- 新增或明显改造 skill 前，先安装并触发仓库内的 `skill-creator`，用它完成意图澄清、真实测试 prompt、评测或人工审阅口径；轻量文案修补可按影响面缩小验证。
- 新增自研 skill 时从 `templates/skill-template/` 起步；新增或重命名 skill 时，同步更新根 `README.md` 的 skill 清单。
- `skills/skill-creator/` 是第三方固定上游快照，不写入个人仓库定制规则；版本和更新流程维护在 `docs/contributing/skill-creator-upstream.md`。
- 默认保持 skill 最小结构；只有真实需要时才增加 `scripts/`、`references/`、`templates/`、`assets/`、`evals/`、`tests/`。
- 带 `scripts/` 的 skill 按代码变更处理，需要关注副作用、凭据读取、文件写入和跨平台行为。
- 不提交账号密码、授权码、Token、私钥、客户敏感信息、本机缓存或一次性生成产物。
- `.claude/`、`.omc/`、`.obsidian/` 是本地工具状态或适配目录，不作为项目知识主真源。
- 保留用户已有未跟踪或未提交改动；只修改当前任务明确覆盖的文件。

## Agent 扩展索引

- `.agents/README.md`：如存在，先阅读；用于索引项目本地 rules、skills、hooks、commands、templates、scripts 和 adapters。
- `.agents/` 只在确有项目本地 Agent 扩展材料时创建，不为空目录占位。

## 验证要求

- 只改 Markdown 文档时，至少检查文档链接、路径和 skill 清单是否与当前目录一致。
- skill 可发现性变更后运行 `npx skills add . --list`。
- 修改单个 skill 后，至少安装到一个目标 agent 验证：`npx skills add . -g -a <agent> --skill <skill-name> -y`；如不适合安装，说明原因。
- 修改 skill 脚本时，优先运行该 skill 自带的验证命令或最小可复现实例。
- 修改打包、安装或分发相关内容时，补充验证所依赖的命令、路径和产物位置。
