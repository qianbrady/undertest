"""CLI 集成测试：在真实 git 夹具仓库上运行完整主流程（终端 / JSON / HTML / 错误路径）。"""

from __future__ import annotations

import contextlib
import io
import json
import unittest
from pathlib import Path

from tests.helpers import GitFixtureTestMixin, commit_all, write_file
from undertest.cli import main


class CliIntegrationTest(GitFixtureTestMixin, unittest.TestCase):
    """构造一个多 commit 夹具仓库：app.py（有测试）、helper.py（无测试）。"""

    def make_busy_repo(self) -> None:
        write_file(self.repo, "core/app.py", "a\nb\n")
        commit_all(self.repo, "c1: app init")
        write_file(self.repo, "core/app.py", "a\nb\nc\n")
        commit_all(self.repo, "c2: app grow")
        write_file(self.repo, "util/helper.py", "x\n")
        commit_all(self.repo, "c3: helper init")
        write_file(self.repo, "util/helper.py", "x\ny\n")
        commit_all(self.repo, "c4: helper grow")
        write_file(self.repo, "tests/test_app.py", "import unittest\n")
        commit_all(self.repo, "c5: app tests")
        write_file(self.repo, "README.md", "doc line\n")
        commit_all(self.repo, "c6: docs")

    def run_main(self, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main([*argv])
        return code, out.getvalue(), err.getvalue()

    def test_terminal_top1_only_hotspot(self) -> None:
        self.make_busy_repo()
        code, out, _ = self.run_main(str(self.repo), "--top", "1")
        self.assertEqual(code, 0)
        self.assertIn("测试黑洞", out)
        self.assertIn("util/helper.py", out)  # 高频且无测试 -> 黑洞
        self.assertNotIn("core/app.py", out)  # 有测试不出现

    def test_json_and_html_export(self) -> None:
        self.make_busy_repo()
        json_path = self._dir / "out.json"
        html_path = self._dir / "out.html"
        code, out, _ = self.run_main(
            str(self.repo), "--top", "5", "--json", str(json_path), "--html", str(html_path)
        )
        self.assertEqual(code, 0)
        self.assertIn("已导出 json 报告", out)
        self.assertIn("已导出 html 报告", out)

        data = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertEqual(data["stats"]["testable_sources"], 2)  # app.py + helper.py
        self.assertEqual(data["stats"]["test_files"], 1)  # tests/test_app.py
        app = next(f for f in data["files"] if f["file"] == "core/app.py")
        self.assertEqual(app["tests"], ["tests/test_app.py"])
        self.assertEqual(data["hotspots"][0]["file"], "util/helper.py")
        # 热区必须不含测试文件自身（tests/test_app.py）
        self.assertTrue(
            all(h["file"] != "tests/test_app.py" for h in data["hotspots"])
        )
        # README.md 虽改动 1 次，但不属于可测源码，不进热区
        self.assertTrue(all(h["file"] != "README.md" for h in data["hotspots"]))

        html_doc = html_path.read_text(encoding="utf-8")
        self.assertIn("bar-row", html_doc)
        self.assertIn("测试黑洞雷达", html_doc)

    def test_default_cwd_and_version_flag(self) -> None:
        self.make_busy_repo()
        # --version 通过 argparse 直接退出
        with contextlib.redirect_stdout(io.StringIO()):
            try:
                main(["--version"])
                self.fail("--version 应触发 SystemExit")
            except SystemExit as exc:
                self.assertEqual(exc.code, 0)

    def test_not_a_git_repo_friendly_error(self) -> None:
        plain = self._dir / "plain"
        plain.mkdir(parents=True, exist_ok=True)
        code, _, err = self.run_main(str(plain))
        self.assertEqual(code, 1)
        self.assertIn("不是 git 仓库", err)

    def test_top_zero_is_argument_error(self) -> None:
        self.make_busy_repo()
        code, _, err = self.run_main(str(self.repo), "--top", "0")
        self.assertEqual(code, 2)
        self.assertIn("--top", err)

    def test_empty_repo_runs_cleanly(self) -> None:
        # 空仓库（无提交）：退出码 0，不崩溃
        code, out, _ = self.run_main(str(self.repo))
        self.assertEqual(code, 0)
        self.assertIn("测试黑洞", out)


if __name__ == "__main__":
    unittest.main()