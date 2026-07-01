# codex-thread-organizer

> Codex 会话标题、收口摘要和回溯索引维护。**适用范围标注**：个人工作流。

## 是什么

`codex-thread-organizer` 用于维护 Codex 会话的可回溯性：给相关线程统一命名、在会话结束时生成短摘要和 handoff、整理历史会话、提出索引和归档建议。

它解决的是个人会话导航问题，不处理代码实现、项目文档治理或仓库知识沉淀。

## 何时用

- 新会话开始时先处理会话名，再继续主任务。
- 按命名规则收口当前会话。
- 整理最近一组 Codex 会话标题。
- 给拆分到多个会话的长期事项生成索引。
- 标注测试、安装核对、历史会话和归档候选。

常见触发词包括：`codex-thread-organizer`、`codex-threads`、`codex-thread-namer`、`先重命名本会话`、`按命名规则收口`、`整理会话标题`。

推荐使用短命令入口：

| 命令 | 用途 |
| --- | --- |
| `codex-thread-organizer:init` | 初始化当前会话为常驻线程命名管理器 |
| `codex-thread-organizer:rename` | 只处理当前或指定线程重命名 |
| `codex-thread-organizer:handoff` | 只生成下一会话 handoff |
| `codex-thread-organizer:closeout` | 组合执行命名、五行摘要、必要 handoff 和归档建议 |

别名 `codex-thread-namer:*` 等价可用。

**不适合**：项目 README/AGENTS/docs 归位、代码修改、业务文档治理；这些应使用对应项目或知识管理 skill。

## 前置条件

- Codex 当前环境提供线程管理工具时，可以直接列出、读取、重命名、归档或创建线程。
- 如果线程工具暂不可用，skill 会降级为标题建议、收口摘要和 handoff；连续主线编号需要等工具恢复后再补齐。
- 自动重命名依赖宿主提供 thread tools。CLI 或其他宿主没有重命名工具时，skill 只能给出建议标题和收口信息。
- 不默认直接写入本地 Codex 数据库；本地元数据只用于诊断或用户明确批准的人工恢复。

## 安装

```bash
npx skills add https://github.com/Seashell113/skills.git -g --skill codex-thread-organizer
```

## 使用示例

```text
codex-thread-organizer:init
```

```text
codex-thread-organizer:rename
根据当前任务内容重命名本会话。
```

```text
codex-thread-organizer:handoff
只生成下一会话交接提示，不改名。
```

```text
codex-thread-organizer:closeout
按命名规则收口当前会话；如有待完成或待确认事项，给出 handoff。
```

```text
整理团队skills最近的PKM/Subagent会话标题，先预览再改。
```

## 目录说明

| 路径 | 用途 |
| --- | --- |
| `SKILL.md` | skill 主体指令（给 agent 读） |
| `agents/openai.yaml` | Codex UI 元数据 |
