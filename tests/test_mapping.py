"""映射测试：测试文件识别、源码->测试映射、热区排序（纯路径集合运算）。"""

from __future__ import annotations

import unittest

from undertest.churn import FileChurn
from undertest.mapping import (
    build_mapping,
    find_hotspots,
    is_test_file,
    source_candidates_for_test,
    test_candidates_for_source,
)


class IsTestFileTest(unittest.TestCase):
    def test_python_naming(self) -> None:
        self.assertTrue(is_test_file("test_foo.py"))
        self.assertTrue(is_test_file("tests/test_app.py"))
        self.assertTrue(is_test_file("foo_test.py"))
        self.assertTrue(is_test_file("pkg/sub/test_mod.py"))

    def test_python_non_test(self) -> None:
        self.assertFalse(is_test_file("foo.py"))
        self.assertFalse(is_test_file("src/main.py"))
        self.assertFalse(is_test_file("pythonista.py"))  # 仅后缀 *_test.py 才算

    def test_js_naming(self) -> None:
        self.assertTrue(is_test_file("foo.spec.js"))
        self.assertTrue(is_test_file("foo.test.js"))
        self.assertTrue(is_test_file("search.spec.ts"))
        self.assertTrue(is_test_file("foo.test.jsx"))
        self.assertFalse(is_test_file("foo.js"))
        self.assertFalse(is_test_file("spec_helper.js"))

    def test_dir_convention(self) -> None:
        self.assertTrue(is_test_file("__tests__/core.test.js"))
        self.assertTrue(is_test_file("tests/util.py"))  # tests/ 目录按目录归属识别
        self.assertFalse(is_test_file("tests/__init__.py"))  # 辅助文件不算
        self.assertFalse(is_test_file("tests/conftest.py"))
        self.assertFalse(is_test_file("tests/helpers.py"))


class BuildMappingTest(unittest.TestCase):
    FILES = [
        "src/app.py",
        "tests/test_app.py",
        "utils.py",
        "test_utils.py",
        "lib/helper.js",
        "lib/helper.spec.js",
        "comp/core.js",
        "__tests__/core.test.js",
        "orphan.py",
        "cfg.py",
        "tests/test_cfg.py",
        "pkg/sub/x.py",
        "tests/pkg/sub/test_x.py",
    ]

    def test_common_layouts(self) -> None:
        mapping = build_mapping(self.FILES)
        self.assertEqual(mapping["src/app.py"], ["tests/test_app.py"])
        self.assertEqual(mapping["utils.py"], ["test_utils.py"])
        self.assertEqual(mapping["lib/helper.js"], ["lib/helper.spec.js"])
        self.assertEqual(mapping["comp/core.js"], ["__tests__/core.test.js"])
        self.assertEqual(mapping["cfg.py"], ["tests/test_cfg.py"])  # 反向规则补全
        self.assertEqual(mapping["pkg/sub/x.py"], ["tests/pkg/sub/test_x.py"])  # 镜像

    def test_orphan_has_no_mapping(self) -> None:
        mapping = build_mapping(self.FILES)
        self.assertNotIn("orphan.py", mapping)

    def test_candidates_are_supersets_of_hits(self) -> None:
        for rel in self.FILES:
            hits = {t for t in self.FILES if t in test_candidates_for_source(rel)}
            for t in hits:
                self.assertTrue(is_test_file(t), f"{t} 应为测试文件")

    def test_backward_source_candidates(self) -> None:
        # tests/test_app.py 的源码候选应包含 root/app.py 与 src/app.py
        cands = source_candidates_for_test("tests/test_app.py")
        self.assertIn("app.py", cands)
        self.assertIn("src/app.py", cands)
        # tests/pkg/test_x.py 的镜像候选：pkg/x.py
        self.assertIn("pkg/x.py", source_candidates_for_test("tests/pkg/test_x.py"))


class HotspotTest(unittest.TestCase):
    def test_sort_and_filter(self) -> None:
        churn = {
            "a.py": FileChurn("a.py", commits=5, added=10, deleted=2),
            "b.py": FileChurn("b.py", commits=3, added=100, deleted=0),
            "c.py": FileChurn("c.py", commits=3, added=5, deleted=0),
            "d.py": FileChurn("d.py", commits=4, added=8, deleted=0),  # 有测试：不进热区
            "tests/test_d.py": FileChurn(  # 测试文件本身：改动再频繁也不进热区
                "tests/test_d.py", commits=50, added=200, deleted=0
            ),
            "readme.md": FileChurn("readme.md", commits=99, added=1, deleted=0),  # 非可测源码
        }
        mapping = {"d.py": ["test_d.py"]}
        hotspots = find_hotspots(churn, mapping)
        order = [fc.path for fc in hotspots]
        # commit 次数降序；同次数看净行（b.py 100 > c.py 5）
        self.assertEqual(order, ["a.py", "b.py", "c.py"])
        self.assertNotIn("d.py", order)
        self.assertNotIn("tests/test_d.py", order)
        self.assertNotIn("readme.md", order)

    def test_empty(self) -> None:
        self.assertEqual(find_hotspots({}, {}), [])


if __name__ == "__main__":
    unittest.main()