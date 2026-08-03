# codex-chatgpt-dispatch

> 特定环境 Skill：面向 ChatGPT 桌面应用中的 Codex + 内置 Browser。

## 是什么

`codex-chatgpt-dispatch` 帮助 Codex 把当前任务所需上下文整理完整，通过内置
Browser 操作普通 ChatGPT 网页对话，交给用户指定的模型或
推理预设，只提交一次、在同一页面无干预等待，取得文本回复或图片产物后再回到本地
核验。复杂任务使用 `handoff.txt`；目标清楚的简单生图可以直接使用精炼提示词。
对于同一任务的续评，它会复用原网页对话，用新增证据桥要求目标模型明确维持、修订
或反转上一轮判断。

它处理调度协议和上下文质量，不管理账号，不提供模型网关，也不建设任务队列或自动
重试系统。

## 何时用

必须显式调用，例如：

```text
$codex-chatgpt-dispatch 先整理当前方案的 handoff，不要提交
$codex-chatgpt-dispatch 用页面当前可用的 Pro 深度评审并提交一次
调用 codex-chatgpt-dispatch，把这个实现交给指定模型独立判断
$codex-chatgpt-dispatch 用页面当前非 Pro 档位生成一张配图，保存后在本地检查
```

普通评审、模型讨论、材料整理或“要不要让 Pro 再看一遍”不会触发该 Skill。

## 工作流程

```text
显式触发
→ 盘点必要上下文
→ 按复杂度准备直接提示词或 handoff.txt，并选择最少附件
→ 核对账号、目标档位、材料和发送授权
→ 内置 Browser 在普通 ChatGPT 网页只提交一次
→ Browser 在同一页面无干预等待并取得文本或图片结果
→ Browser 失败时才用原生 ChatGPT thread 恢复
→ Codex 本地核验
→ 有新增证据时复用原会话续评，而不是重新复制完整上下文
```

Browser 是第一版正常全链路适配器。用户手工完成网页操作只能作为降级恢复，不能算
自动调度成功；原生 ChatGPT thread 能力只用于 Browser 控制断开、页面不可恢复或
结果读取不完整的异常场景。

## 前置条件

- ChatGPT 桌面应用中的 Codex 可以使用；
- 当前会话提供内置 Browser 和 `browser:control-in-app-browser` Skill；
- Browser 可以打开或接管普通 `chatgpt.com` 页面；
- 当前 ChatGPT 网页账号已登录，且用户有权外发选定材料；
- 提交时页面实际提供用户指定的模型或推理预设；
- Browser 能保持或恢复同一网页对话并读取最终结果。

在 Codex CLI、IDE、纯终端或缺少内置 Browser 的表面可以准备 handoff，但第一版
不会完成自动提交。Browser 不可用时 fail closed。

## 安装

```bash
npx skills add https://github.com/Seashell113/skills.git -g \
  --skill codex-chatgpt-dispatch -y
```

## 核心边界

- 显式触发与发送授权分开。
- Browser 操作前加载并遵循 `browser:control-in-app-browser`。
- 调度期间优先保持 Browser 侧栏可见；侧栏显隐不可控但同一 in-app Browser 标签页
  仍可操作时，不阻断任务。
- 使用用户指定、提交时页面实际可用的模型或推理预设。
- 目标档位不可用时停止，不自动选择近似档位。
- 发送前核对网页账号、目标档位、附件名和数量。
- 同一请求没有新授权时最多发送一次。
- 同一任务续评复用原网页对话，但每次续评仍需要新的发送授权。
- 本地路径不能作为网页端上下文；必须转换为附件、必要摘录或结构化证据。
- 页面显示 `Pro` 等产品档位时按原文记录，不猜测底层具体模型版本。
- 永远不点击“立即回答”或“停止回答”。
- 长等待不触发停止、重试、重开或降级。
- Browser 在同一网页对话中等待并读取结果。
- 原生 thread 只负责异常恢复，`send_message_to_thread` 不承担提交或追问。
- 用户手工接管不计为自动调度验收通过。
- 外部回答必须回到本地证据核验。
- 图片结果需要定位本地文件并检查格式、尺寸和实际画面；保存异常时恢复同一产物。
- 技术方案存在分歧时，优先把可验证假设转成受控 Spike；有新增证据后再续评。
- 续评记录模型维持、修订或反转结论的理由，并区分立即建设与未来触发项。
- Pro 等高成本档位不作为常规 eval。

## 数据与账号

Skill 不读取或持久化 Cookie、Browser Profile、登录凭据和认证存储。凭据、Token、
私钥、session dump、数据库备份、生产用户数据、患者隐私和明显客户敏感材料会在
提交前阻止。

公司源码、业务日志或个人数据能否进入当前 ChatGPT 账号，取决于组织政策、当前
账号设置和用户外发授权。Skill 不自动修改 Memory、训练数据控制或文件 Library
设置。

## 目录说明

| 路径 | 用途 |
| --- | --- |
| `SKILL.md` | Browser 主流程、上下文质量门、等待、结果回收与核验边界 |
| `agents/openai.yaml` | Codex 展示信息和显式触发策略 |
| `evals/evals.json` | 非外发行为与触发验证场景 |

第一版保持 instruction-first，不包含脚本、manifest、数据库或复杂状态机。
