# 贡献指南

感谢你对本仓库的兴趣。无论是修复文档、改进现有 skill，还是贡献新 skill，都欢迎提 Issue 和 PR。

## 目录规范

每个 skill 独占 `skills/<skill-name>/` 目录。自研 skill 结构约定：

| 路径 | 必需 | 用途 |
| --- | --- | --- |
| `SKILL.md` | ✅ | **主真源**：给 agent 读的指令，定义触发、流程、边界和输出约定 |
| `README.md` | ✅ | 给人读的介绍：定位、何时用、安装、前置条件、目录说明 |
| `references/` | 可选 | 按需加载的细则材料，避免把 `SKILL.md` 写成长篇教程 |
| `scripts/` | 可选 | 可执行脚本；确定性计算优先交给脚本而不是 LLM |
| `prompts/` | 可选 | 子 agent 提示词模板 |
| `assets/` | 可选 | 命令模板、文档模板等静态材料 |
| `evals/` | 可选 | 触发与行为评估用例 |

第三方固定快照可以保留上游原始目录结构，不强行补齐本仓库自研 skill 的 `README.md` 或模板文件；来源、许可证、固定版本和更新规则应放在 `docs/contributing/`。

## SKILL.md 编写要求

frontmatter 必须包含：

```yaml
---
name: <与目录名完全一致的 kebab-case 名称>
description: <触发条件描述：什么任务、什么关键词、什么场景下应该使用这个 skill>
---
```

`description` 是 Agent 决定是否加载 skill 的唯一依据，要写清楚正反两面：什么时候**应该**触发（包括用户不点名 skill 时的自然语言场景），什么时候**不应该**触发。

正文编写建议（可参考仓库内现有 skill）：

- 写"先判断、再行动"的流程，不要写平铺的大 checklist
- 明确行为边界：不支持什么、失败时怎么处理、什么情况下先向用户确认
- 细则放 `references/` 按需加载，`SKILL.md` 保持主干清晰
- skill 只沉淀该能力本身可复用的触发、流程和边界，不要复制全局 Agent 规则或个人长期偏好

## 新增 skill 流程

新增或明显改造 skill 前，先安装并触发本仓库内的 `skill-creator`，用它完成意图澄清、真实测试 prompt、评测或人工审阅口径。轻量文案修补可按影响面缩小验证，但仍需保证触发描述和目录清单一致。

1. 复制 [`templates/skill-template/`](templates/skill-template/) 到 `skills/<skill-name>/`
2. 填写 `SKILL.md` 和 `README.md`，按需添加 `references/`、`scripts/` 等
3. 在根 `README.md` 的 Skill 清单表格中追加一行（含适用范围标注），并更新徽章中的 skill 数量
4. 提交 PR，说明 skill 的定位和测试方式

重命名或删除 skill 时，同步更新根 `README.md` 清单。

## 验证要求

- **文档改动**：检查文档内链接、路径与当前目录一致；根 `README.md` 清单与 `skills/` 目录实际一致
- **可发现性变更**：运行 `npx skills add . --list`
- **单个 skill 变更**：至少安装到一个目标 agent 验证，例如 `npx skills add . -g -a codex --skill <skill-name> -y`；如不适合安装，说明原因
- **脚本改动**：运行该 skill 自带的测试或验证命令（如 `weekly-report-summary` 的 `pytest tests/`），或最小可复现实例
- **触发描述改动**：如有 `evals/`，对照评估用例确认正反触发场景仍然成立

带 `scripts/` 的 skill 按代码变更处理，评审时需要关注副作用、凭据读取、文件写入、网络访问和跨平台行为。

## 提交约定

- commit message 遵循 [Conventional Commits](https://www.conventionalcommits.org/)（`feat:` / `fix:` / `docs:` 等），中文描述即可
- 一个 PR 聚焦一件事；skill 行为变更和文档整理分开提交

## License

提交贡献即表示你同意以 [MIT](LICENSE) 协议发布你的贡献内容。
