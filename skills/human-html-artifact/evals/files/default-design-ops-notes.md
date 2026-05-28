# 导出队列状态简报

## 当前状态

导出队列延迟升高，但还没有触发全量降级。当前建议是先控制新增导出量，同时评估是否在周三前扩大 worker pool。

## 关键指标

- backlog：184 个导出任务
- P95 等待时间：9.2 分钟
- 账单同步延迟：37 分钟
- 当前 worker 数：6
- 建议扩容目标：10

## 阻塞项

1. 是否扩大 worker pool 需要周三前确认。
2. 账单同步延迟是否由导出队列触发还未完全确认。
3. 部分大客户导出任务没有拆分，单任务耗时偏长。

## 证据

```txt
queue/export/backlog = 184
queue/export/p95_wait = 9.2m
billing/sync_delay = 37m
```

## 行动项

- 先暂停非必要批量导出。
- 复查大客户导出任务是否可以切分。
- 准备 worker pool 扩容回滚命令。

```bash
pnpm ops:scale export-worker --replicas 10
pnpm ops:scale export-worker --replicas 6
```
