# codex-thread-organizer

> Codex 会话标题、收口摘要和回溯索引维护。**适用范围标注**：个人工作流。

## 是什么

`codex-thread-organizer` 用于维护 Codex 会话的可回溯性：给相关线程统一命名、在会话结束时生成短摘要和 handoff、整理历史会话、提出索引和归档建议。

它解决的是个人会话导航问题，不处理代码实现、项目文档治理或仓库知识沉淀。

## 何时用

- 按命名规则收口当前会话。
- 整理最近一组 Codex 会话标题。
- 给拆分到多个会话的长期事项生成索引。
- 标注测试、安装核对、历史会话和归档候选。

**不适合**：项目 README/AGENTS/docs 归位、代码修改、业务文档治理；这些应使用对应项目或知识管理 skill。

## 前置条件

- Codex 当前环境需要提供线程管理工具，例如列出、读取、重命名、归档或创建线程的工具。

## 安装

```bash
npx skills add https://github.com/Seashell113/skills.git -g --skill codex-thread-organizer
```

## 使用示例

```text
按命名规则收口这个会话
```

```text
整理团队skills最近的PKM/Subagent会话标题，先预览再改
```

```text
给这组PKM历史会话生成一个索引
```

## 目录说明

| 路径 | 用途 |
| --- | --- |
| `SKILL.md` | skill 主体指令（给 agent 读） |
| `agents/openai.yaml` | Codex UI 元数据 |
