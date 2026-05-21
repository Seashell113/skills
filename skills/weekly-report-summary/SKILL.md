---
name: weekly-report-summary
description: 自动处理阿里企业邮箱中的周报邮件，既支持团队周报汇总并按固定 Word 模板生成文档，也支持提取个人历史周报邮件并导出 Markdown 归档。当用户提到“汇总周报”“周报邮件”“阿里企业邮箱”“授权码”“按模板生成周报 Word”“最近一周/上周周报汇总”“模板里找不到某个花名”“先检查周报汇总环境或配置路径”“个人周报”“我的周报”“历史周报”“导出周报”“从邮件提取周报”“个人周报归档”时，都应使用此 skill。Agent 应主动完成解释器探测、运行时路径确认、本地 override 配置写入和脚本执行，而不是只给文档链接或让用户去改代码。
---

# Weekly Report Summary

用这个 skill 帮用户完成两条能力链路：

- 团队汇总模式：从阿里企业邮箱抓取团队周报，按 Word 模板生成汇总文档
- 个人归档模式：提取自己发送的历史周报邮件，清洗后导出单个 Markdown 归档文件

## 先判定模式

- 明确要“团队周报汇总”“按模板出 Word”“修模板花名映射”：走团队汇总模式
- 明确要“个人周报”“历史周报”“导出 Markdown”“从邮件提取我自己的周报”：走个人归档模式
- 如果用户只说“周报”，先澄清是“团队汇总”还是“个人归档”

## 执行规则

- 不要只给文档链接。先检查环境、定位配置，再执行。
- 不要让用户编辑 skill 安装目录里的代码文件。
- 用户本地配置只写入 `config.CONFIG_PATH`。
- 团队共享默认值由 skill 源码维护；本地 `config.json` 只存邮箱凭据和用户/机器级 override。
- 输出文件默认写到 `<skill-home>/runs/`，除非用户显式传 `--output`。
- 个人模式默认导出单个 Markdown 文件，不做按周拆分。
- 个人模式如果只导出某个区块，使用标准区块键：`this_week_work`、`next_week_plan`、`gains_losses`、`praise`。

## 运行时模型

先读取 `scripts/config.py`，确认运行时目录。

默认路径：

- macOS/Linux: `~/.gancao-skills/weekly-report-summary/`
- Windows: `%USERPROFILE%\.gancao-skills\weekly-report-summary\`
- 如果设置了 `GANCAO_SKILLS_HOME`，则以该目录为根目录

关键路径：

- 配置文件：`<skill-home>/config/config.json`
- 输出目录：`<skill-home>/runs/`
- 调试路径打印：`<python-command> scripts/main.py --print-paths`

本地 `config.json` 中常见内容：

- 邮箱地址和客户端授权码
- 网络较慢机器可单独覆盖 `imap_timeout_seconds`
- 个别机器的 `template_path` 或 `output_dir`
- 某个用户专属的 `name_alias_map` / `group_members` override
- 个人模式的 `personal_mailbox` / `personal_subject_pattern` / `personal_sender_*` override

不要把团队共享默认映射整份复制进本地配置，也不要再要求用户编辑 `scripts/config.py`。

## 工作流

### 1. 检查解释器和依赖

先按 `python3 --version`、`py -3 --version`、`python --version` 的顺序探测可用解释器。

如果 `python-docx` 缺失，用探测成功的解释器安装：

```bash
<python-command> -m pip install -r scripts/requirements.txt
```

### 2. 先打印路径，再决定怎么跑

优先运行：

```bash
<python-command> scripts/main.py --print-paths
```

这样用户能先看到当前配置文件、输出目录和模板路径，以及个人模式默认邮箱和主题规则。

### 3. 团队汇总模式

- 用户要真实汇总团队周报邮件：走邮箱模式
- 用户只想验证模板填充、调试导出、做回归测试：优先走 `--json` 模式

邮箱模式：

```bash
<python-command> scripts/main.py --days 5
```

本地 JSON 模式：

```bash
<python-command> scripts/main.py --json <path-to-json> --output <path-to-docx>
```

### 4. 个人归档模式

默认从已发送邮箱 alias 自动解析实际文件夹，再按主题正则和发件人过滤：

```bash
<python-command> scripts/main.py --personal
```

常见变体：

```bash
<python-command> scripts/main.py --personal --from 2026-01-01 --to 2026-04-01
<python-command> scripts/main.py --personal --section-only --section-key this_week_work
<python-command> scripts/main.py --personal --subject-pattern "^\\d+月第\\d+周周报"
<python-command> scripts/main.py --personal --personal-mailbox inbox
<python-command> scripts/main.py --personal-json evals/fixtures/personal_reports.json
```

### 5. 需要配置时怎么处理

- 如果 `EMAIL_ADDRESS` 或 `EMAIL_PASSWORD` 还是默认值，向用户索取阿里企业邮箱地址和客户端授权码
- 把这些值写入 `config.CONFIG_PATH`
- 如果报“模板中未找到: xxx”，只把用户需要的映射写入本地 `name_alias_map`
- 如果个人模式需要更严格的主题筛选，只把 `personal_subject_pattern` 等 override 写入本地配置
- 除非用户明确是在维护 skill 源码，否则不要修改共享默认映射

### 6. 交付结果

- 成功后明确返回输出文件路径
- 如果使用了 `--output`，返回用户指定的路径
- 如果使用默认路径，说明文件在 `<skill-home>/runs/`
- 个人模式如果检测到已发送历史可能受 IMAP 限制，要主动提示用户检查邮箱客户端同步范围，并说明可显式改用 `--personal-mailbox inbox`

## 项目结构

```text
weekly-report-summary/
├── evals/
│   ├── evals.json
│   └── fixtures/
├── scripts/
│   ├── config.py
│   ├── email_fetcher.py
│   ├── personal_report_fetcher.py
│   ├── md_exporter.py
│   ├── main.py
│   └── requirements.txt
├── templates/
│   └── 周报模版.docx
└── SKILL.md

~/.gancao-skills/weekly-report-summary/
├── config/
│   └── config.json
├── state/
├── cache/
└── runs/
```

## 故障排查

- **IMAP 连接失败**：
  - 通常是授权码错误，或者 IMAP 服务未开启。
  - 建议用户检查阿里邮箱设置中的“客户端密码”和“IMAP/SMTP服务”开关。
  - 如果网络较慢或服务器收尾响应慢，可在本地 `config.json` 或环境变量中提高 `IMAP_TIMEOUT_SECONDS`。
- **个人模式已发送只看到最近一段历史**：
  - 这通常不是 skill 本身的问题，而是邮箱客户端同步范围限制。
  - 建议用户登录网页版邮箱检查 IMAP 或客户端同步历史范围。
  - 短期绕过时可显式改用 `--personal-mailbox inbox`。
- **模板文件不存在**：
  - 先用 `--print-paths` 看当前 `template_path`。
  - 如果模板被移动了，引导用户把本地 `template_path` override 写入 `config.CONFIG_PATH`。
- **只想做本地回归，不想连邮箱**：
  - 团队模式优先用 `--json`
  - 个人模式优先用 `--personal-json`
