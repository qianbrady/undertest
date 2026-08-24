# undertest — Test Black-Hole Radar（测试黑洞雷达）

从 git 历史找出「高频改动 × 零直接测试」的源码文件，输出补测优先级清单。

纯 Python 标准库实现，零第三方依赖，纯本地离线运行，Windows / macOS / Linux 通用。

## 解决什么问题

代码库越改越乱，总有些文件被反复修改却没有任何测试兜底——它们就是「测试黑洞」：
- 改动越频繁，回归风险越高；
- 没有测试，出问题只能靠肉眼和运气。

undertest 用 `git log --numstat` 聚合每个源码文件的 **commit 次数** 与 **净增删行**，
按命名约定（`test_*.py` / `*_test.py` / `*.spec.js` / `*.test.js` / `tests/` / `__tests__/` 目录）
建立「源码文件 → 测试文件」映射，找出 **改动频繁却零直接测试** 的热点文件，
给出可直接执行的补测优先级 TOP-N 清单，并支持 JSON 导出与单文件 HTML 报告（内联 CSS + 条形图）。

## 安装

无需安装依赖（Python ≥ 3.10 即可，推荐 3.11+）：

```bash
# 方式一：在仓库根目录直接以包方式运行
python -m undertest --help

# 方式二：复制包目录到任意位置后，把父目录加入 PYTHONPATH
export PYTHONPATH=/path/to/project:$PYTHONPATH
python -m undertest --help
```

## 30 秒快速开始

```bash
# 对任意 git 仓库扫描，输出 TOP-20 测试黑洞
python -m undertest /path/to/your/repo

# 只看前 10 个，并导出全量 JSON 与 HTML 报告
python -m undertest /path/to/your/repo --top 10 --json churn.json --html report.html

# 在仓库目录内直接跑（默认当前目录）
cd /path/to/your/repo && python -m undertest
```

参数一览：

| 参数 | 说明 |
|---|---|
| `path`（位置参数） | git 仓库路径，默认当前目录 |
| `--top N` | 输出 TOP-N 个测试黑洞（默认 20）|
| `--json PATH` | 额外导出全量统计 JSON |
| `--html PATH` | 额外生成单文件 HTML 报告（内联 CSS + 条形图）|
| `--version` | 版本号 |

## 示例输出

```text
测试黑洞雷达 undertest v0.1.0
============================================================
仓库          : /repo
跟踪文件      : 42  (可测源码 31，测试文件 8)
有直接测试源码: 11  测试黑洞文件: 6

测试黑洞 TOP 20（高频改动 × 零直接测试）
#   Commits  增/删     净行   最近改动   源码文件
1   17       +890/-112  1002  2025-01-12  src/payment/checkout.py
2   14       +431/-63   494   2025-01-09  api/handlers/auth.py
3    9       +120/-30   150   2024-12-30  core/app.py
...
提示：--json PATH 导出全量数据；--html PATH 生成带条形图的报告；--top N 调整条数。
```

HTML 报告为单文件（全部 CSS/标记内联），可直接分享或挂到 CI artifact 上，
内含按 commit 次数归一化的横向条形图（见 `docs/action.md` 的无网络 GitHub Action 用法）。

## 工作原理

1. `git -C <repo> log --numstat --format=@@%H %ct` 读全历史，每提交每文件聚合：
   - `commits`：该文件被多少条提交触及（重命名 `old => new` 记旧路径零行改动 + 新路径一次改动；二进制记 0 行）；
   - `added / deleted`：净增删行；
   - `last_ts`：最近一次改动提交时间。
2. 命名约定识别测试文件（`test_*.py` / `*_test.py` / `*.spec.js` / `*.test.js`，
   支持 `.ts/.jsx/.tsx/.mjs/.cjs`；`tests/`、`__tests__/`、`test/` 目录按目录归属识别，
   排除 `__init__.py` / `conftest.py` / `fixtures.py` / `helpers.py` 等辅助文件）。
3. 双向建映射：从源码侧枚举测试候选路径，也从测试侧反推源码候选路径，
   只有仓库中真实存在的文件才算命中。
4. 热区 = 有 git 改动记录 + 属于可测源码（排除文档/配置/媒体/二进制与
   `node_modules` 等依赖目录）+ 无任何直接测试；排序：commit 次数降序 → 净行降序 → 路径字典序。

## 已知局限

- 映射基于**命名约定**启发式，非 AST 级精确匹配：`src/app.py` ↔ `tests/test_app.py`、
  `tests/` 下非命名约定的普通 `.py` 会被当成测试文件；对约定外的奇怪布局会漏报/误报；
- 只统计**被 git 跟踪过**的文件（未提交到历史的工作树文件不在统计范围）；
- 不做增量/缓存，全历史 `--numstat` 扫描在大仓库上可能较慢（可配合 `--top` 使用）；
- 依赖本机 `git` 命令（`git -C <path> ...`）。

## Roadmap

- [x] v0.1.0：churn 统计、命名约定映射、TOP-N 热区、`--json` / `--html`、GitHub Action 包装说明
- [ ] 增量扫描与子模块支持
- [ ] 按作者/日期窗口过滤（如只看最近 90 天）
- [ ] 更多语言测试命名约定（Go/Rust/Java 等）
- [ ] 与 GitHub API 对接时提供离线降级与 `--demo` 样例数据

## License

MIT，见 [LICENSE](LICENSE)。原创性说明：本项目的概念与具体实现为原创；
与 CodeScene/CodeClimate 等商业度量平台的差异是「可执行的补测优先级清单 + 开箱即用的零依赖 CLI/CI 包装」。