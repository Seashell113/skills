# fe-code-review

> 团队统一的前端代码审查入口，V1 聚焦版本级审查：整体影响、回归风险与合并建议。**团队定制 skill**——审查口径和输出结构是为特定前端团队设计的。

## 是什么

接住所有"前端 review"请求的统一入口。V1 正式支持 `version-review`（审分支、PR、版本实现、相对 `master` 的改动），按三条主线审查：

- 功能正确性与逻辑漏洞
- 影响面与回归风险
- 稳定性、可扩展性与复用性

输出固定结构的中文审查结论：决策摘要（非代码作者可读）+ 详细 Findings（P0–P3 分级、置信度、阻塞性）+ 四档合并建议 + 建议回归路径。

`focused-review` / `staged-review` / `re-review` 属于规划中的扩展模式，V1 会识别并提示，不假装支持。

## 适用范围说明

审查主线、严重级别口径和报告结构是按特定前端团队的协作习惯定制的。其他团队可以直接借用框架，但建议根据自身流程调整 `references/severity-and-merge.md` 中的分级与合并建议规则。

## 安装

```bash
npx skills add https://github.com/Seashell113/skills.git -g --skill fe-code-review
```

## 使用示例

```text
帮我做一次前端版本级 review，分支 feat/xxx，基线 origin/master
review 一下这个 PR 的整体影响和回归风险
```

## 目录说明

| 路径 | 用途 |
| --- | --- |
| `SKILL.md` | skill 主体指令（给 agent 读） |
| `references/mode-routing.md` | 审查模式路由口径 |
| `references/severity-and-merge.md` | P0–P3 分级与四档合并建议规则 |
| `references/subagent-playbook.md` | 大改动时的并行子 agent 规则 |
| `evals/evals.json` | 评估用例 |
