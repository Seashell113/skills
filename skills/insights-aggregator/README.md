# insights-aggregator

> 跨工具 AI 编程助手使用洞察分析：扫描 Claude Code 与 Codex 的本地会话记录，生成自包含 HTML 洞察报告。**通用 skill**，需要本地 Python 3。

## 是什么

类似 Claude Code 官方 `/insights`，但覆盖 **Claude Code + Codex 两个工具**并扩展了跨工具关联分析（并行使用、同项目接力、项目×工具矩阵、工具分工对比）。

架构上"本地脚本做全部确定性计算，LLM 只做两层语义分析"：

1. `collect.py` 扫描解析双工具会话（纯本地，无 LLM）
2. 并行子 agent 对窗口内会话做 facet 提取
3. `aggregate.py` 聚合统计与跨工具关联（纯本地）
4. 并行子 agent 生成 9 个洞察 section + At a Glance 摘要
5. `render.py` 沿用原模板渲染 HTML 报告；知识盘点单独输出 HTML / Markdown / JSON

## 何时用

- "分析我的 agent 使用情况" / "claude code 和 codex 用得怎么样"
- 想知道两个工具的分工模式、任务-模型匹配度、使用摩擦点
- 想要一份可留存的阶段性使用报告
- 从历史会话提取业务、项目、技术和组织经验，判断 Agent/subagent/Skill/模型/工具是否产生实际效果

## 前置条件

- Python 3（脚本仅用标准库）；读取 `.jsonl.zst` 还需要本机 `zstd` 命令
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

## 窗口统计与独立盘点

统计按 `(since, as_of]` 内活动纳入会话，长期会话不会因创建较早被漏掉；各项指标只计窗口内事件。短任务进入使用统计，facet 提取另设门槛。支持归档与 zstd 压缩的 Codex rollout。`collect.py --since ISO --as-of ISO --max-facets 0` 可只重算确定性数据，不调用模型；后续 aggregate 沿用相同冻结窗口。

知识盘点按知识点/阶段逐条保留来源、状态、复用条件和已有知识关系，使用 `render.py --knowledge-inventory PATH` 单独输出。报告保留原样式和精选洞察。详见 [盘点协议](reference/knowledge-inventory.md)。

## 复用证据与可选扩展

保留原 7/9 个使用洞察 section；用户明确要求，或本轮材料确有可复用经验/基建效果问题时，追加历史知识与基建效果两项分析。结论引用可定位来源，采纳状态单独记录；没有结果、替代成本或对照证据时写未知。

已有任务材料时用 `aggregate.py --evidence-bundle /private/path/bundle.json --home /private/path/run` 进入原聚合与渲染流程，不重复语义抽取；统计不足时仍补跑本地采集与聚合，不能把选样规模当全部使用量。直接阅读任务与完成 facet 分开计数，未知时长、提交数、满意度与模型统计不补零。协议与示例见 [evidence bundle](reference/evidence-bundle.md)。

工具分析按实际使用范围确定，零星残留记录不触发跨工具比较。聚焦单工具时复用其独立聚合统计，保留完整采集结果，并用 `selection.focus_note` 简短说明范围；报告保留原样式，主控统一修订全文以减少重复、突出具体判断和有价值的下一步。

回归：`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s skills/insights-aggregator/tests`（在仓库根目录执行）。

## 隐私说明

- 原始会话文件**只读不动**；所有缓存与报告落在本地 `~/.agent-insights/`（权限 0600）
- 报告包含项目路径和会话摘要，属于个人工作数据，分享前请自行评估

## 目录说明

| 路径 | 用途 |
| --- | --- |
| `SKILL.md` | skill 主体指令（给 agent 读） |
| `scripts/collect.py` | 扫描 + 解析双工具会话，维护 SessionMeta 缓存 |
| `scripts/codex_segments.py` | 按冻结字节边界区分 Codex owned live、导入历史与 orphan |
| `scripts/aggregate.py` | 聚合统计与跨工具关联 |
| `scripts/evidence_bundle.py` | 复用已准备证据并保留未知指标与选样口径 |
| `scripts/render.py` | 渲染自包含 HTML 报告 |
| `tests/test_codex_segments.py` | Codex fork、subagent、无效行与快照回归夹具 |
| `tests/test_codex_user_messages.py` | 新旧 UserMessage、去重、轮次和缓存升级的合成回归 |
| `prompts/facet-extraction.md` | facet 提取子 agent 提示词 |
| `prompts/insight-sections.md` | 洞察 section 提示词 |
| `reference/claude-insights-spec.md` | 官方 `/insights` 逻辑规范（背景知识） |
| `reference/codex-session-schema.md` | Codex 会话格式与字段映射（含新工具适配方法） |

Codex 的一个物理 rollout 可能包含继承的父会话历史。采集器会以文件名和首条 `session_meta` 校验物理会话，只将 owned live 事件计入指标；需要固定重跑口径时，可传入带 byte cutoff 与 SHA-256 的 `--codex-snapshot-manifest`。

用户输入同时支持旧 `event_msg/user_message` 与新 `item_completed/UserMessage`，保留消息数和 native turn 模型配置数的区别。格式修复将 SessionMeta schema 升至 15；首次后续正常采集会在原窗口及数量上限内重新排队旧 Codex facet，不触发采集器自行调用模型，不使 Claude facet 因此失效。字段和本地回归命令见 [Codex 格式说明](reference/codex-session-schema.md)。

旧 Codex facet 未完成刷新时，聚合报告保留有效会话统计，但不会消费过期摘要或用旧 warmup 分类排除会话；旧缓存文件保持原样。

Codex fork 若未保留 foreign `session_meta`，采集器使用同次扫描或 manifest 中的父源，校验冻结 SHA-256 后逐行比较有 native turn/item/call ID 锚点的连续前缀；仅忽略 fork 重写的时间与 event thread 字段。匹配历史排除后保留累计 token 基线。父源缺失或无法证明前缀时保留原事件，并在 `source_audit.fork_history` 与 collect 的 `codex_ownership.fork_lineage_unverified` 明示未核实；这不证明存在复制历史，也不应自动清零正常 fork/subagent。发现可疑根会话时，须说明统计影响或将其单列未知，不能把 owner_leakage_lines=0 当完整归属已证实。manifest 之外的父源不会被自动读取。
