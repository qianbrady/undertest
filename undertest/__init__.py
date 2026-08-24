"""undertest —— 测试黑洞雷达（Test Black-Hole Radar）。

从 git 历史（git log --numstat）统计每个源码文件的改动频率，
按命名约定建立「源码文件 -> 测试文件」映射，找出
“高频改动 × 零直接测试”的热点文件（测试黑洞），
输出终端 TOP-N 表格、JSON 导出与单文件 HTML 报告。

纯 Python 标准库实现，零第三方依赖。
"""

__version__ = "0.1.0"