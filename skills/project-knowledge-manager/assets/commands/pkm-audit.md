---
description: 审计当前项目已沉淀信息的标准性、准确度、唯一真源、双写和过期风险。可注册为 /pkm-audit。
---

# /pkm-audit

请使用 `project-knowledge-manager` skill，按中文输出。

任务：

1. 检查当前项目知识结构：
   - `README.md`
   - `AGENTS.md`
   - `CLAUDE.md`
   - `openspec/`
   - `docs/`
   - `.agents/`
   - 模块 README / AGENTS
2. 如可执行脚本，先运行本 skill 自带的结构检查脚本。不要假设当前项目根目录存在该脚本；应从 skill 安装目录解析路径：

   ```bash
   python3 <skill-dir>/scripts/project_knowledge_audit.py .
   ```

3. 如果无法定位或执行脚本，跳过脚本并继续语义审计。在脚本结果或人工检查基础上补充：
   - 信息是否放错位置
   - 是否存在双写
   - 是否存在过期或未验证说法
   - 是否把 system / developer 指令、全局 `AGENTS.md`、用户长期偏好或团队公共规则复制进项目
   - 是否把工具适配层当主真源
4. 按 `P0` / `P1` / `P2` / `P3` 输出问题、证据和修复建议。
5. 只输出审计报告，不直接修改文件。
