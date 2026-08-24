"""report —— 终端表格、JSON 导出与单文件 HTML 报告的渲染。"""

from __future__ import annotations

import html
import json
import time
from pathlib import Path

from undertest import __version__
from undertest.churn import FileChurn, is_testable_source
from undertest.mapping import find_hotspots, is_test_file


def _fmt_ts(ts: int) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(ts)) if ts > 0 else "-"


def _table(headers: list[str], rows: list[list[str]]) -> str:
    """渲染对齐的纯文本表格（宽度按内容自适应）。"""
    widths = [
        max(
            len(str(headers[i])),
            *(len(r[i]) for r in rows),
        )
        for i in range(len(headers))
    ]
    fmt = "  ".join("{:<%d}" % w for w in widths)
    sep = "  ".join("-" * w for w in widths)
    lines = [fmt.format(*headers), sep]
    lines += [fmt.format(*r) for r in rows]
    return "\n".join(lines)


def summarize(
    repo: Path,
    churn: dict[str, FileChurn],
    mapping: dict[str, list[str]],
) -> dict[str, object]:
    """汇总统计信息（终端摘要与报告共用）。"""
    return {
        "repo": str(repo),
        "tracked_files": len(churn),
        "testable_sources": sum(
            1 for p in churn if not is_test_file(p) and is_testable_source(p)
        ),
        "test_files": sum(1 for p in churn if is_test_file(p)),
        "sources_with_tests": len(mapping),
    }


def render_terminal(
    repo: Path,
    churn: dict[str, FileChurn],
    mapping: dict[str, list[str]],
    hotspots: list[FileChurn],
    top: int,
) -> str:
    """渲染终端 TOP-N 热区表格与摘要。"""
    summary = summarize(repo, churn, mapping)
    out: list[str] = []
    out.append(f"测试黑洞雷达 undertest v{__version__}")
    out.append("=" * 60)
    out.append(f"仓库          : {summary['repo']}")
    out.append(
        f"跟踪文件      : {summary['tracked_files']}  "
        f"(可测源码 {summary['testable_sources']}，测试文件 {summary['test_files']})"
    )
    out.append(
        f"有直接测试源码: {summary['sources_with_tests']}  "
        f"测试黑洞文件: {len(hotspots)}"
    )
    out.append("")
    shown = hotspots[:top]
    out.append(f"测试黑洞 TOP {len(shown)}（高频改动 × 零直接测试）")
    headers = ["#", "Commits", "增/删", "净行", "最近改动", "源码文件"]
    rows = [
        [
            str(i),
            str(fc.commits),
            f"+{fc.added}/-{fc.deleted}",
            str(fc.net),
            _fmt_ts(fc.last_ts),
            fc.path,
        ]
        for i, fc in enumerate(shown, 1)
    ]
    if rows:
        out.append(_table(headers, rows))
    else:
        out.append("（无：仓库中不存在“改动频繁却无测试”的源码文件，做得好！）")
    out.append("")
    out.append("提示：--json PATH 导出全量数据；--html PATH 生成带条形图的报告；--top N 调整条数。")
    return "\n".join(out)


