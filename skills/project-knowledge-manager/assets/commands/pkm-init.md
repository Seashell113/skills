---
description: 初始化或规范化项目知识目录，输出 README/AGENTS/CLAUDE/docs/openspec/.agents/module README 的创建与更新计划，默认不直接写文件。可注册为 /pkm-init。
---

# /pkm-init

请使用 `project-knowledge-manager` skill，按中文输出。

任务：

1. 检查当前项目的 `README.md`、`AGENTS.md`、`CLAUDE.md`、`openspec/`、`docs/`、`.agents/` 和重要模块 README。
2. 根据项目真实信息密度，判断应创建或更新哪些文件。
3. 输出“项目知识初始化计划”，包含：
   - 当前状态
   - 拟变更
   - 暂不创建的目录及理由
   - 草稿内容摘要
   - 需要用户确认的问题
4. 默认不要直接创建或修改文件。用户明确确认后再落盘。
5. 不要把 system / developer 指令、全局 `AGENTS.md`、用户长期偏好或团队通用 rules 写入目标项目文档。

如果用户在命令后附带路径、范围或 `--apply`，仍需先确认目标项目和写入计划是否清晰。
