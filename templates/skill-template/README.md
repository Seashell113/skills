# skill-name

> 一句话定位。**适用范围标注**：通用 / 团队定制 / 特定环境（说明依赖什么）。

## 是什么

两三句话向人类读者介绍这个 skill 做什么、解决什么问题、和相近工具的区别。

## 何时用

- 典型场景 1
- 典型场景 2

**不适合**：哪些场景不该用它。

## 前置条件

- 运行时依赖（如 Python 3、某个服务的凭据）；没有则删掉本节

## 安装

```bash
npx skills add https://github.com/Seashell113/skills.git -g --skill skill-name
```

## 使用示例

```text
一句能触发这个 skill 的自然语言指令
```

## 目录说明

| 路径 | 用途 |
| --- | --- |
| `SKILL.md` | skill 主体指令（给 agent 读） |
| `references/...` | 按需加载的细则材料 |