def render_json(
    repo: Path,
    churn: dict[str, FileChurn],
    mapping: dict[str, list[str]],
    hotspots: list[FileChurn],
) -> str:
    """渲染 JSON 报文（全量数据，便于下游消费）。"""
    files = sorted(churn.values(), key=lambda fc: (-fc.commits, -fc.net, fc.path))
    payload = {
        "tool": "undertest",
        "version": __version__,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "repo": str(repo),
        "stats": summarize(repo, churn, mapping)
        | {"hotspot_count": len(hotspots), "hotspot_top": len(hotspots)},
        "hotspots": [
            {
                "file": fc.path,
                "commits": fc.commits,
                "added": fc.added,
                "deleted": fc.deleted,
                "net_lines": fc.net,
                "last_commit_ts": fc.last_ts,
            }
            for fc in hotspots
        ],
        "files": [
            {
                "file": fc.path,
                "commits": fc.commits,
                "added": fc.added,
                "deleted": fc.deleted,
                "net_lines": fc.net,
                "last_commit_ts": fc.last_ts,
                "tests": sorted(mapping.get(fc.path, [])),
                "is_test_file": is_test_file(fc.path),
            }
            for fc in files
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _bar_rows(hotspots: list[FileChurn], top: int) -> list[str]:
    """生成 HTML 条形图行（宽度按 commit 次数相对最大值归一化）。"""
    shown = hotspots[:top]
    if not shown:
        return ["<p class='empty'>没有发现测试黑洞。</p>"]
    max_commits = max(fc.commits for fc in shown) or 1
    rows = []
    for fc in shown:
        pct = fc.commits / max_commits * 100.0
        rows.append(
            f'<div class="bar-row">'
            f'<span class="bar-label" title="{html.escape(fc.path)}">{html.escape(fc.path)}</span>'
            f'<span class="bar-track"><span class="bar" style="width:{pct:.1f}%"></span></span>'
            f'<span class="bar-n">{fc.commits}</span>'
            f"</div>"
        )
    return rows


def render_html(
    repo: Path,
    churn: dict[str, FileChurn],
    mapping: dict[str, list[str]],
    hotspots: list[FileChurn],
    top: int,
) -> str:
    """渲染单文件 HTML 报告（内联 CSS，含简单条形图）。"""
    summary = summarize(repo, churn, mapping)
    summary["hotspot_count"] = len(hotspots)
    shown = hotspots[:top]
    hot_rows = [
        f"<tr><td>{i}</td><td class='f'>{html.escape(fc.path)}</td>"
        f"<td>{fc.commits}</td><td>+{fc.added}/-{fc.deleted}</td>"
        f"<td>{fc.net}</td><td>{_fmt_ts(fc.last_ts)}</td></tr>"
        for i, fc in enumerate(shown, 1)
    ]
    hot_table = "\n".join(hot_rows) if hot_rows else (
        "<tr><td colspan='6' class='empty'>没有发现测试黑洞。</td></tr>"
    )
    bars = "\n".join(_bar_rows(hotspots, top))
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>测试黑洞雷达 · {html.escape(summary["repo"])}</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font-family: "Segoe UI", "Microsoft YaHei", system-ui, sans-serif;
         max-width: 960px; margin: 2rem auto; padding: 0 1rem; line-height: 1.6; }}
  h1 {{ margin-bottom: .2rem; }}
  .sub {{ color: #888; font-size: .9rem; }}
  .chips {{ display: flex; gap: 1rem; flex-wrap: wrap; margin: 1rem 0; }}
  .chip {{ background: #f0f0f0; border-radius: 8px; padding: .5rem 1rem; font-size: .85rem; }}
  .chip b {{ display: block; font-size: 1.3rem; }}
  .chip.hot b {{ color: #c0392b; }}
  h2 {{ margin-top: 1.6rem; font-size: 1.15rem; }}
  .bar-row {{ display: flex; align-items: center; gap: .6rem; margin: .35rem 0; }}
  .bar-label {{ flex: 0 0 42%; white-space: nowrap; overflow: hidden;
                text-overflow: ellipsis; font-family: Consolas, monospace; font-size: .8rem; }}
  .bar-track {{ flex: 1; background: #ececec; border-radius: 4px; height: 16px; overflow: hidden; }}
  .bar {{ display: block; height: 100%; background: linear-gradient(90deg,#e74c3c,#c0392b);
          border-radius: 4px; min-width: 2px; }}
  .bar-n {{ flex: 0 0 2.5rem; text-align: right; font-family: Consolas, monospace; font-size: .8rem; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: .5rem; font-size: .85rem; }}
  th, td {{ border-bottom: 1px solid #ddd; padding: .4rem .6rem; text-align: left; }}
  th {{ background: #f7f7f7; }}
  td.f {{ font-family: Consolas, monospace; }}
  .empty {{ color: #27ae60; }}
  footer {{ margin-top: 2rem; color: #aaa; font-size: .8rem; }}
  @media (prefers-color-scheme: dark) {{
    .chip {{ background: #2a2a2a; }} .bar-track {{ background: #333; }}
    th {{ background: #2a2a2a; }} th, td {{ border-color: #444; }}
  }}
</style>
</head>
<body>
<h1>🕳️ 测试黑洞雷达</h1>
<div class="sub">undertest v{__version__} · {html.escape(summary["repo"])} ·
生成于 {time.strftime("%Y-%m-%d %H:%M:%S")}</div>
<div class="chips">
  <div class="chip"><b>{summary["tracked_files"]}</b>跟踪文件</div>
  <div class="chip"><b>{summary["testable_sources"]}</b>可测源码</div>
  <div class="chip"><b>{summary["test_files"]}</b>测试文件</div>
  <div class="chip"><b>{summary["sources_with_tests"]}</b>有测试的源码</div>
  <div class="chip hot"><b>{summary["hotspot_count"]}</b>测试黑洞</div>
</div>
<h2>高频改动 × 零直接测试（TOP {len(shown)}）</h2>
<div class="bars">{bars}</div>
<h2>测试黑洞明细</h2>
<table>
  <thead><tr><th>#</th><th>源码文件</th><th>Commits</th><th>增/删</th><th>净行</th><th>最近改动</th></tr></thead>
  <tbody>{hot_table}</tbody>
</table>
<footer>由 undertest（纯 Python 标准库，零依赖）离线生成。</footer>
</body>
</html>"""


def write_text(path: Path, content: str) -> None:
    """写文件（失败向上抛 OSError，由 CLI 层转成友好报错）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")