"""cli —— 命令行入口：argparse 参数解析 + 主流程编排。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from undertest import __version__
from undertest.churn import collect_churn, is_git_repo
from undertest.mapping import build_mapping, find_hotspots
from undertest.report import render_html, render_json, render_terminal, write_text


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="undertest",
        description=(
            "测试黑洞雷达：从 git 历史统计每个源码文件的改动频率，"
            "按命名约定建立「源码 -> 测试」映射，"
            "找出高频改动却零直接测试的热点文件（测试黑洞）。"
        ),
        epilog=(
            "示例：undertest ./myrepo --top 20 --json churn.json --html report.html\n"
            "纯 Python 标准库，零第三方依赖；全部数据仅来源于本地 git 历史。"
        ),
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="git 仓库路径（默认当前目录）",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        metavar="N",
        help="输出 TOP-N 个测试黑洞（默认 20）",
    )
    parser.add_argument(
        "--json",
        metavar="PATH",
        help="额外导出全量统计到 JSON 文件",
    )
    parser.add_argument(
        "--html",
        metavar="PATH",
        help="额外生成单文件 HTML 报告（内联 CSS + 条形图）",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"undertest {__version__}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI 主流程。返回进程退出码（0 成功 / 1 运行错误 / 2 参数错误）。"""
    args = build_parser().parse_args(argv)
    if args.top < 1:
        print("错误：--top 必须 >= 1", file=sys.stderr)
        return 2

    repo = Path(args.path).expanduser().resolve()
    if not is_git_repo(repo):
        print(
            f"错误：{repo} 不是 git 仓库根目录（或 git 命令不可用）。"
            "请指向仓库根路径，或先在该目录执行 git init。",
            file=sys.stderr,
        )
        return 1

    try:
        churn = collect_churn(repo)
    except RuntimeError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1

    mapping = build_mapping(list(churn))
    hotspots = find_hotspots(churn, mapping)

    print(render_terminal(repo, churn, mapping, hotspots, args.top))

    for flag, path in (("--json", args.json), ("--html", args.html)):
        if not path:
            continue
        out = Path(path).expanduser()
        try:
            if flag == "--json":
                write_text(out, render_json(repo, churn, mapping, hotspots))
            else:
                write_text(out, render_html(repo, churn, mapping, hotspots, args.top))
        except OSError as exc:
            print(f"错误：无法写入 {out}：{exc}", file=sys.stderr)
            return 1
        print(f"已导出 {flag.lstrip('-')} 报告 -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())