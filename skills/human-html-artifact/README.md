# human-html-artifact

> 复杂 Markdown 材料的 HTML sidecar 视图生成器。**通用 skill**，不依赖特定环境。

## 是什么

把长篇、结构交叉的 Markdown 材料（技术方案、调研报告、PR/MR review、状态报告、设计说明、多文档摘录）转化为**自包含、可离线打开的单文件 HTML 阅读页**。

它不是通用 Markdown 转 HTML 工具，也不套固定模板：核心是先识别 Markdown 难以承载的阅读瓶颈（对照、筛选、下钻、图形化、复制复用），再用 HTML 的表达能力针对性放大，源 Markdown 保持不变。

## 何时用

- 想把方案 / 报告 / review 材料"做成好读的页面"给老板、团队或评审会看
- 原文有多阶段、多风险、多方案对比、多字段、多 diff，线性阅读成本高
- 读者角色不同（决策者看结论、评审人看风险证据、执行者看命令行动项）

**不适合**：普通 Markdown 预览、维护 README、纯文本 diff、长期维护的前端应用。

## 安装

```bash
npx skills add https://github.com/Seashell113/skills.git -g --skill human-html-artifact
```

## 使用示例

```text
把这份技术方案做成 HTML 阅读页
帮我把这次 review 结论转成能给团队看的评审页
```

## 输出特点

- 单文件 `.html`，CSS/JS 全内联，无 CDN / 远程依赖，可离线打开
- 默认 Vercel-like 开发者平台视觉风格（可由用户指定覆盖）
- 代码 / diff / 命令 / JSON 默认带复制按钮；关闭 JS 后核心内容仍可读
- 响应式 + 打印样式 + 基础可访问性

## 目录说明

| 路径 | 用途 |
| --- | --- |
| `SKILL.md` | skill 主体指令（给 agent 读） |
| `references/artifact-patterns.md` | HTML affordance 模式库，按信息形状选模块 |
| `references/DESIGN.md` | 默认视觉基线规范 |
| `references/quality-rubric.md` | 交付前质量检查表 |
| `agents/openai.yaml` | OpenAI 系工具的适配描述 |
| `evals/evals.json` | 触发与行为评估用例 |
