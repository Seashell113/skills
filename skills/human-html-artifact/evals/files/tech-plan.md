# Node / pnpm 工具链统一收口方案评审稿

> 文档状态：评审前草案  
> 目标读者：前端架构、CI 维护人、各业务线技术负责人  
> 评审目标：判断方案是否足以支撑 90+ 仓库的分批落地，而不是只看命令是否可执行

## 1. 一句话结论

本方案建议将开发者本地 Node 管理工具从 `nvm` 收口到 `fnm`，同时把团队 Node / pnpm 版本分层钉死，并在活跃仓库补齐 `.nvmrc`、`packageManager`、`engines.node` 三类声明。

核心理由不是“fnm 更新”或“pnpm 更新”，而是解决三类长期问题：

1. AI 工具与项目 Node 切换互相影响。
2. 90+ 仓库版本声明缺失，导致本地、CI、lockfile 行为漂移。
3. 新项目缺少默认标准，技术债继续扩散。

## 2. 当前事实与扫描结果

### 2.1 团队环境

- 仓库形态：多仓，约 90+ 个仓库，活跃仓库约 20-50 个。
- 当前 Node 管理方式：多数开发者使用 `nvm`，少量 Windows 成员使用 nvm-windows。
- CI 平台：Jenkins，固定长生命周期 Agent。
- 操作系统：大部分 macOS，少部分 Windows。
- 包管理器：pnpm，但版本跨度大。

### 2.2 Node 声明情况

| 指标 | 数量 | 评审关注 |
|---|---:|---|
| 有 `.nvmrc` | 4 | 覆盖率极低，自动切换不可依赖 |
| 无 `.nvmrc` | 约 89 | 新人主要靠口头信息 |
| 有 `engines.node` | 约 40 | 声明口径不统一 |
| 无任何 Node 声明 | 约 50 | CI 与本地环境不可解释 |

### 2.3 pnpm 声明情况

| pnpm 版本 | 项目数 | 代表项目 | 风险 |
|---|---:|---|---|
| 未声明 | 约 78 | 大部分项目 | lockfile 由个人环境决定 |
| 7.26.3 | 10 | admin-business-basics、admin-crm | 可升级到 8，但需单独提交 lockfile |
| 8.x | 2 | gc-website、tcm-gpt | 可作为 Node 16/18 过渡标准 |
| 9 | 1 | queue-calling-screen | 应对齐到 10 |
| 10 | 1 | admin-saas | 新项目标准候选 |
| 6.32.4 | 1 | vite-vue3-lowcode | 需要例外处理 |

## 3. 已确认的核心决策

### 3.1 本地统一 fnm，CI 暂不迁移

本地开发者统一使用 `fnm`，替代 `nvm`。Jenkins Agent 保持 `nvm` 不变。

理由：

- `fnm --use-on-cd` 对 `.nvmrc` 自动切换更稳定，macOS 和 Windows 一套文档可覆盖。
- `fnm` 是独立二进制，shell 启动成本低。
- nvm 可以先保留在磁盘上，只注释 shell 加载语句，回退成本低。
- Jenkins 现有 Linux Agent 不依赖跨平台自动切换，短期迁移收益不高。

### 3.2 AI 工具先解耦

AI 工具不等待仓库治理。Claude Code、Codex 等本地通用工具优先用官方独立安装方式，避免被项目 Node 切换影响。

仅当某工具只有 npm 包形式时，才在 `fnm default` 对应 Node 20 下全局安装。

### 3.3 Node 标准版本

| 大版本 | 团队标准 patch | 用途 | 状态 |
|---|---|---|---|
| 20 | 20.20.0 | 默认版本，新项目首选 | 主力 |
| 18 | 18.20.8 | 现有 18.x 项目过渡 | 过渡 |
| 16 | 16.20.2 | 现有 16.x 项目过渡 | 过渡 |

策略：全员安装精确 patch，但 `.nvmrc` 只写大版本号，如 `20`。这样 patch 升级时只更新团队指引，不批量改仓库。

### 3.4 pnpm 标准版本

| Node 版本 | pnpm 版本 | lockfile 格式 | 说明 |
|---|---|---|---|
| Node 20 | pnpm 10.30.3 | v9.0 | 新项目标准 |
| Node 18 | pnpm 8.15.9 | v6.1 | 过渡项目 |
| Node 16 | pnpm 8.15.9 | v6.1 | 过渡项目 |

不使用 corepack。原因：

- Node 25 起 corepack 不再内置。
- 企业私有源场景下 corepack shim 与全局 pnpm 管理容易增加排障复杂度。
- 团队本次的目标是降低变量，不是引入新的分发层。

## 4. 明确不做什么

