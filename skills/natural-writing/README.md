# natural-writing

中文技术材料写作与编辑，默认面向技术读者。通用、无脚本或外部服务依赖，当前为 0.1.0 试用版。

根据原话、笔记或事实材料生成说明文档、技术方案正文和页面文案，减少空话与生硬措辞。也可编辑已有文稿；原文已经清楚时保留，不要求缩短到固定字数。

本 Skill 负责表达和组织。技术选型、代码实现、页面视觉设计由相应任务流程处理。

## 使用

```text
$natural-writing 根据这些材料写一份给技术团队看的说明。
```

```text
$natural-writing 把这份初稿改得自然一点。
```

明确面向非技术读者时，在任务中说明。按需求输出 Markdown 或页面正文，不强制套用固定结构，也不附加长篇改写说明。

## 安装与分发

个人仓是开发与更新来源，团队仓同步相同版本用于分发。个人用户从个人仓安装；团队成员可从团队仓安装。两者同名，重装会覆盖同名安装，请固定自己的更新来源。

个人仓（Codex）：

```bash
npx skills add https://github.com/Seashell113/skills.git -g -a codex --skill natural-writing -y
```

团队仓（需要仓库读取权限）：

```bash
npx skills add git@git.igancao.com:frontend-web/ai-coding/skills.git -g -a codex --skill natural-writing -y
```

以上命令用于合入主线后的版本。评审期间可从对应 PR/MR 分支检出仓库，再执行：

```bash
npx skills add . -g -a codex --skill natural-writing -y
```

更新时重新执行自己来源的安装命令。其他 Agent 按需调整 `-a`。也可复制本目录安装；`.skill` 包是 ZIP 格式，需要目录的工具可先解压。

## 验证情况

以相同模型、相同输入做了有／无 Skill 对照：两份从原始材料生成的文档均获得评阅者偏好；两份已有文稿的改写未显示明确额外收益。每组只运行一次，不代表跨模型、团队或无记忆环境的稳定结果。

本版沿用被测试的正文，仅补齐生成场景的触发描述和版本信息。自动触发准确性仍需实际使用观察，必要时直接点名 Skill。

使用中重点反馈哪句更好或更差、是否增加了无用展开，以及是否改变了条件、范围或结论状态。依据真实问题调整，不把偏好积累成禁用词表。

## 文件

- `SKILL.md`：Agent 指令。
- `README.md`：使用与安装说明。
- `LICENSE`：MIT 许可证。
