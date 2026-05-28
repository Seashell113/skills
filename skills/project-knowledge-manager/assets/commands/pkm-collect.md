---
description: 回顾当前对话或指定文本，提取需要落盘的项目知识，生成信息归位表和写入计划，默认等待用户核对后再写入。可注册为 /pkm-collect。
---

# /pkm-collect

请使用 `project-knowledge-manager` skill，按中文输出。

任务：

1. 回顾当前对话、用户选中的文本或命令后附带的内容。
2. 提取值得沉淀的信息，并分成：
   - 已验证事实
   - 判断或设计原因
   - 待验证问题
   - 行动项
3. 为每条信息选择唯一主归属：
   - `README.md`
   - `AGENTS.md`
   - `CLAUDE.md`
   - `openspec/`
   - `docs/`
   - `.agents/`
   - 模块 `README.md`
   - 模块 `AGENTS.md`
4. 输出信息归位表和拟写入计划。
5. 明确哪些内容暂不落盘、哪些内容需要验证。
6. 默认不要直接写文件。用户确认归位表和写入计划后再落盘。

不要把未验证信息写成事实。不要双写同一事实。
不要把 system / developer 指令、全局 `AGENTS.md`、用户长期偏好或团队通用 rules 当作项目知识写入。
