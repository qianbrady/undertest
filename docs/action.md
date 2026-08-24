# 用 GitHub Action 把 undertest 变成定时守卫

undertest 是纯本地单文件式 CLI（零依赖、零网络），可直接包成 GitHub Action，
在每次 push 或按 schedule 定时跑一遍，把「测试黑洞 TOP-N」HTML 报告作为 artifact 留存，
让补测优先级成为团队的成文约定。下面两种方式任选（都**不需要网络**，无需 pip/npm）。

---

## 方式 A：把 undertest 作为独立 Action 仓库发布（推荐）

建立一个独立仓库（例如 `your-org/undertest-action`），把本案的 `undertest/` 包目录与
下面的 `action.yml` 提交进去；在目标仓库使用时按 `uses: 你的用户名/undertest-action@v1` 引用。

### action.yml（置于 Action 仓库根目录）

```yaml
name: 'undertest'
description: '测试黑洞雷达：输出高频改动×零直接测试 的 TOP-N 清单与 HTML 报告（纯本地，零网络）'
author: 'undertest contributors'
inputs:
  top:
    description: '输出 TOP-N 个测试黑洞'
    required: false
    default: '20'
  json_path:
    description: 'JSON 导出路径（相对 runner workspace），空则不导出'
    required: false
    default: ''
  html_path:
    description: 'HTML 报告路径（相对 runner workspace）'
    required: false
    default: 'undertest-report.html'
outputs:
  hotspot_count:
    description: '发现的测试黑洞文件数量'
runs:
  using: 'composite'
  steps:
    - name: 运行 undertest
      shell: bash
      working-directory: ${{ github.workspace }}
      run: |
        python3 - <<'PY'
        import subprocess, sys
        from undertest.cli import main
        argv = ["${{ github.workspace }}", "--top", "${{ inputs.top }}"]
        if "${{ inputs.json_path }}" != "":
            argv += ["--json", "${{ inputs.json_path }}"]
        if "${{ inputs.html_path }}" != "":
            argv += ["--html", "${{ inputs.html_path }}"]
        sys.exit(main(argv))
        PY
        echo "hotspot_count=$?" >> "$GITHUB_OUTPUT"
```

## 方式 B：不发布 Action，直接在目标仓库的 workflow 里跑

把 `undertest/` 包目录复制进目标仓库（例如放在 `tools/undertest/`），然后在
`.github/workflows/undertest.yml` 中引用。

---

### 目标仓库的 workflow 示例（`.github/workflows/undertest.yml`）

```yaml
name: undertest-report

on:
  push:
    branches: [main]
  schedule:
    - cron: '0 3 * * 1'   # 每周一 03:00 定时扫描
  workflow_dispatch:      # 也支持手动触发

permissions:
  contents: read

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0            # 必须：undertest 需要完整 git 历史
      # 方式 A（已发布 Action）：
      - uses: your-org/undertest-action@v1
        with:
          top: '20'
          html_path: 'undertest-report.html'
          json_path: 'undertest-report.json'
      # —— 或 —— 方式 B（本地包）：
      # - name: 运行 undertest
      #   run: python3 -m undertest "$GITHUB_WORKSPACE" --top 20 \
      #          --json undertest-report.json --html undertest-report.html
      #   working-directory: tools/undertest
      - name: 上传报告为 artifact
        uses: actions/upload-artifact@v4
        with:
          name: undertest-report
          path: |
            undertest-report.html
            undertest-report.json
```

### 闭环建议

1. push 或每周定时触发扫描，报告按 artifact 留存（含 commit 数归一化的条形图 HTML，浏览器直接打开）；
2. 重点盯「最近 90 天内新增的热点」：凡是排在 TOP-N 且持续冒头的新源码文件，就是该补测的信号；
3. 补上测试后，该文件会从热区消失——用 `hotspot_count` 输出值做趋势线，让「黑洞收敛」可度量；
4. 可选：在 PR 检查里把 `hotspot_count > 阈值` 设为 warning（不阻断，仅提示），避免噪音化。

### 注意事项

- **必须 `fetch-depth: 0`**（浅克隆没有历史，undertest 会得到空结果）；
- 纯本地运行，无网络、无 token；未来如需对接 GitHub API（如按作者过滤），
  会遵循「无 token 时优雅降级」原则，默认仍走本地 git 历史；
- Python 版本：runner 自带 `python3`（ubuntu-latest 为 3.12+），无需 setup-python。