| 不做事项 | 原因 | 后续条件 |
|---|---|---|
| 不迁移到 Volta | 工具链差异大，Jenkins 需改造 | 若未来 CI 一起重构再评估 |
| 不强推 Node 22/24 | Node 20 够用且更稳 | 有明确运行时需求再议 |
| 不把 Node 16/18 项目直接升 pnpm 10 | lockfile 格式和运行时约束不兼容 | 项目升到 Node 20 后再做 |
| 不改造 Jenkins 工具链 | CI 收益不足，风险较高 | 先补声明和校验 |
| 不一次性改完 90+ 仓库 | 批量风险大，业务迭代会被阻塞 | 分批推进 |

## 5. 执行阶段

### 第 0 阶段：AI 工具先行解耦

目标：1-2 天内解决开发者 AI 工具因 Node 切换失效的问题。

行动：

1. 发布独立安装说明。
2. 指导开发者确认在任意项目目录下都能运行 AI 工具。
3. 对仍需 npm 全局安装的工具，统一安装在 Node 20 默认环境下。

验收：

- 在 Node 16、18、20 项目目录下切换后，AI 工具仍可运行。
- 不要求任何业务仓库在此阶段改代码。

### 第 1 阶段：本地环境标准化

目标：全员安装 fnm、标准 Node 和对应 pnpm。

关键命令：

```bash
brew install fnm
fnm install 20.20.0
fnm install 18.20.8
fnm install 16.20.2
fnm default 20
fnm use 20 && corepack disable && npm install -g pnpm@10.30.3
fnm use 18 && corepack disable && npm install -g pnpm@8.15.9
fnm use 16 && corepack disable && npm install -g pnpm@8.15.9
```

风险：

- Windows PowerShell profile 路径差异可能导致 `fnm env` 未生效。
- 部分开发者本机已有全局 npm 工具，切换后需要重新安装或迁移。

### 第 2 阶段：仓库声明补齐

目标：按项目实际 Node 版本补齐 `.nvmrc`、`packageManager`、`engines.node`。

Node 20 项目：

```json
{
  "packageManager": "pnpm@10.30.3",
  "engines": {
    "node": ">=20.0.0 <21.0.0"
  }
}
```

Node 18 过渡项目：

```json
{
  "packageManager": "pnpm@8.15.9",
  "engines": {
    "node": ">=18.0.0 <21.0.0"
  }
}
```

Node 16 过渡项目：

```json
{
  "packageManager": "pnpm@8.15.9",
  "engines": {
    "node": ">=16.0.0 <21.0.0"
  }
}
```

### 第 3 阶段：CI 校验与例外治理

目标：CI 不负责修复 lockfile，只负责验证。

建议校验：

- `.nvmrc` 是否存在。
- `packageManager` 是否符合分层策略。
- `engines.node` 是否与 `.nvmrc` 大版本匹配。
- `pnpm install --frozen-lockfile` 是否通过。

例外清单字段：

| 字段 | 含义 |
|---|---|
| 仓库名 | 例外对象 |
| 当前 Node / pnpm | 当前真实状态 |
| 例外原因 | 为什么不能对齐 |
| 负责人 | 谁负责退出例外 |
| 到期时间 | 何时重新评估 |
| 退出条件 | 达成什么即可回归标准 |

## 6. 争议点与待评审问题

1. 是否允许两周内保留 nvm 加载注释作为回退，而不是直接删除。
2. 是否要求所有活跃仓库在同一个治理窗口补齐声明。
3. 是否把 corepack 禁用写成强制规则，还是仅作为推荐。
4. pnpm 7 项目升级到 8 时，lockfile 变更是否必须单独 MR。
5. Jenkins 是否只补校验脚本，还是同步安装 fnm 但不启用。

## 7. 风险登记

| 风险 | 影响 | 触发信号 | 缓解方式 |
|---|---|---|---|
| pnpm lockfile 大量变化 | MR 难 review | `pnpm-lock.yaml` 巨大 diff | lockfile 单独 MR，禁止混业务代码 |
| Windows 自动切换失败 | 少数成员环境不可用 | 进入目录后 Node 版本不变 | PowerShell profile 检查清单 |
| 老项目 engines 过严 | 安装直接失败 | `engine-strict` 或 CI 报错 | 先声明实际范围，不一刀切 Node 20 |
| AI 工具仍受 Node 影响 | 原始痛点未解决 | 切换项目后工具消失 | 优先独立安装，npm 工具只挂默认 Node |
| 例外项目失控 | 治理长期无法收敛 | 例外数不下降 | 例外清单要求到期和退出条件 |

## 8. 评审阅读难点

这份文档线性阅读时有几个问题：

- 版本表、阶段计划、风险登记、例外治理分散在不同章节。
- “当前本地迁移”和“CI 暂不迁移”容易被误读为口径冲突。
- 评审人需要快速切换“管理者摘要”“执行命令”“风险矩阵”“待决策问题”。
- 命令和 JSON 示例很长，不应占据首屏。
