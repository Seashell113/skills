# Anthropic Skill Creator Upstream

本文记录本仓库中 `skills/skill-creator/` 的来源、固定版本和更新规则。个人仓库的 skill 创建和改造流程可以借用该 skill，但仓库规则仍以根目录 `README.md`、`CONTRIBUTING.md` 和 `AGENTS.md` 为准。

## 当前快照

- 上游仓库：<https://github.com/anthropics/skills>
- 上游目录：`skills/skill-creator/`
- 引入 commit：`57546260929473d4e0d1c1bb75297be2fdfa1949`
- 引入日期：`2026-07-02`
- 许可证：Apache License 2.0，原始 `LICENSE.txt` 随快照保留

`skills/skill-creator/` 应与上述 commit 中的上游目录保持一致。个人仓库规则、中文说明和本地使用约束不要直接写入该目录。

## 为什么固定快照

- 创建 skill 的方法论应稳定，避免上游 `main` 漂移导致流程和评测口径变化。
- 上游包含可执行 Python 脚本和 HTML viewer，需要在进入个人公开仓库前完成人工审查。
- 固定 commit 可以重现引入内容，并准确比较后续差异。

## 当前运行前提

- viewer 和部分脚本使用 Python 3.10+ 语法。
- `scripts/quick_validate.py` 依赖 PyYAML；执行验证的 Python 环境需要能够 `import yaml`。
- 描述优化等高级流程会调用上游 `SKILL.md` 中声明的外部 CLI，使用前按实际 agent 环境确认可用性。

这些是对当前上游快照的运行环境说明，不修改上游文件。后续同步时需要重新核对。

## 人工更新流程

1. 从 Anthropic 官方仓库读取目标 commit 的完整 SHA，不能只记录浮动的 `main`。
2. 下载或检出该 commit，比较 `skills/skill-creator/` 与当前快照的完整目录差异。
3. 检查 `SKILL.md`、脚本依赖、文件写入、网络调用、凭据读取和 viewer 行为。
4. 用目标 commit 的完整目录整体替换本仓库快照，不在替换过程中混入个人定制。
5. 更新本文的 commit 和引入日期。
6. 运行仓库要求的可发现性、安装、Python 编译和 smoke test。
7. 通过独立 PR 提交，描述上游主要变化、风险检查和验证结果。

禁止通过 CI 或本地定时任务自动跟随上游 `main` 并直接写入本仓库。可以使用工具辅助下载和比较，但最终变更必须经人工审查。
