# insights-aggregator

> 跨工具 AI 编程助手使用洞察分析：扫描 Claude Code 与 Codex 的本地会话记录，生成自包含 HTML 洞察报告。**通用 skill**，需要本地 Python 3。

## 是什么

类似 Claude Code 官方 `/insights`，但覆盖 **Claude Code + Codex 两个工具**并扩展了跨工具关联分析（并行使用、同项目接力、项目×工具矩阵、工具分工对比）。

架构上"本地脚本做全部确定性计算，LLM 只做两层语义分析"：

1. `collect.py` 扫描解析双工具会话（纯本地，无 LLM）
2. 并行子 agent 对窗口内会话做 facet 提取
3. `aggregate.py` 聚合统计与跨工具关联（纯本地）
4. 并行子 agent 生成 9 个洞察 section + At a Glance 摘要
5. `render.py` 渲染单文件 HTML 报告

## 何时用

- "分析我的 agent 使用情况" / "claude code 和 codex 用得怎么样"
- 想知道两个工具的分工模式、任务-模型匹配度、使用摩擦点
- 想要一份可留存的阶段性使用报告

## 前置条件

- Python 3（脚本仅用标准库）
- 本地存在 Claude Code（`~/.claude/projects/`）或 Codex（`~/.codex/sessions/`）会话记录，单工具也可运行
- 注意：Claude Code 默认约 30 天清理历史会话，想积累数据可调大 `settings.json` 中的 `cleanupPeriodDays`

## 安装

```bash
npx skills add https://github.com/Seashell113/skills.git -g --skill insights-aggregator
```

## 使用示例

```text
/insights
生成最近一个月的跨工具使用洞察报告
```

默认分析最近 30 天、facet 提取上限 50 条会话；调大窗口意味着更多并行 LLM 调用和耗时。

## 隐私说明

- 原始会话文件**只读不动**；所有缓存与报告落在本地 `~/.agent-insights/`（权限 0600）
- 报告包含项目路径和会话摘要，属于个人工作数据，分享前请自行评估

## 目录说明

| 路径 | 用途 |
| --- | --- |
| `SKILL.md` | skill 主体指令（给 agent 读） |
| `scripts/collect.py` | 扫描 + 解析双工具会话，维护 SessionMeta 缓存 |
| `scripts/aggregate.py` | 聚合统计与跨工具关联 |
| `scripts/render.py` | 渲染自包含 HTML 报告 |
| `prompts/facet-extraction.md` | facet 提取子 agent 提示词 |
| `prompts/insight-sections.md` | 洞察 section 提示词 |
| `reference/claude-insights-spec.md` | 官方 `/insights` 逻辑规范（背景知识） |
| `reference/codex-session-schema.md` | Codex 会话格式与字段映射（含新工具适配方法） |
