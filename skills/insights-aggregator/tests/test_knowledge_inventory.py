"""Independent outputs keep all evidenced points and do not mutate the input."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from knowledge_inventory import load_inventory, write_inventory


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
            self.assertEqual(doc.count("<details>"), 13)
            self.assertIn('href="report.html"', doc)
            self.assertIn("&lt;script&gt;", doc)
            self.assertNotIn("<script>", doc)
            self.assertIn("K11", (Path(tmp) / "knowledge-inventory.md").read_text())
            self.assertEqual(json.loads((Path(tmp) / "knowledge-inventory.json").read_text()), data)
            self.assertEqual(path.read_text(), original)
            for output in outputs:
                self.assertEqual(Path(output).stat().st_mode & 0o777, 0o600)

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
