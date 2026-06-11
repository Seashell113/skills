# tech-plan-pairing

> 技术方案结对制定——和你一起把模糊的技术方向想清楚，逐步收敛成可落地的方案。**通用 skill**，不依赖特定环境。

## 是什么

一套五阶段协作流程：问题澄清 → 事实验证 → 方案探索 → 外部审查 → 文档落地。它的角色不是"方案生成器"——不是接到需求就输出一份完整文档，而是通过多轮讨论先回到问题定义，再对比至少两条备选路径，最后分层产出文档。

针对 LLM 在技术讨论中的典型偏差做了显式约束：关键事实必须现查不凭记忆、最佳实践要做适用性判断、允许推翻自己、记录"为什么不做 X"。

## 何时用

- 从零制定技术方案：工具链选型、架构设计、技术迁移、流程规范、技术债治理
- 拿到一版初稿（其他 agent / 同事写的），想先回到问题定义重新校准方向
- "先别直接给结论，先一起把问题和约束想清楚"
- "我们团队的 X 比较混乱，想统一一下"这类需要多轮探讨的技术决策

**不适合**：纯 code review、成熟方案的执行跟踪、单一明确问题的快速解答。

## 安装

```bash
npx skills add https://github.com/Seashell113/skills.git -g --skill tech-plan-pairing
```

## 使用示例

```text
tech-plan-pairing 我们想统一团队的包管理器，先一起想清楚
有人建议我们迁移到 monorepo，你觉得呢
```

## 目录说明

| 路径 | 用途 |
| --- | --- |
| `SKILL.md` | skill 主体指令（给 agent 读） |
| `references/patterns.md` | 方案探索阶段的行为模式与反模式 |
| `references/output-templates.md` | 文档分层原则与结构参考 |
| `references/context-update-protocol.md` | 长期上下文目录的同步协议 |
| `evals/evals.json`、`evals/trigger-evals.json` | 行为与触发评估用例 |
