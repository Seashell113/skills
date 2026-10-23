# 独立知识与经验盘点

阅读报告帮助理解这一阶段的使用方式、变化和下一步尝试；盘点保存可再次检索、核验、归位的知识点。两者共用来源，但条目数量、完整性要求和写法不同。知识盘点不是已采纳决定清单，也不自动写入用户知识库。

## 提取与覆盖

优先复用已有来源、原文核验和分析。一个长会话可以包含多个任务阶段和不同领域的知识点；按命题拆条，合并重复，保留冲突、条件、证据状态和未解决问题。不按“一会话一条”压缩，也不为凑数量拆分同一结论。

默认 facet 的单消息与头尾截断无法证明长会话完整覆盖。必要时在已授权会话内按阶段定位原文，记录读过的消息/行范围、未读部分和窗口前背景。盘点的完整性只相对于实际已读范围；不写“全历史穷尽”。业务、项目、技术、组织、个人工作经验均可纳入，不局限于 Agent 操作建议。

已有知识关系只记录可核实的命中与关系（已有、兼容补充、矛盾、待核对）；没有检索不能称“尚未沉淀”。助手回执、用户认可、外部验收和当前仍然适用分别判断。未决事项可以保留，建议不能变成用户决定。

## 数据结构

以 UTF-8 JSON 保存，最小示例：

```json
{
  "schema_version": 1,
  "title": "历史知识与经验盘点",
  "scope": {
    "window": "窗口起止及开闭边界",
    "sessions_read": 1,
    "coverage": "实际读过的阶段与原文范围",
    "limits": "未覆盖部分与时效边界"
  },
  "items": [{
    "id": "K01",
    "title": "有具体对象的知识点",
    "category": "工程经验",
    "summary": "一两句话表达可复用内容",
    "context": "形成背景",
    "lesson": "事实支持的判断，必要时标为候选",
    "reuse_when": "适用条件",
    "status": "已验证经验 / 候选判断 / 用户偏好 / 未决问题 / 仅方案等实际状态",
    "evidence": [{"source_id": "S1", "locator": "来源身份和行范围", "quote_or_summary": "支撑事实的摘要"}],
    "existing_knowledge": {"relation": "待核对", "target": "", "note": "本轮未核对长期知识"},
    "next_step": "可选：补证或归位建议"
  }]
}
```

将此文件交给原渲染器：

```bash
python3 scripts/render.py --home /private/path/run --out /private/path/run/report.html \
  --knowledge-inventory /private/path/run/knowledge-inventory-input.json
```

在报告同目录生成 `knowledge-inventory.html`、`.md`、`.json`，并加入往返链接。HTML 复用原报告 CSS；Markdown 与 JSON 可独立用于后续检索、去重和知识治理。报告中 `knowledge_findings` 只选少量值得读者思考或尝试的内容，详细盘点与证据不重复铺进主报告。
