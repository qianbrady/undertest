"""测试公共工具：在工作区内构造真实 git 夹具仓库。

沙箱限制下系统临时目录不可写，夹具一律放在项目根 `.tmp_fixtures/`
（已加入 .gitignore，不会进入提交）。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

#: 项目根（tests/helpers.py 的上两级）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
#: 夹具仓库基目录（工作区内，保证可写、可被 git 忽略）
FIXTURE_BASE = PROJECT_ROOT / ".tmp_fixtures"


def git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """在仓库内执行 git 命令；失败即抛。"""
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def make_repo(base: Path) -> Path:
    """git init + 本地身份配置（user.name=builder / user.email=builder@example.com）。"""
    repo = base / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    git(repo, "init", "-q")
    git(repo, "config", "user.name", "builder")
    git(repo, "config", "user.email", "builder@example.com")
    git(repo, "config", "core.autocrlf", "false")
    git(repo, "config", "commit.gpgsign", "false")
    return repo


def write_file(repo: Path, rel: str, content: str) -> Path:
    """按字节写入文件（避开 Windows 文本模式的换行转换，保证行数确定）。"""
    target = repo / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content.encode("utf-8"))
    return target


def commit_all(repo: Path, message: str) -> None:
    """git add -A && git commit。"""
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)


class GitFixtureTestMixin:
    """unittest mixin：setUp/tearDown 提供真实 git 夹具仓库。"""

    def setUp(self) -> None:  # noqa: N802（unittest 命名）
        FIXTURE_BASE.mkdir(parents=True, exist_ok=True)
        # 不用 tempfile（mkdtemp 目录在沙箱下被拒写），
        # 用 pid+纳秒时间戳生成唯一目录
        self._dir = FIXTURE_BASE / f"fixture_{os.getpid()}_{time.time_ns()}"
        self._dir.mkdir(parents=True, exist_ok=False)
        self.repo = make_repo(self._dir)

    def tearDown(self) -> None:  # noqa: N802
        shutil.rmtree(self._dir, ignore_errors=True)