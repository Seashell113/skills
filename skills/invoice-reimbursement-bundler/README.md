# invoice-reimbursement-bundler

> 本地发票 PDF 的报销打包助手。**通用 skill**，需要本地 Python 3 和 `pdfplumber`。

## 是什么

这个 skill 帮你把散落在一个或多个目录里的发票 PDF 整理成报销单：

1. 扫描目录，按发票号识别每一张票的价税合计
2. 按发票号查重
3. 自动拼出**不低于目标金额且超出最少**的发票组合
4. 将选中的发票复制或移动到结果目录
5. 支持从已有报销目录和剩余票一起重新拼单

它只读取 PDF 里的文本，**不做 OCR**；扫描件或图片型发票会被标记为无法解析，需要你手工处理。

## 何时用

- "帮我统计一下这个目录的发票总额"
- "把这些发票凑成 3000 元报销"
- "按发票号查一下有没有重复"
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

1. 先 `scan` 预览：发票数、总额、重复、无法解析的文件
2. 再用 `bundle --target 3000` 计算组合（只输出，不改文件）
3. 你确认后，才执行 `--apply --mode copy` 或 `--mode move`

## 脚本命令

脚本位于 `{skill_dir}/scripts/invoice_bundle.py`。

### 扫描目录

```bash
python3 {skill_dir}/scripts/invoice_bundle.py scan --inputs ~/Documents/发票,~/Documents/发票2
```

### 只计算组合

```bash
python3 {skill_dir}/scripts/invoice_bundle.py bundle --target 3000 --inputs ~/Documents/发票
```

### 复制选中发票到结果目录

```bash
python3 {skill_dir}/scripts/invoice_bundle.py bundle --target 3000 --inputs ~/Documents/发票 --output-root ~/Documents/报销结果 --apply --mode copy
```

### 移动选中发票到结果目录

```bash
python3 {skill_dir}/scripts/invoice_bundle.py bundle --target 3000 --inputs ~/Documents/发票 --output-root ~/Documents/报销结果 --apply --mode move
```

## 组合规则

- 总额 **>=** 目标金额
- 优先**超出金额最小**
- 超出金额相同时，优先**张数最少**
- 发票唯一性以**发票号**为准

## 安全边界

- 默认只扫描和预览，不移动文件
- 测试和验证使用临时副本，不改动原始目录
- 不删除用户文件，不清理旧目录
- 已有报销目录里的票若仍存在，重新拼单时视为可继续使用

## 目录说明

| 路径 | 用途 |
| --- | --- |
| `SKILL.md` | skill 主体指令（给 agent 读） |
| `scripts/invoice_bundle.py` | 发票扫描、组合、复制/移动脚本 |
| `evals/evals.json` | 评估用例 |
