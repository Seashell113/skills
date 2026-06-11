# weekly-report-summary

> 阿里企业邮箱周报处理：团队周报汇总生成 Word 文档，或个人历史周报导出 Markdown 归档。**特定环境 skill**——依赖阿里企业邮箱 IMAP 与团队 Word 模板。

## 是什么

两条能力链路：

- **团队汇总模式**：通过 IMAP 抓取团队成员的周报邮件，按固定 Word 模板（`templates/周报模版.docx`）生成汇总文档
- **个人归档模式**：从已发送邮件中提取自己的历史周报，清洗后导出单个 Markdown 归档文件

agent 会主动完成解释器探测、运行时路径确认、本地配置写入和脚本执行；用户配置只写入本机 `~/.gancao-skills/weekly-report-summary/config/config.json`，不需要改 skill 源码。

## 适用范围说明

这是为特定团队流程定制的 skill：邮箱协议按阿里企业邮箱适配，Word 模板和花名映射是团队私有约定。直接拿去用大概率需要替换模板和调整发件人/主题过滤规则，更适合作为"邮件抓取 + 模板填充"类 skill 的参考实现。

## 前置条件

- Python 3 + `python-docx`（`pip install -r scripts/requirements.txt`）
- 阿里企业邮箱账号，且已开启 IMAP 服务并生成客户端授权码
- 团队汇总模式需要 Word 模板（仓库自带默认模板）

## 安装

```bash
npx skills add https://github.com/Seashell113/skills.git -g --skill weekly-report-summary
```

## 使用示例

```text
汇总最近一周的团队周报
导出我自己的历史周报为 Markdown
```

本地调试（不连邮箱）：团队模式用 `--json`，个人模式用 `--personal-json`。

## 目录说明

| 路径 | 用途 |
| --- | --- |
| `SKILL.md` | skill 主体指令（给 agent 读） |
| `scripts/main.py` | 入口脚本（`--print-paths` 可查看运行时路径） |
| `scripts/config.py` | 路径与默认配置模型 |
| `scripts/email_fetcher.py` / `personal_report_fetcher.py` | 团队 / 个人模式的邮件抓取 |
| `scripts/md_exporter.py` | 个人周报 Markdown 导出 |
| `templates/周报模版.docx` | 团队汇总 Word 模板 |
| `tests/` | pytest 单元测试 |
| `evals/` | 评估用例与本地调试 fixtures |
