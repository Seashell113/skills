"""Synthetic only: no private sessions or report snapshots."""
import hashlib
import contextlib
import io
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from aggregate import aggregate_group, parse_iso, namespace_facet_sources, write_outputs, build_context
from evidence_bundle import load_bundle
from render import evidence_sections, metric, source_anchors, md_bold, TEXT_SOURCE_ANCHORS


def example():
    return {
        "schema_version": 1, "generated_at": "2026-10-01T00:00:00Z",
        "window": {"days": 30, "cutoff": "2026-09-01T00:00:00Z", "as_of": "2026-10-01T00:00:00Z"},
        "selection": {"method": "synthetic selected sample", "limits": "not representative",
                      "direct_read_sessions": 1, "facets_extracted": 0,
                      "scope_note": "3 user + 4 assistant messages"},
        "metrics": {"combined": {"total_sessions": 1, "sessions_with_facets": 0,
                                  "total_messages": 3, "git_commits": 0},
                    "by_agent": {"codex": {"total_sessions": 1, "total_messages": 3}}},
        "sources": [{"id": "S<script>", "locator": 'L2 <img src=x onerror="alert(1)">',
                     "session_id": "synthetic", "title": "Example", "summary": "bounded observation"}],
        "knowledge_candidates": [{"finding": "candidate only"}],
        "infrastructure_observations": [{"observed_result": "observed only"}],
    }


