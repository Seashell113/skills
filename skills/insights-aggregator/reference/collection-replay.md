# 冻结采集恢复与阅读前归属校准

适用于已有 Codex snapshot manifest 的确定性重放，不调用 LLM、不扩大原清单。`collect.py` 已把同次扫描或 manifest 的父源传给 owned reader；自建 packet、补读和组批脚本也应复用下面的入口，不能直接按事件时间组批后再校准继承历史。

## 旧 JSONL 路径压缩迁移

旧 manifest 记录的是当时未压缩 JSONL 的 `byte_length` / `sha256`。路径消失而同名 `.jsonl.zst` 存在时，后缀只是定位线索，不能把原长度和 hash 当成压缩物理身份。

```bash
python3 {skill_dir}/scripts/recover_codex_snapshot.py \
  --manifest /private/run/statistics-manifest.json \
  --out /private/run/recovery-map.json

python3 {skill_dir}/scripts/collect.py \
  --codex-snapshot-manifest /private/run/statistics-manifest.json \
  --codex-recovery-map /private/run/recovery-map.json \
  --home /private/run/replay --since <原起点> --as-of <原终点> \
  --max-load 2000 --max-facets 0
```

恢复脚本只检查 manifest 内缺失路径的同名压缩候选。新映射以 0600 排他创建，不覆盖旧 manifest、旧映射或源文件。退出码为 0 且 `failed=0` 后才重放；失败项保留原因，不降级 hash 检查。生成器不证明源清单之外的完整性。

映射绑定原 manifest 文件 hash、snapshot ID、每项原 path/session_id/逻辑长度/hash，另记压缩后继的物理路径、长度、mtime 和 hash。读取时重验压缩物理长度/hash，完整解压到自动关闭的私密临时文件，确认 zstd 完整性，再核对解压后的原冻结前缀 hash；只把该前缀交给解析器。压缩前已追加的后续字节可以存在，但不会进入旧快照。逻辑与物理 hash 不混用，也不持久保存解压全文。

原路径仍存在时优先读原路径；即使原 hash 错误，也不悄悄回退压缩后继。没有显式恢复映射时不会自动猜测路径。原生 manifest 本来就指向 `.jsonl.zst` 的条目继续按压缩物理前缀校验。

## packet 和组批共用同一冻结父源

在消息筛选、时间窗口、容量切块和派发阅读前，先用完整冻结身份集合构建 `sources`。选中会话只是阅读范围，父源可来自该 manifest 的其他成员，不能从选中子会话列表重新构造一个缺父源的集合。

```python
from codex_segments import load_snapshot_sources, read_owned_snapshot_session

sources = {s["session_id"]: s for s in load_snapshot_sources(manifest, recovery_map)}
stream = read_owned_snapshot_session(sources, selected_session_id)
audit = stream.audit
if not audit["identity_valid"] or audit["owner_leakage_lines"] or audit["invalid_json_lines"]:
    raise ValueError("冻结源或归属校验失败，停止组批")
fork = audit.get("fork_history")
queue = "unknown_attribution" if fork and fork["status"] != "native_anchored_exact_prefix" else "current"
# 保存 audit、原行号和 queue，再从 stream.records 提取/脱敏可见消息、裁时间窗口。
# unknown 队列保留原消息供定向阅读，由主控决定是否进入精确统计分母。
# current 队列只含已排除认证父历史的 owned stream。
```

`read_owned_snapshot_session` 自动把同一 `sources` 传给子源和父源，不扫描其他会话文件。只有冻结父源 hash 通过、连续前缀逐行匹配且有原生 ID 锚点，才能排除继承历史。未能证明时保留全部原事件并标明未知，不能凭文本相似清零。`owner_leakage_lines=0` 本身不证明 fork 已认证。原父源缺失、hash 不符或解压失败均应处理后再组批。

阅读派发与统计应使用同一校准后的流；不要复用“源 hash 相同但归属依赖不同”的旧 packet/统计缓存。复用缓存时除本源身份、解析版本和窗口外，还应核对 `fork_parent_source(sources[parent_id])`，其中包含父源及恢复身份。每项保存 audit 与依赖，使后续能回到原父源行号，不把被排除历史当作独立效果复现。

## 长会话的后续纠正

字符容量切块保证输入可控，不保证块边界就是业务阶段。汇总一个长会话时串行核对后段是否纠正了前段结论，简记“原候选 ID → 后续纠正来源 → 当前状态/合并去向/仍未知”。不要求每块重读全会话。覆盖检查只能验证输入与阅读声明；高影响判断、异常归属和跨块纠正仍需主控按具体原文抽查。
