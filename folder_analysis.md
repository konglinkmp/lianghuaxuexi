# 文件夹内容分析与清理建议

## 1. `tools` 文件夹内容
该文件夹主要包含一些独立的 Python 脚本，用于市场数据分析、持仓检查和更新。

| 文件名 | 作用描述 |
| :--- | :--- |
| `analyze_held_stocks.py` | 分析当前持有的股票。 |
| `analyze_stock.py` | 分析特定股票。 |
| `check_holdings.py` | 检查当前的股票持仓情况。 |
| `check_requested_stocks.py` | 检查用户请求的股票。 |
| `get_spot_price.py` | 获取股票实时价格。 |
| `run_sensitivity_test.py` | 运行敏感性测试（可能与交易策略有关）。 |
| `update_holdings.py` | 更新持仓数据。 |

**必要性分析：**
这些脚本看起来是辅助工具，可能在日常运行、调试或手动数据维护时非常有用。**不建议随意删除**，除非你确定不再需要这些辅助功能。

---

## 2. `tests` 文件夹内容
该文件夹包含项目的自动化测试代码，分为单元测试（unit）和集成测试（integration）。

| 路径/文件名 | 作用描述 |
| :--- | :--- |
| `tests/unit/core/` | 核心逻辑测试，如 `test_technical_indicators.py`（技术指标测试）。 |
| `tests/unit/risk/` | 风险控制测试，如 `test_drawdown_controller.py`（回撤控制测试）。 |
| `tests/unit/strategy/` | 交易策略测试，如 `test_ai_risk.py`、`test_auction_filter.py`。 |
| `tests/integration/` | 集成测试，如 `test_real_ai.py`。 |
| 其他 `test_*.py` | 针对特定改进（如风险升级、风格漂移）的专项测试。 |

**必要性分析：**
这些测试文件对于保证代码质量和逻辑正确性至关重要。尤其是涉及量化交易和风险控制的逻辑，如果没有测试，修改代码时很容易引入隐藏 Bug。**强烈建议保留**。

---

## 结论与建议
- **不要删除 `tests`**：它是项目稳定性的保障。
- **谨慎处理 `tools`**：如果某些脚本确实从未使用过，可以考虑移动到备份目录或删除，但建议先确认它们是否在 `run_daily.sh` 或其他自动化流程中被调用。

你是否在使用某些特定的脚本，或者觉得哪些功能目前完全没在用？我可以帮你检查它们的调用关系。