class EvidenceBundleTests(unittest.TestCase):
    def write_bundle(self, root, bundle):
        path = root / "bundle.json"
        path.write_text(json.dumps(bundle), encoding="utf-8")
        return path

    def test_unknown_and_zero_are_distinct(self):
        with tempfile.TemporaryDirectory() as tmp:
            agg = load_bundle(self.write_bundle(Path(tmp), example()), aggregate_group([], {}), parse_iso)
        self.assertIsNone(agg["combined"]["total_duration_hours"])
        self.assertEqual(agg["combined"]["git_commits"], 0)
        self.assertNotIn("models", agg["combined"]["available_metrics"])
        self.assertIn("git_commits", agg["combined"]["available_metrics"])
        self.assertFalse(agg["cross_tool_metrics_available"])
        self.assertEqual(metric(None), "未知")
        self.assertEqual(metric(0), "0")

    def test_reuse_cli_preserves_scope_sources_and_original_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self.write_bundle(root, example())
            # A malformed cache proves this path does not consume old metadata/facets.
            cache = root / "cache/meta/codex"
            cache.mkdir(parents=True)
            (cache / "old.json").write_text('{"start_time":"bad"}', encoding="utf-8")
            subprocess.run([sys.executable, str(SCRIPTS / "aggregate.py"), "--evidence-bundle", str(path),
                            "--home", str(root), "--days", "1"], check=True, capture_output=True)
            context = (root / "work/insight-context.md").read_text(encoding="utf-8")
            self.assertIn("candidate only", context)
            self.assertIn("observed only", context)
            self.assertIn("available_metrics", context)
            self.assertIn("直接阅读不等于完成 facet", context)
            insights = root / "work/insights"
            insights.mkdir()
            sections = {
                "project_areas": {"areas": [{"name": "Original work area", "session_count": 1}]},
                "what_works": {"impressive_workflows": [{"title": "Original usage insight", "description": "Kept"}]},
                "tool_comparison": {"narrative": "MUST_NOT_RENDER_COMPARISON"},
                "cross_tool_workflows": {"observed_patterns": [{"title": "MUST_NOT_RENDER_HANDOFF"}]},
                "at_a_glance": {"quick_wins": "Next action", "tool_division": "MUST_NOT_RENDER_DIVISION"},
                "suggestions": {"config_additions": [], "usage_patterns": [{"title": "Try one change"}]},
                "knowledge_findings": {"intro": "Knowledge", "findings": [{"title": "New knowledge",
                    "finding": "<script>alert(1)</script>", "status": "candidate", "evidence": ["S<script>"]}]},
                "infrastructure_effectiveness": {"assessments": [{"name": "Actual mechanism",
                    "observed_result": "bounded", "alternative_and_cost": "未知", "evidence": ["S<script>"]}]},
            }
            for name, value in sections.items():
                (insights / f"{name}.json").write_text(json.dumps(value), encoding="utf-8")
            out = root / "report.html"
            subprocess.run([sys.executable, str(SCRIPTS / "render.py"), "--home", str(root), "--out", str(out)],
                           check=True, capture_output=True)
            report = out.read_text(encoding="utf-8")
            self.assertIn("Original usage insight", report)
            self.assertIn("Original work area", report)
            self.assertIn("New knowledge", report)
            self.assertIn("Actual mechanism", report)
            self.assertIn("直接阅读任务", report)
            self.assertNotIn("0/1", report)
            self.assertIn("用户消息", report)
            self.assertNotIn('id="section-model-effort"', report)
            self.assertNotIn('id="section-charts"', report)
            self.assertNotIn('<div class="stat-value">未知</div>', report)
            self.assertLess(report.index('速览'), report.index('选样方法：'))
            self.assertIn("选样范围 2026-09-01", report)
            self.assertIn("3 user + 4 assistant", report)
            self.assertNotIn("MUST_NOT_RENDER", report)
            self.assertIn('href="#section-patterns"', report)
            self.assertNotIn('href="#section-features"', report)
            self.assertIn('href="#' + source_anchors(example()['sources'])['S<script>'] + '"', report)
            self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', report)
            self.assertNotIn('<img src=x', report)
            self.assertEqual(out.stat().st_mode & 0o777, 0o600)
            self.assertEqual((root / "work/aggregated.json").stat().st_mode & 0o777, 0o600)

    def test_missing_source_is_visible_and_escaped(self):
        html, _, _ = evidence_sections({"knowledge_findings": {"findings": [
            {"title": "Example", "evidence": ['<unknown>']}]}}, [])
        self.assertIn("&lt;unknown&gt;（来源未提供）", html)
        self.assertNotIn('<unknown>', html)

    def test_focused_bundle_keeps_totals_and_hides_stale_cross_tool_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = example()
            bundle["selection"]["focus_note"] = 'Only current tool <script>alert(1)</script>'
            bundle["window"]["cutoff"] = "2026-09-01T17:00:00Z"
            bundle["display_timezone"] = {"name": "Asia/Shanghai"}
            group = {"total_sessions": 12, "total_messages": 40, "days_active": 7}
            bundle["metrics"] = {"combined": group, "by_agent": {"codex": group}}
            agg = load_bundle(self.write_bundle(root, bundle), aggregate_group([], {}), parse_iso)
            with contextlib.redirect_stdout(io.StringIO()):
                write_outputs(tmp, agg, [])
            context = (root / "work/insight-context.md").read_text()
            self.assertNotIn("## Cross-tool signals", context)
            self.assertNotIn("Claude Code", context)
            ins = root / "work/insights"
            ins.mkdir()
            for name, value in {
                "tool_comparison": {"narrative": "STALE_COMPARISON"},
                "cross_tool_workflows": {"observed_patterns": [{"title": "STALE_HANDOFF"}]},
                "at_a_glance": {"tool_division": "STALE_DIVISION"},
            }.items():
                (ins / (name + ".json")).write_text(json.dumps(value))
            out = root / "report.html"
            subprocess.run([sys.executable, str(SCRIPTS / "render.py"), "--home", tmp, "--out", str(out)],
                           check=True, capture_output=True)
            report = out.read_text()
            self.assertIn("Codex 使用洞察报告", report)
            self.assertIn('<div class="stat-value">12</div>', report)
            self.assertIn('<div class="stat-value">40</div>', report)
            self.assertIn('<div class="stat-value">7</div>', report)
            self.assertNotIn("STALE_", report)
            self.assertNotIn('id="section-tools"', report)
            self.assertIn("选样范围 2026-09-02", report)
            self.assertIn("Only current tool &lt;script&gt;", report)
            self.assertNotIn("Only current tool <script>", report)

    def test_context_keeps_cross_tool_evidence_only_for_multiple_tools(self):
        group = aggregate_group([], {})
        agg = {"combined": group, "by_agent": {"codex": group, "claude-code": group},
               "cross_tool": {"overlap": {}, "handoffs": {"direction_counts": {}, "examples": []},
                              "project_tool_matrix": {}}}
        context = build_context(agg, [])
        self.assertIn("## Cross-tool signals", context)
        self.assertIn("Claude Code 的 models 单位", context)
        self.assertIn("不能仅凭模型名称", context)

    def test_window_statistics_and_inventory_keep_separate_scopes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = example()
            bundle["selection"].update(statistics_scope="window", semantic_metrics_scope="sample")
            bundle["display_timezone"] = {"name": "Asia/Shanghai", "label": "CST", "utc_offset": "+0800"}
            for group in [bundle["metrics"]["combined"], bundle["metrics"]["by_agent"]["codex"]]:
                group.update(total_sessions=20, tool_wrapped_calls=5, languages={"Python": 1},
                             total_lines_added=2, total_lines_removed=1,
                             tool_category_counts={"orchestration": 5}, message_hours=[9])
            path = self.write_bundle(root, bundle)
            subprocess.run([sys.executable, str(SCRIPTS / "aggregate.py"), "--evidence-bundle", str(path),
                            "--home", str(root)], check=True, capture_output=True)
            inventory = root / "inventory-input.json"
            inventory.write_text(json.dumps({"schema_version": 1, "scope": {"sessions_read": 1}, "items": [
                {"id": "K1", "title": "Point", "summary": "Bounded", "status": "candidate",
                 "evidence": [{"source_id": "S1", "locator": "L2"}]}]}))
            out = root / "report.html"
            subprocess.run([sys.executable, str(SCRIPTS / "render.py"), "--home", str(root), "--out", str(out),
                            "--knowledge-inventory", str(inventory)], check=True, capture_output=True)
            report = out.read_text()
            stats = re.search(r'<div class="stats-row">(.*?)</div>\s*<p', report, re.S).group(1)
            self.assertIn("活跃会话", stats)
            self.assertIn("直接阅读任务", stats)
            self.assertNotIn("提交命令记录", stats)
            self.assertNotIn("涉及语言", report)
            self.assertIn("Asia/Shanghai", report)
            self.assertIn("内部的工具未完整展开", report)
            self.assertIn('href="knowledge-inventory.html"', report)
            self.assertTrue((root / "knowledge-inventory.html").is_file())

    def test_rejects_duplicate_source_and_mistyped_metric(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for mutate in (lambda b: b["sources"].append(b["sources"][0]),
                           lambda b: b["metrics"]["combined"].update({"duration_hours_typo": 10}),
                           lambda b: b["metrics"]["combined"].update({"git_commits": -1})):
                bundle = example()
                mutate(bundle)
                with self.assertRaises(ValueError):
                    load_bundle(self.write_bundle(root, bundle), aggregate_group([], {}), parse_iso)

    def test_inline_references_accept_chinese_parentheses_and_multiple_ids(self):
        TEXT_SOURCE_ANCHORS.update({"E03": "source-E03", "E05": "source-E05"})
        try:
            rendered = md_bold('<script>（E03、E05、E99）（E030） (E03/E05)')
            self.assertEqual(rendered.count('href="#source-E03"'), 2)
            self.assertEqual(rendered.count('href="#source-E05"'), 2)
            self.assertIn('E99', rendered)
            self.assertNotIn('href="#source-E030"', rendered)
            self.assertIn('&lt;script&gt;', rendered)
        finally:
            TEXT_SOURCE_ANCHORS.clear()

    def test_readable_source_anchor_is_stable_across_reordering(self):
        sources = [{"id": "E16"}, {"id": "E2"}]
        self.assertEqual(source_anchors(sources)["E16"], "source-E16")
        self.assertEqual(source_anchors(sources), source_anchors(list(reversed(sources))))

    def test_two_facets_with_local_s1_get_distinct_sources_without_changing_cache(self):
        facets = [{"agent": "codex", "session_id": sid,
                   "sources": [{"id": "S1", "locator": "L1", "title": sid}],
                   "knowledge_candidates": [{"finding": sid, "evidence": ["S1", "missing"]}],
                   "infrastructure_observations": [{"name": sid, "evidence": ["S1"]}]}
                  for sid in ("first", "second")]
        original = json.dumps(facets, sort_keys=True)
        agg = {"combined": aggregate_group([], {}), "by_agent": {"codex": aggregate_group([], {})},
               "cross_tool": {"overlap": {}, "handoffs": {"direction_counts": {}, "examples": []},
                              "project_tool_matrix": {}}}
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            write_outputs(tmp, agg, facets)
            output = json.loads((Path(tmp) / "work/aggregated.json").read_text())
            context = (Path(tmp) / "work/insight-context.md").read_text()
        ids = [source["id"] for source in output["sources"]]
        self.assertEqual(ids, ["facet/codex/first/S1", "facet/codex/second/S1"])
        self.assertRegex(context, r'"evidence": \[\s+"facet/codex/first/S1"')
        self.assertIn('"facet/codex/second/S1"', context)
        self.assertIn('"facet/codex/first/missing"', context)
        self.assertEqual(json.dumps(facets, sort_keys=True), original)
        self.assertEqual(len(set(source_anchors(output["sources"]).values())), 2)
        facets[0]["sources"].append({"id": "S1"})
        with self.assertRaisesRegex(ValueError, "duplicate source ids within facet"):
            namespace_facet_sources(facets)

    def test_new_sections_keep_primary_findings_and_sources_outside_details(self):
        knowledge, infra, _ = evidence_sections({
            "knowledge_findings": {"findings": [{"title": "K", "finding": "PRIMARY_FINDING",
                "reuse": "DETAIL_REUSE", "status": "DETAIL_STATUS", "limits": "DETAIL_LIMIT",
                "evidence": ["S1"]}]},
            "infrastructure_effectiveness": {"assessments": [{"name": "I", "purpose": "DETAIL_PURPOSE",
                "observed_result": "PRIMARY_RESULT", "decision": "PRIMARY_DECISION",
                "alternative_and_cost": "DETAIL_COST", "next_check": "DETAIL_CHECK", "evidence": ["S1"]}]},
        }, [{"id": "S1", "locator": "L1"}])
        for rendered, primary, secondary in ((knowledge, ["PRIMARY_FINDING"], ["DETAIL_REUSE", "DETAIL_STATUS", "DETAIL_LIMIT"]),
                                             (infra, ["PRIMARY_RESULT", "PRIMARY_DECISION"], ["DETAIL_PURPOSE", "DETAIL_COST", "DETAIL_CHECK"])):
            before, details = rendered.split("<details>", 1)
            self.assertNotIn("<details open", rendered)
            self.assertIn('href="#source-S1"', before)
            for value in primary:
                self.assertIn(value, before)
            for value in secondary:
                self.assertIn(value, details)
                self.assertNotIn(value, before)

    def test_css_is_byte_identical_to_original_renderer(self):
        source = (SCRIPTS / "render.py").read_text(encoding="utf-8")
        css = re.search(r'    css = """(.*?)    """', source, re.S).group(1)
        self.assertEqual(hashlib.sha256(css.encode()).hexdigest(),
                         "b1ab006e7457e18b11be910aaa3c98607fba439a5a662c994031d68eafd8d19b")


if __name__ == "__main__":
    unittest.main()
