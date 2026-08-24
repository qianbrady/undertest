"""churn —— 从 git 历史聚合每个文件的改动频率（commit 次数与净增删行）。

数据源：`git log --numstat --format=@@%H %ct`（命令输出按提交分块，
每块以 @@<hash> <unix-ts> 开头，其后逐行是 `加\t删\t路径`）。
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

#: git log 每块提交记录的起始标记（自定义 --format 前缀）
COMMIT_MARKER = "@@"

#: 花括号压缩形式的重命名行：lib/{alpha.py => beta.py}suffix
_RENAME_BRACE_RE = re.compile(r"^(.*)\{(.*) => (.*)\}(.*)$")

#: 跳过这些目录里的文件（生成物 / 依赖 / 元数据，不参与统计）
NON_SOURCE_DIRS = frozenset({
    "node_modules", "dist", "build", "vendor", "target", "out",
    ".git", "__pycache__", ".venv", "venv", "coverage", ".idea", ".vscode",
})

#: 这些扩展名的文件不参与“补测优先级”判定（媒体 / 二进制 / 文档 / 配置）
NON_TESTABLE_EXTS = frozenset({
    # 图片 / 字体
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".bmp", ".webp",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    # 压缩包 / 媒体
    ".zip", ".gz", ".tar", ".7z", ".rar", ".xz", ".bz2",
    ".mp3", ".mp4", ".wav", ".ogg", ".mov", ".avi", ".webm",
    # 编译产物 / 二进制
    ".pyc", ".pyo", ".class", ".o", ".so", ".dll", ".exe", ".dylib",
    ".bin", ".map", ".lock",
    # 文档 / 配置（改动再频繁也不需要补测）
    ".md", ".markdown", ".txt", ".rst", ".adoc",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
})

#: 无扩展名 / 点文件形态的非源码文件名（工具文件、许可、说明等，不进热区）
NON_TESTABLE_BASENAMES = frozenset({
    "license", "copying", "authors", "notice", "changelog", "readme",
    ".gitignore", ".gitattributes", ".gitmodules", ".dockerignore",
    ".editorconfig",
    "dockerfile", "procfile", "gemfile", "rakefile", "makefile",
    "justfile", "taskfile",
})


@dataclass
class FileChurn:
    """单个文件在 git 历史中的改动统计（路径为仓库相对路径，/ 分隔）。"""

    path: str
    commits: int = 0
    added: int = 0
    deleted: int = 0
    last_ts: int = 0

    @property
    def net(self) -> int:
        """净增删行（added + deleted）。"""
        return self.added + self.deleted


def run_git(repo: Path, *args: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    """在指定仓库内执行 git 命令（跨平台：git -C <path>）。

    ``-c core.quotepath=false`` 关闭非 ASCII 文件名的八进制转义，
    保证中文/emoji 文件名在统计中按原样保留。超时（默认 120s，
    极端大仓库保护）时抛 RuntimeError，由上层转为友好报错。
    """
    try:
        return subprocess.run(
            ["git", "-c", "core.quotepath=false", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"git 命令超时（>{timeout}s）：{args[0] if args else '?'}") from exc


def is_git_repo(repo: Path) -> bool:
    """判断路径本身是否为 git 仓库根（目录等于 `git rev-parse --show-toplevel`）。

    要求「目录本身是仓库根」而非「在某个仓库工作树内」，
    避免对仓库内子目录给出误导性结果（对非 git 目录友好返回 False 而非崩溃）。
    """
    if not repo.exists() or not repo.is_dir():
        return False
    proc = run_git(repo, "rev-parse", "--show-toplevel")
    if proc.returncode != 0:
        return False
    top = proc.stdout.strip()
    if not top:
        return False
    try:
        return Path(top).resolve() == repo.resolve()
    except OSError:
        return False


def is_testable_source(rel: str) -> bool:
    """判断相对路径是否属于“可测源码”（排除依赖目录、文档/媒体/配置类与工具文件）。"""
    parts = rel.split("/")
    if any(p in NON_SOURCE_DIRS for p in parts):
        return False
    name = parts[-1]
    if name.lower() in NON_TESTABLE_BASENAMES:
        return False
    dot = name.rfind(".")
    ext = name[dot:].lower() if dot >= 0 else ""
    return ext not in NON_TESTABLE_EXTS


def _bump(
    stats: dict[str, FileChurn],
    path: str,
    added: int,
    deleted: int,
    ts: int,
) -> None:
    entry = stats.get(path)
    if entry is None:
        entry = stats[path] = FileChurn(path=path)
    entry.commits += 1
    entry.added += added
    entry.deleted += deleted
    if ts > entry.last_ts:
        entry.last_ts = ts


def collect_churn(repo: Path) -> dict[str, FileChurn]:
    """聚合仓库全历史中每个文件的 commit 次数与净增删行。

    返回 ``{相对路径: FileChurn}``；空仓库（无任何提交）返回空字典。
    对二进制文件（numstat 记 ``-``）计为 0 行；重命名（``old => new``）
    拆成旧路径零行改动 + 新路径一次改动。
    """
    proc = run_git(repo, "log", "--numstat", "--format=" + COMMIT_MARKER + "%H %ct")
    if proc.returncode != 0:
        err = proc.stderr.lower()
        if (
            "does not have any commits" in err
            or "unknown revision" in err
            or "bad default revision" in err
        ):
            return {}
        raise RuntimeError(f"git log 失败：{proc.stderr.strip() or 'git 不可用'}")

    stats: dict[str, FileChurn] = {}
    current_ts = 0
    for raw in proc.stdout.splitlines():
        if raw.startswith(COMMIT_MARKER):
            rest = raw[len(COMMIT_MARKER):].split()
            if len(rest) >= 2 and rest[1].isdigit():
                current_ts = int(rest[1])
            continue
        if not raw.strip():
            continue
        parts = raw.split("\t")
        if len(parts) < 3:
            continue
        added_s, deleted_s = parts[0], parts[1]
        # 文件名里可能含制表符：git 以字面 \t 转义，用 join 保持原样
        name = "\t".join(parts[2:])
        added = int(added_s) if added_s.lstrip("-").isdigit() else 0
        deleted = int(deleted_s) if deleted_s.lstrip("-").isdigit() else 0
        if " => " in name:
            # 重命名有两种输出形式：
            #   全路径形式：  legacy.py => modern.py
            #   花括号压缩：  lib/{alpha.py => beta.py}（同目录/共享前后缀时）
            m = _RENAME_BRACE_RE.match(name)
            if m:
                prefix, old_tail, new_tail, suffix = m.groups()
                old = (prefix + old_tail + suffix).strip()
                new = (prefix + new_tail + suffix).strip()
            else:
                old, new = name.rsplit(" => ", 1)
                old, new = old.strip(), new.strip()
            _bump(stats, old, 0, 0, current_ts)
            _bump(stats, new, added, deleted, current_ts)
        else:
            _bump(stats, name, added, deleted, current_ts)
    return stats