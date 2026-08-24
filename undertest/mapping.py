"""mapping —— 测试文件识别与「源码文件 -> 测试文件」映射。

命名约定（按任务要求，并做少量务实扩展，细节见 README）：

- Python：``test_*.py`` / ``*_test.py``（同目录或同级 ``tests/`` 目录）
- JavaScript 系：``*.spec.js`` / ``*.test.js``（并支持 .ts/.jsx/.tsx/.mjs/.cjs）
- 目录约定：``tests/`` 与 ``__tests__/`` 目录下按命名约定/目录归属识别测试文件
"""

from __future__ import annotations

import re

from undertest.churn import FileChurn, is_testable_source

#: JavaScript 系可测扩展名（*_test.js / *.spec.js 约定的扩展集）
JS_EXTENSIONS = frozenset({".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs"})

#: 按“目录即测试”约定的目录名
TEST_DIR_NAMES = frozenset({"tests", "__tests__", "test"})

#: tests/ 目录下的辅助文件，不算测试本体
TEST_AUX_FILES = frozenset({"__init__.py", "conftest.py", "fixtures.py", "helpers.py"})

_SPEC_RE = re.compile(r"^(.+)\.(spec|test)\.(js|ts|jsx|tsx|mjs|cjs)$")


def is_test_file(rel: str) -> bool:
    """按命名约定判断一个仓库相对路径是否为测试文件。"""
    parts = rel.split("/")
    name = parts[-1]
    in_test_dir = any(p in TEST_DIR_NAMES for p in parts[:-1])
    if in_test_dir:
        if name in TEST_AUX_FILES:
            return False
        if name.endswith(".py") or _SPEC_RE.match(name):
            return True
    if name.startswith("test_") and name.endswith(".py"):
        return True
    if name.endswith("_test.py"):
        return True
    return bool(_SPEC_RE.match(name))


def _join(*parts: str) -> str:
    return "/".join(p for p in parts if p)


def _test_names_for_source(name: str) -> list[str]:
    """依据命名约定返回源码文件名对应的测试文件基名（不含目录）。"""
    dot = name.rfind(".")
    if dot <= 0:
        return []
    stem, ext = name[:dot], name[dot:]
    if ext == ".py":
        return [f"test_{name}", f"{stem}_test.py"]
    if ext in JS_EXTENSIONS:
        return [f"{stem}.spec{ext}", f"{stem}.test{ext}"]
    return []


def _source_basename(test_name: str) -> str | None:
    """从测试文件名反推源码基名：test_foo.py -> foo.py，foo.spec.js -> foo.js。"""
    if test_name.endswith("_test.py"):
        return test_name[: -len("_test.py")] + ".py"
    if test_name.startswith("test_") and test_name.endswith(".py"):
        return test_name[len("test_"):]
    m = _SPEC_RE.match(test_name)
    if m:
        return m.group(1) + m.group(3)
    return None


def test_candidates_for_source(rel: str) -> list[str]:
    """枚举源码文件可能的测试文件路径（候选，可能存在也可能不存在）。

    启发式规则（全部基于命名约定，存在性由调用方核对）：

    1. 同目录：``test_<name>`` / ``<stem>_test.py`` / ``<stem>.spec.<ext>`` 等；
    2. 同级 ``tests/`` 目录（按 basename）；
    3. 镜像：源码在子目录时 ``tests/<子目录>/test_<name>``；
    4. JS 系额外支持 ``__tests__/``（根级与镜像）。
    """
    parts = rel.split("/")
    name = parts[-1]
    base = _join(*parts[:-1])
    names = _test_names_for_source(name)
    if not names:
        return []
    cands: list[str] = []
    for n in names:  # 同目录
        cands.append(_join(base, n))
    for n in names:  # 同级 tests/（按 basename）
        cands.append(_join("tests", n))
    if base:  # 镜像到 tests/ 子目录
        for n in names:
            cands.append(_join("tests", base, n))
    if name.endswith(tuple(sorted(JS_EXTENSIONS))):  # JS 系：__tests__/ 约定
        for n in names:
            cands.append(_join("__tests__", n))
            if base:
                cands.append(_join("__tests__", base, n))
    return list(dict.fromkeys(cands))


def source_candidates_for_test(rel: str) -> list[str]:
    """从测试文件反推可能的源码路径（覆盖“测试在 tests/、源码在根或 src/”的常见布局）。"""
    parts = rel.split("/")
    name = parts[-1]
    base = _source_basename(name)
    if base is None:
        return []
    sdir = _join(*parts[:-1])
    cands = [_join(sdir, base), base, _join("src", base), _join("lib", base)]
    for i, p in enumerate(parts[:-1]):
        if p in TEST_DIR_NAMES:
            rest = parts[i + 1:-1]
            cands.append(_join(*rest, base))  # tests/pkg/test_x.py -> pkg/x.py
            break
    return list(dict.fromkeys(cands))


def build_mapping(all_rel: list[str]) -> dict[str, list[str]]:
    """建立 ``{源码相对路径: [测试文件相对路径, ...]}`` 映射。

    双向核对：既从源码侧枚举测试候选，也从测试侧反推源码候选，
    命中仓库实际存在的文件才算数。仅对“可测源码”建映射。
    """
    file_set = set(all_rel)
    test_files = {f for f in all_rel if is_test_file(f)}
    mapping: dict[str, list[str]] = {}

    # 正向：源码 -> 测试
    for src in all_rel:
        if is_test_file(src) or not is_testable_source(src):
            continue
        hits = sorted(t for t in test_files if t in test_candidates_for_source(src))
        if hits:
            mapping[src] = hits

    # 反向：测试 -> 源码（补齐 tests/ 风格布局）
    for t in test_files:
        for s in source_candidates_for_test(t):
            if s in file_set and not is_test_file(s) and is_testable_source(s):
                mapping.setdefault(s, [])
                if t not in mapping[s]:
                    mapping[s].append(t)

    for src in mapping:
        mapping[src] = sorted(set(mapping[src]))
    return mapping


def find_hotspots(
    churn: dict[str, FileChurn],
    mapping: dict[str, list[str]],
) -> list[FileChurn]:
    """计算热区：被 git 历史改动过、属于可测源码、本身不是测试文件、
    且没有任何直接测试的文件。

    排序：commit 次数降序 -> 净增删行降序 -> 路径字典序（保证稳定输出）。
    """
    candidates = [
        fc for path, fc in churn.items()
        if is_testable_source(path)
        and not is_test_file(path)
        and not mapping.get(path)
    ]
    return sorted(candidates, key=lambda fc: (-fc.commits, -fc.net, fc.path))