"""报告渲染测试：终端表格、JSON 导出、HTML 单文件（含转义与条形图）。"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from undertest.churn import FileChurn
from undertest.mapping import build_mapping, find_hotspots
from undertest.report import render_html, render_json, render_terminal

REPO = Path("/fake/repo")

CHURN = {
    "core/app.py": FileChurn("core/app.py", commits=9, added=120, deleted=30, last_ts=1700000000),
    "hot1.py": FileChurn("hot1.py", commits=5, added=50, deleted=10, last_ts=1700000001),
    "hot2.py": FileChurn("hot2.py", commits=4, added=8, deleted=2, last_ts=0),
    "readme.md": FileChurn("readme.md", commits=99, added=1, deleted=0, last_ts=0),
}
MAPPING = build_mapping(list(CHURN) + ["tests/test_app.py"])
HOTSPOTS = find_hotspots(CHURN, MAPPING)


class TerminalTest(unittest.TestCase):
    def test_top_limits_rows(self) -> None:
        text = render_terminal(REPO, CHURN, MAPPING, HOTSPOTS, top=1)
        self.assertIn("测试黑洞 TOP 1", text)
        self.assertIn("hot1.py", text)
        self.assertNotIn("hot2.py", text)

    def test_headers_and_no_hotspot_message(self) -> None:
        text = render_terminal(REPO, CHURN, MAPPING, HOTSPOTS, top=99)
        self.assertIn("源码文件", text)
        self.assertIn("Commits", text)

        text2 = render_terminal(REPO, {}, {}, [], top=20)
        self.assertIn("无", text2)


class JsonTest(unittest.TestCase):
    def test_structure_and_sorting(self) -> None:
        data = json.loads(render_json(REPO, CHURN, MAPPING, HOTSPOTS))
        self.assertEqual(data["tool"], "undertest")
        self.assertEqual(data["hotspots"][0]["file"], "hot1.py")
        self.assertEqual(data["hotspots"][0]["commits"], 5)
        files = {f["file"]: f for f in data["files"]}
        # 全量导出且 hot1 无测试、core/app.py 有测试
        self.assertIn("readme.md", files)
        self.assertEqual(files["hot1.py"]["tests"], [])
        self.assertEqual(files["core/app.py"]["tests"], ["tests/test_app.py"])
        self.assertTrue(files["core/app.py"]["is_test_file"] is False)
        self.assertTrue(data["stats"]["hotspot_count"] >= 2)


class HtmlTest(unittest.TestCase):
    def test_contains_css_bars_and_escapes(self) -> None:
        nasty = FileChurn("<script>alert(1)</script>.py", commits=7, added=1, deleted=0)
        churn2 = {"x": nasty}
        html_doc = render_html(REPO, churn2, {}, [nasty], top=10)
        self.assertIn("<style>", html_doc)
        self.assertIn("bar-row", html_doc)
        self.assertIn("width:", html_doc)  # 条形图宽度
        self.assertNotIn("<script>alert(1)</script>", html_doc)  # 已转义
        self.assertIn("&lt;script&gt;", html_doc)

    def test_empty_no_crash(self) -> None:
        html_doc = render_html(REPO, {}, {}, [], top=20)
        self.assertIn("没有发现测试黑洞", html_doc)


if __name__ == "__main__":
    unittest.main()