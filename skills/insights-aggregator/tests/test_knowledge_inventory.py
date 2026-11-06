"""Independent outputs keep all evidenced points and do not mutate the input."""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from knowledge_inventory import load_inventory, write_inventory, item_anchor, INVENTORY_FILTER_JS, ANCHOR_NAV_JS


class InventoryTests(unittest.TestCase):
    def example(self):
        return {"schema_version": 1, "scope": {"coverage": "two phases of one session"}, "items": [
            {"id": f"K{i}", "title": f"Point {i}", "category": "Engineering", "summary": "<script>alert(1)</script>",
             "status": "candidate", "lesson": "bounded", "existing_knowledge": {"relation": "unverified"},
             "evidence": [{"source_id": "S1", "locator": f"L{i}"}]} for i in range(12)]}

    def test_all_points_have_independent_outputs_and_safe_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.json"
            original = json.dumps(self.example())
            path.write_text(original)
            data = load_inventory(path)
            outputs = write_inventory(data, tmp, "body {}", "report.html")
            self.assertEqual(len(outputs), 3)
            doc = (Path(tmp) / "knowledge-inventory.html").read_text()
            self.assertEqual(len(re.findall(r"<details(?: |>)", doc)), 13)
            self.assertIn('href="report.html"', doc)
            self.assertIn("&lt;script&gt;", doc)
            self.assertNotIn("<script>alert(1)</script>", doc)
            self.assertIn("K11", (Path(tmp) / "knowledge-inventory.md").read_text())
            self.assertEqual(json.loads((Path(tmp) / "knowledge-inventory.json").read_text()), data)
            self.assertEqual(path.read_text(), original)
            for output in outputs:
                self.assertEqual(Path(output).stat().st_mode & 0o777, 0o600)

    def test_stable_safe_ids_and_no_js_inventory_is_complete(self):
        data = self.example()
        data["items"][0]["id"] = 'K<script> / 中文'
        data["items"][0]["status"] = '\"><img src=x onerror=alert(1)>'
        with tempfile.TemporaryDirectory() as tmp:
            write_inventory(data, tmp, "ORIGINAL_CSS", "report.html")
            doc = (Path(tmp) / "knowledge-inventory.html").read_text()
        self.assertIn('<style>ORIGINAL_CSS</style>', doc)
        self.assertEqual(doc.count('data-knowledge-item data-status='), len(data['items']))
        self.assertNotRegex(doc, r'data-knowledge-item[^>]*\shidden(?: |>)')
        self.assertIn('id="inventory-filter" class="narrative" hidden', doc)
        self.assertIn('id="inventory-result-count" role="status" aria-live="polite"', doc)
        self.assertNotIn('<img src=x', doc)
        self.assertIn('id="' + item_anchor(data['items'][0]['id']) + '"', doc)
        self.assertEqual(item_anchor('C172'), 'item-C172')
        self.assertNotEqual(item_anchor('a b'), item_anchor(':612062'))
        self.assertEqual(len({item_anchor(item['id']) for item in data['items']}), len(data['items']))

    @unittest.skipUnless(shutil.which("node"), "Node required for lightweight JS unit checks")
    def test_filter_and_hash_navigation_without_browser(self):
        setup = r"""
const assert = require('node:assert/strict');
const listeners = {};
function element(fields = {}) {
  return Object.assign({value: '', hidden: false, events: {}, closest() { return null; }, addEventListener(type, callback) { this.events[type] = callback; }, focus() { this.focused = true; }}, fields);
}
const firstDetail = {open: false};
const first = element({id: 'item-K1', textContent: '请求 LOG 已验证 <img src=x>', dataset: {status: '已验证'},
  querySelector() { return firstDetail; }, scrollIntoView() { this.scrolled = true; }, closest() { return this; }});
const second = element({id: 'item-K2', textContent: '授权候选', dataset: {status: '候选'},
  querySelector() { return null; }, scrollIntoView() {}, closest() { return this; }});
const category = {querySelectorAll() { return [first, second]; }};
first.parentElement = category; second.parentElement = category;
const els = {'inventory-filter': element({hidden: true}), 'inventory-query': element(), 'inventory-status': element(),
  'inventory-clear': element(), 'inventory-result-count': element(), 'item-K1': first, 'item-K2': second};
global.document = {getElementById(id) { return els[id]; },
  querySelectorAll(selector) { return selector === '[data-knowledge-item]' ? [first, second] : [category]; },
  addEventListener(type, callback) { (listeners[type] ||= []).push(callback); },
  dispatchEvent(event) { (listeners[event.type] || []).forEach(callback => callback(event)); }};
global.CustomEvent = class { constructor(type, options) { this.type = type; this.detail = options.detail; } };
global.window = {addEventListener(type, callback) { this[type] = callback; }};
global.location = {hash: '#item-K1'};
global.requestAnimationFrame = callback => callback();
"""
        checks = r"""
assert.equal(firstDetail.open, true); // Initial deep link opens details and focuses target.
assert.equal(first.focused, true);
assert.equal(els['inventory-filter'].hidden, false);
const query = els['inventory-query'], status = els['inventory-status'], count = els['inventory-result-count'];
query.value = '请求 log'; query.events.input();
assert.equal(first.hidden, false); assert.equal(second.hidden, true); assert.equal(count.textContent, '显示 1 / 2 项');
status.value = '候选'; status.events.change();
assert.equal(category.hidden, true); assert.equal(count.textContent, '显示 0 / 2 项');
query.value = '<img src=x>'; status.value = ''; query.events.input();
assert.equal(first.hidden, false); // Search terms remain text and never become HTML.
let prevented = false;
els['inventory-filter'].events.submit({preventDefault() { prevented = true; }}); assert.equal(prevented, true);
query.value = 'no result'; query.events.input(); firstDetail.open = false;
window.hashchange(); // Existing filter cannot hide an incoming hash target.
assert.equal(first.hidden, false); assert.equal(second.hidden, false); assert.equal(firstDetail.open, true);
assert.equal(query.value, ''); assert.equal(count.textContent, '显示 2 / 2 项');
status.value = '候选'; status.events.change(); els['inventory-clear'].events.click();
assert.equal(status.value, ''); assert.equal(query.focused, true);
location.hash = '#%bad'; window.hashchange(); // Malformed URL fragment is harmless.
const source = element({id: 'source-E1', tagName: 'DETAILS', open: false, querySelector() { return null; }, scrollIntoView() {}});
els['source-E1'] = source;
document.dispatchEvent({type: 'click', target: {closest() { return {getAttribute() { return '#source-E1'; }}; }}});
assert.equal(source.open, true); assert.equal(source.focused, true);
"""
        result = subprocess.run([shutil.which("node"), "-"], input=setup + INVENTORY_FILTER_JS + ANCHOR_NAV_JS + checks,
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_no_unlocated_or_duplicate_knowledge(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.json"
            for mutation in (lambda d: d["items"].append(d["items"][0]),
                             lambda d: d["items"][0]["evidence"][0].pop("locator")):
                data = self.example()
                mutation(data)
                path.write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    load_inventory(path)


if __name__ == "__main__":
    unittest.main()
