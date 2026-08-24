# Changelog

## v0.1.0 (2025-02)

首个可用的测试黑洞雷达 CLI：

- `git log --numstat` 聚合每个文件的 commit 次数、净增删行与最近改动时间；
  正确处理二进制（`- -`）、删除、重命名（`old => new`）、含空格文件名与空仓库；
- 命名约定测试文件识别与「源码 → 测试」双向映射（Python / JavaScript 系 + `tests/`、`__tests__/` 目录）；
- 「高频改动 × 零直接测试」热区排序，终端 TOP-N 表格（默认 20）；
- `--json` 全量导出与 `--html` 单文件报告（内联 CSS + 条形图）；
- 对非 git 目录 / `--top 0` 等给出友好报错与合理退出码（1 / 2）；
- `docs/action.md`：无网络 GitHub Action 包装说明（含 `action.yml` 示例与定时用法）；
- 全套 unittest（27 例），真实 git 夹具仓库（临时目录 init + 身份配置 + 多提交）验证。