"""churn 统计测试：真实 git 夹具仓库验证 commit 次数与净增删行聚合。"""

from __future__ import annotations

import unittest

from tests.helpers import GitFixtureTestMixin, commit_all, git, write_file
from undertest.churn import (
    collect_churn,
    is_git_repo,
    is_testable_source,
    run_git,
)


class ChurnBasicTest(GitFixtureTestMixin, unittest.TestCase):
    """正常路径：多提交聚合 commit 次数与增删行。"""

    def test_aggregates_commits_and_lines(self) -> None:
        write_file(self.repo, "src/app.py", "a\nb\nc\n")
        commit_all(self.repo, "c1")
        write_file(self.repo, "src/app.py", "a\nb\nc\nd\n")
        commit_all(self.repo, "c2")
        write_file(self.repo, "src/util.py", "x\n")
        commit_all(self.repo, "c3")

        churn = collect_churn(self.repo)
        app = churn["src/app.py"]
        util = churn["src/util.py"]

        self.assertEqual(app.commits, 2)
        self.assertEqual(app.added, 4)  # c1 加 3 行 + c2 加 1 行
        self.assertEqual(app.deleted, 0)
        self.assertEqual(app.net, 4)
        self.assertEqual(util.commits, 1)
        self.assertEqual(util.added, 1)
        self.assertGreater(app.last_ts, 0)  # 记录了最近提交时间
        self.assertTrue(is_git_repo(self.repo))


class ChurnEdgeTest(GitFixtureTestMixin, unittest.TestCase):
    """边界情况：二进制、删除、重命名、空格文件名。"""

    def test_binary_delete_rename_space(self) -> None:
        # 二进制文件：numstat 记为 "-	-" → 计 0 行
        write_file(self.repo, "data.bin", "ab\x00cd")
        commit_all(self.repo, "c1")
        # 文件重命名为新文件名
        git(self.repo, "mv", "data.bin", "data2.bin")
        commit_all(self.repo, "c2")
        # 删除一个文本文件
        write_file(self.repo, "tmp.txt", "1\n2\n")
        commit_all(self.repo, "c3")
        git(self.repo, "rm", "-q", "tmp.txt")
        commit_all(self.repo, "c4")
        # 文件名含空格
        write_file(self.repo, "my file.py", "x\n")
        commit_all(self.repo, "c5")

        churn = collect_churn(self.repo)
        # 二进制：1 次 commit（创建），重命名又计 1 次 -> 共 2 次，行数为 0
        self.assertEqual(churn["data.bin"].commits, 2)
        self.assertEqual(churn["data.bin"].added, 0)
        # 重命名：旧路径零行改动 +1 次，新路径 +1 次
        self.assertEqual(churn["data2.bin"].commits, 1)
        self.assertEqual(churn["data2.bin"].added, 0)
        # 删除：创建 + 删除各计一次改动（git 记 deleted 行数）
        self.assertEqual(churn["tmp.txt"].commits, 2)
        self.assertGreaterEqual(churn["tmp.txt"].deleted, 2)
        # 空格文件名完全保留
        self.assertEqual(churn["my file.py"].commits, 1)
        self.assertEqual(churn["my file.py"].added, 1)

    def test_empty_repo_no_commits(self) -> None:
        # 空仓库（无提交）：不崩溃，返回空字典
        self.assertEqual(collect_churn(self.repo), {})
        self.assertEqual(collect_churn(self.repo), {})

    def test_non_repo_dir(self) -> None:
        # plain 目录没有自己的 .git（父级有仓库，但本身不是仓库根）
        plain = self._dir / "plain"
        plain.mkdir(parents=True, exist_ok=True)
        self.assertFalse(is_git_repo(plain))
        # 不存在的路径
        self.assertFalse(is_git_repo(self._dir / "nope"))
        # 仓库内子目录也不是仓库根
        sub = self.repo / "src"
        sub.mkdir(parents=True, exist_ok=True)
        self.assertFalse(is_git_repo(sub))
        # 仓库根本身是
        self.assertTrue(is_git_repo(self.repo))

    def test_run_git_returns_process(self) -> None:
        proc = run_git(self.repo, "rev-parse", "--is-inside-work-tree")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "true")


class SourceFilterTest(unittest.TestCase):
    """扩展名 / 目录过滤（热区只针对可测源码）。"""

    def test_is_testable_source(self) -> None:
        self.assertTrue(is_testable_source("src/app.py"))
        self.assertTrue(is_testable_source("Makefile"))  # 无扩展名也算源码
        self.assertFalse(is_testable_source("README.md"))  # 文档不算
        self.assertFalse(is_testable_source("package.json"))  # 配置不算
        self.assertFalse(is_testable_source("node_modules/lodash/index.js"))
        self.assertFalse(is_testable_source("dist/bundle.js"))
        self.assertFalse(is_testable_source("__pycache__/x.pyc"))
        self.assertFalse(is_testable_source("assets/logo.png"))
        self.assertTrue(is_testable_source("pkg/sub/mod.ts"))


if __name__ == "__main__":
    unittest.main()