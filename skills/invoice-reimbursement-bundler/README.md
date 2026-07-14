# invoice-reimbursement-bundler

> 本地发票 PDF 的报销打包助手。**通用 skill**，需要本地 Python 3 和 `pdfplumber`。

## 是什么

这个 skill 帮你把散落在一个或多个目录里的发票 PDF 整理成报销单：

1. 扫描目录，识别每张票的发票号、价税合计和购买方抬头
2. 按发票号查重
3. 按指定抬头检查，未指定时自动分类
4. 自动拼出**不低于目标金额且超出最少**的发票组合
5. 用户确认后，默认将选中的发票移动到结果目录
6. 支持从已有报销目录和剩余票一起重新拼单

它只读取 PDF 里的文本，**不做 OCR**；扫描件或图片型发票会被标记为无法解析，需要你手工处理。

## 何时用

- "帮我统计一下这个目录的发票总额"
- "把这些发票凑成 3000 元报销"
- "按发票号查一下有没有重复"
- "检查这些发票的抬头是否一致"
- "把选中的发票移动到一个新文件夹"
- "从之前的报销目录和剩下的票重新拼一单"
- "/invoice-bundle"

**不适合**：需要 OCR 识别扫描件、自动删除/清理旧目录、税务查验/真伪校验。

## 前置条件

- Python 3
- `pdfplumber`：用于提取 PDF 文本

```bash
pip install pdfplumber
```

## 安装

```bash
npx skills add https://github.com/Seashell113/skills.git -g --skill invoice-reimbursement-bundler
```

## 使用示例

```text
/invoice-bundle
帮我拼一个 3000 元的发票报销单，目录是 ~/Documents/发票
```

Agent 会按以下顺序执行：

1. 先 `scan` 预览：发票数、总额、重复、抬头分类、无法解析的文件
2. 再用 `bundle --target 3000` 计算组合（只输出，不改文件）
3. 你确认后执行 `--apply`，默认移动选中发票；明确要求保留源文件时使用 `--mode copy`

## 脚本命令

脚本位于 `{skill_dir}/scripts/invoice_bundle.py`。

### 扫描目录

```bash
python3 {skill_dir}/scripts/invoice_bundle.py scan --inputs ~/Documents/发票,~/Documents/发票2
```

指定购买方抬头：

```bash
python3 {skill_dir}/scripts/invoice_bundle.py scan --inputs ~/Documents/发票 --title 杭州甘之草科技股份有限公司
```

未指定抬头时，扫描结果会自动按购买方抬头分类。检测到多个抬头或未知抬头时，需要先确认使用规则。

### 只计算组合

```bash
python3 {skill_dir}/scripts/invoice_bundle.py bundle --target 3000 --inputs ~/Documents/发票 --title 杭州甘之草科技股份有限公司
```

### 确认后移动选中发票到结果目录

```bash
python3 {skill_dir}/scripts/invoice_bundle.py bundle --target 3000 --inputs ~/Documents/发票 --output-root ~/Documents/已报 --apply --title 杭州甘之草科技股份有限公司
```

结果目录按预期金额和选中张数命名，例如 `2026-07-14_3000元_12张`；实际选中总额只在结果 JSON 和交付说明中展示。

### 保留源文件时改为复制

```bash
python3 {skill_dir}/scripts/invoice_bundle.py bundle --target 3000 --inputs ~/Documents/发票 --output-root ~/Documents/报销结果 --apply --mode copy --title 杭州甘之草科技股份有限公司
```

## 组合规则

- 总额 **>=** 目标金额
- 优先**超出金额最小**
- 超出金额相同时，优先**张数最少**
- 发票唯一性以**发票号**为准
- 指定抬头时，仅匹配的发票参与组合
- 未指定抬头时自动分类，不静默混用多个抬头或未知抬头

## 安全边界

- 默认先扫描和预览，用户确认后移动选中发票
- 测试和验证使用临时副本，不改动原始目录
- 不删除用户文件，不清理旧目录
- 已有报销目录里的票若仍存在，重新拼单时视为可继续使用

## 目录说明

| 路径 | 用途 |
| --- | --- |
| `SKILL.md` | skill 主体指令（给 agent 读） |
| `scripts/invoice_bundle.py` | 发票扫描、组合、复制/移动脚本 |
| `evals/evals.json` | 评估用例 |
