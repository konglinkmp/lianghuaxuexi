# 📈 A股量化交易决策辅助工具

一个基于 Python 的 A 股量化交易决策辅助系统，帮助你筛选股票、生成交易计划、回测策略效果。

✨ **核心功能**：
- 🎯 **分层策略**：稳健层（20%）+ 激进层（80%），差异化风控
- 🛡️ **智能风控**：分级回撤控制、月度回撤管理、AI 新闻风险分析
- 📊 **专业回测**：含幸存者偏差警告、参数敏感性测试
- 📱 **消息推送**：支持 Bark、钉钉、企业微信

---

## 🆕 首次使用（新人必读）

### 第一步：克隆项目并安装依赖

```bash
# 1. 克隆代码仓库
git clone <your-repo-url> ~/workspace/量化
cd ~/workspace/量化

# 2. 创建虚拟环境（推荐 Python 3.11+）
python3 -m venv venv

# 3. 激活虚拟环境
source venv/bin/activate

# 4. 安装依赖
pip install -r requirements.txt

# 5. 验证安装是否成功
PYTHONPATH=src python -c "import quant; print('✅ 安装成功！')"
```

### 第二步：首次运行

```bash
# 激活环境（每次使用前都要执行）
source venv/bin/activate

# 运行主程序（生成明日交易计划）
PYTHONPATH=src python -m quant.main --ignore-holdings

# 查看生成的交易计划
open data/trading_plan.csv  # Mac
# 或
cat data/trading_plan.csv   # 命令行查看
```

### 第三步：配置你的资金和持仓（可选）

```bash
# 编辑 update_holdings.py，填入你的资金和持仓
# 然后运行：
python update_holdings.py
```

---

## 🚀 日常使用

---

## 📋 功能一览

| 功能 | 说明 | 命令 |
|------|------|------|
| 生成交易计划 | 筛选明日可买入的股票 | `PYTHONPATH=src python -m quant.main` |
| 竞价过滤 | 开盘前过滤跳空计划 | `PYTHONPATH=src python -m quant.main --auction-only` |
| 回测策略 | 验证策略历史表现 | `PYTHONPATH=src python -m quant.backtester` |
| 单股回测 | 测试某只股票的策略效果 | 见下方示例 |
| 持仓管理 | 记录和跟踪持仓 | 见下方示例 |
| 可视化报告 | 生成回测图表 | 见下方示例 |

---

## 🎯 使用场景

### 场景一：明天我应该买什么股票？

#### 方法1：全A股扫描（推荐新手）

```bash
# 激活环境
source venv/bin/activate

# 运行主程序（默认使用分层策略）
PYTHONPATH=src python -m quant.main

# 可选：禁用分层策略，使用传统单层模式
PYTHONPATH=src python -m quant.main --no-layer

# 可选：禁用自适应参数
PYTHONPATH=src python -m quant.main --no-adaptive
```

**输出结果（分层策略）：**
```
📊 共筛选出 8 只股票（稳健层 5 + 激进层 3）

💰 稳健层（价值趋势策略）
    止损: -5% | 止盈: +15%
    【稳1】江河集团 - 价值趋势股

🚀 激进层（热门资金策略）
    止损: -8% | 止盈: +25%
    【激1】天力复合 - 热门资金股
```

- 终端显示分层推荐股票
- 自动保存到 `data/trading_plan.csv` 文件（含风格基准权重、板块强度、行业/概念信息）

**查看结果：**
```bash
# 用 Excel 或 Numbers 打开
open data/trading_plan.csv

# 或用命令行查看
cat data/trading_plan.csv
```

#### 方法2：只分析我自选的股票

1. **编辑 `data/myshare.txt`**，每行一个股票代码：
   ```
   000001
   600036
   002352
   601212
   ```

2. **运行程序**：
   ```bash
   PYTHONPATH=src python -m quant.main --custom
   ```

#### 方法3：快速测试（只分析前100只）

```bash
PYTHONPATH=src python -m quant.main --limit 100
```

---

### 场景二：测试某只股票的历史策略效果

想知道某只股票用这个策略在过去一年表现如何？

```bash
source venv/bin/activate

PYTHONPATH=src python -c "
from quant.backtester import backtest_stock, BacktestResult, print_backtest_report

# 修改这里的股票代码和名称
trades = backtest_stock('002352', '顺丰控股', use_trailing_stop=True)

if trades:
    result = BacktestResult()
    for trade in trades:
        result.add_trade(trade)
    
    # 显示详细交易记录
    print('📋 交易记录:')
    for t in trades:
        pnl_pct = t.get('pnl_pct', 0) * 100
        emoji = '🟢' if pnl_pct > 0 else '🔴'
        print(f'{emoji} {t[\"entry_date\"].strftime(\"%Y-%m-%d\")} 买入¥{t[\"entry_price\"]:.2f} → {t[\"exit_date\"].strftime(\"%Y-%m-%d\")} 卖出¥{t[\"exit_price\"]:.2f} | {t[\"exit_reason\"]} | {pnl_pct:+.2f}%')
    
    print()
    print_backtest_report(result)
else:
    print('无交易记录')
"
```

---

### 场景三：回测我的自选股

```bash
# 确保 data/myshare.txt 中有你的股票代码
PYTHONPATH=src python -m quant.backtester

# 可选：输出专业风险报告
PYTHONPATH=src python -m quant.backtester --risk-report
```

**输出：**
- 胜率、盈亏比、最大回撤等指标
- 最近10笔交易记录

---

### 场景四：生成可视化回测报告

```bash
PYTHONPATH=src python -c "
from quant.backtester import backtest_stock
from quant.visualizer import plot_performance_report

# 收集多只股票的交易数据
trades = []
stocks = [('000001', '平安银行'), ('600036', '招商银行'), ('002352', '顺丰控股')]

for code, name in stocks:
    trades += backtest_stock(code, name)

# 生成可视化报告
plot_performance_report(trades, 'outputs/my_report.png')
print('报告已生成: outputs/my_report.png')
"

# 打开报告图片
open outputs/my_report.png
```

---

### 场景五：记录我买入的股票（持仓跟踪）

#### 添加持仓

```bash
PYTHONPATH=src python -c "
from quant.position_tracker import position_tracker

# 添加持仓（代码、名称、买入价、股数、止损价、止盈价、行业）
position_tracker.add_position(
    '002352',           # 股票代码
    '顺丰控股',          # 名称
    42.50,              # 买入价
    1000,               # 股数
    40.38,              # 止损价
    48.88,              # 止盈价
    '物流'              # 行业
)

# 查看当前持仓
position_tracker.print_positions()
"
```

#### 查看所有持仓

```bash
PYTHONPATH=src python -c "
from quant.position_tracker import position_tracker
position_tracker.print_positions()
"
```

#### 卖出股票

```bash
PYTHONPATH=src python -c "
from quant.position_tracker import position_tracker

# 卖出（代码、卖出价、原因）
trade = position_tracker.remove_position('002352', 48.50, '止盈')
if trade:
    print(f'盈亏: ¥{trade[\"pnl\"]:.2f} ({trade[\"pnl_pct\"]:+.2f}%)')
"
```

---

### 场景六：检查今天能不能交易（回撤控制）

```bash
PYTHONPATH=src python -c "
from quant.drawdown_controller import drawdown_controller

# 更新当前资金（根据实际情况修改）
can_trade, msg = drawdown_controller.update_capital(95000)
print(msg)

# 查看详细状态
drawdown_controller.print_status()
"
```

也可以使用净值文件让主程序自动读取：

示例文件（`data/account_status.json`）：

```json
{
  "current_capital": 95000,
  "as_of": "2026-01-06"
}
```

---

### 场景六点五：竞价过滤（开盘前过滤跳空）

```bash
PYTHONPATH=src python -c "
import akshare as ak
import pandas as pd
from quant.auction_filter import apply_auction_filters

plan = pd.read_csv('data/trading_plan.csv')
snapshot = ak.stock_zh_a_spot_em()  # 9:15~9:25 期间运行

keep_df, cancel_df = apply_auction_filters(plan, snapshot)
keep_df.to_csv('data/trading_plan_auction.csv', index=False, encoding='utf-8-sig')

print('保留数量:', len(keep_df), '取消数量:', len(cancel_df))
"
```

或直接使用主程序参数：

```bash
PYTHONPATH=src python -m quant.main --auction-only
```

说明：`--auction-only` 会在过滤后直接推送保留计划（需已配置通知）。

---

### 场景七：配置消息推送（钉钉/微信）

1. 编辑 `config/notification_config.json`

2. 示例（钉钉机器人）：
   ```json
   {
     "enabled": true,
     "channels": {
       "dingtalk": {
         "enabled": true,
         "webhook": "https://oapi.dingtalk.com/robot/send?access_token=你的token",
         "secret": "你的密钥"
       }
     }
   }
   ```

3. 测试推送：
   ```bash
   PYTHONPATH=src python -c "
   from quant.notifier import notification_manager
   notification_manager.send_all('测试', '这是一条测试消息')
   "
   ```

---

### 场景八：辅助工具（快速诊断）

为了方便日常快速查看，项目中提供了多个独立的辅助工具：

#### 1. 持仓快速扫描器
一键查看当前所有持仓的技术面趋势（是否在 MA20 之上）。
```bash
python tools/check_holdings.py
```

#### 2. 个股深度诊断器
对任意指定的股票进行深度技术面+基本面分析。
```bash
python tools/analyze_stock.py 000547
```

#### 3. 参数敏感性测试（新增）
测试策略参数的稳定性，识别过拟合风险。
```bash
# 快速模式（9组参数组合）
python tools/run_sensitivity_test.py --quick --limit 5

# 完整模式（135组参数组合）
python tools/run_sensitivity_test.py --limit 10 --output outputs/sensitivity.csv
```

输出示例：
```
🟢 参数稳定性: 75.2/100 - ✅ 高 (策略稳定)

🏆 最佳参数组合:
   - MA_SHORT: 20
   - STOP_LOSS_RATIO: 0.05
```

---

## ⚙️ 配置说明

所有配置都在 `config/config.py` 文件中：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `STOP_LOSS_RATIO` | 0.05 | 止损比例（5%） |
| `TAKE_PROFIT_RATIO` | 0.15 | 止盈比例（15%） |
| `TRAILING_STOP_RATIO` | 0.08 | 移动止盈回撤（8%） |
| `MA_SHORT` | 20 | 短期均线周期 |
| `MA_LONG` | 60 | 长期均线周期 |
| `VOLUME_RATIO_THRESHOLD` | 1.2 | 放量倍数阈值 |
| `MAX_POSITIONS` | 10 | 最大持仓数量 |
| `MAX_SECTOR_POSITIONS` | 3 | 同行业最大持仓 |
| `TOTAL_CAPITAL` | 64248 | 总资金（用于计算仓位） |
| `POSITION_RATIO` | 0.10 | 单笔仓位比例（10%） |

### 风控参数（回撤与风险预算）

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `MAX_DRAWDOWN_HARD` | 0.20 | 总回撤硬线 |
| `DRAWDOWN_REDUCE_LEVEL_1` | 0.12 | 降仓线1 |
| `DRAWDOWN_REDUCE_LEVEL_2` | 0.16 | 降仓线2 |
| `DRAWDOWN_REDUCE_TARGET_L1` | 0.60 | 触发线1后总仓位上限 |
| `DRAWDOWN_REDUCE_TARGET_L2` | 0.30 | 触发线2后总仓位上限 |
| `MONTHLY_DRAWDOWN_SOFT` | 0.08 | 月度软线 |
| `MONTHLY_DRAWDOWN_HARD` | 0.12 | 月度硬线 |
| `MONTHLY_RISK_SCALE` | 0.50 | 触发软线后风险预算缩放 |
| `RISK_BUDGET_CONSERVATIVE` | 0.0030 | 稳健层单笔风险预算 |
| `RISK_BUDGET_AGGRESSIVE` | 0.0050 | 激进层单笔风险预算 |
| `MAX_SINGLE_POSITION_RATIO` | 0.40 | 单票最大仓位 |
| `RISK_CONTRIBUTION_LIMIT` | 0.25 | 单票风险贡献上限 |
| `LIQUIDITY_ADV_LIMIT` | 0.05 | 单票仓位不超过20日成交额的5% |

### 竞价过滤参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `AUCTION_GAP_UP_CANCEL` | 0.03 | 高开超过3%取消买入 |
| `AUCTION_GAP_DOWN_CANCEL` | 0.02 | 低开超过2%取消买入 |
| `AUCTION_GAP_UP_REPRICE` | 0.01 | 高开超过1%重定价 |
| `AUCTION_REPRICE_SLIPPAGE` | 0.005 | 重定价滑点 |
| `AUCTION_MIN_VOLUME_RATIO` | 0.5 | 量比过滤阈值 |
| `AUCTION_LIMIT_BUFFER` | 0.98 | 接近涨跌停缓冲 |

### 风格基准参数（组合加权）

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `ENABLE_STYLE_BENCHMARK` | True | 启用风格基准 |
| `STYLE_LOOKBACK_DAYS` | 120 | 基准历史窗口 |
| `STYLE_INDEX_CODES` | ... | 风格指数代码映射 |
| `STYLE_CAP_THRESHOLDS` | ... | 市值分层阈值 |
| `STYLE_BUCKET_MAP` | ... | 市值分层→指数映射 |
| `STYLE_DEFAULT_WEIGHTS` | ... | 无持仓时默认权重 |

### 板块强度过滤参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `ENABLE_SECTOR_STRENGTH_FILTER` | True | 启用板块强度过滤 |
| `SECTOR_STRENGTH_LOOKBACK` | 20 | 板块强度回看天数 |
| `SECTOR_STRENGTH_TOP_PCT` | 0.20 | 强度排名前百分比 |
| `SECTOR_STRENGTH_REQUIRE_EXCESS` | True | 要求超额收益>0 |
| `SECTOR_STRENGTH_REQUIRE_BOTH` | True | 行业+概念双重过滤 |
| `SECTOR_STRENGTH_APPLY_LAYERS` | aggressive | 仅激进层/全部 |
| `SECTOR_STRENGTH_ALLOW_NO_CONCEPT` | True | 无概念时是否放行 |
| `SECTOR_STRENGTH_CACHE_FILE` | data/sector_strength.json | 强度缓存 |

### 概念强度榜单参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `ENABLE_CONCEPT_STRENGTH_REPORT` | True | 输出概念强度榜单 |
| `CONCEPT_STRENGTH_TOP_N` | 20 | 输出榜单数量 |
| `CONCEPT_STRENGTH_OUTPUT_FILE` | data/concept_strength.csv | 榜单输出文件 |

### 分层策略参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `ENABLE_TWO_LAYER_STRATEGY` | True | 分层策略开关 |
| `CONSERVATIVE_CAPITAL_RATIO` | 0.20 | 稳健层资金比例 |
| `AGGRESSIVE_CAPITAL_RATIO` | 0.80 | 激进层资金比例 |
| `CONSERVATIVE_STOP_LOSS` | 0.05 | 稳健层止损-5% |
| `CONSERVATIVE_TAKE_PROFIT` | 0.15 | 稳健层止盈+15% |
| `AGGRESSIVE_STOP_LOSS` | 0.08 | 激进层止损-8% |
| `AGGRESSIVE_TAKE_PROFIT` | 0.25 | 激进层止盈+25% |

---

## 📁 文件说明

| 文件 | 作用 |
|------|------|
| `src/quant/main.py` | 主程序入口 |
| `config/config.py` | 配置参数 |
| `src/quant/strategy.py` | 策略逻辑（买入信号、止损止盈） |
| `src/quant/data_fetcher.py` | 数据获取（AKShare） |
| `src/quant/stock_pool.py` | 股票池管理 |
| `src/quant/plan_generator.py` | 交易计划生成 |
| `src/quant/auction_filter.py` | 竞价过滤器 |
| `src/quant/style_benchmark.py` | 风格基准合成 |
| `src/quant/stock_classifier.py` | 股票分类器（热门股/价值股） |
| `src/quant/layer_strategy.py` | 分层策略引擎 |
| `src/quant/sector_strength.py` | 板块强度过滤 |
| `src/quant/backtester.py` | 回测引擎 |
| `src/quant/transaction_cost.py` | 交易成本模型 |
| `src/quant/position_tracker.py` | 持仓跟踪 |
| `src/quant/drawdown_controller.py` | 回撤控制 |
| `src/quant/risk_control.py` | 风控状态读取 |
| `src/quant/risk_positioning.py` | 风险预算仓位计算 |
| `src/quant/visualizer.py` | 可视化报告 |
| `src/quant/notifier.py` | 消息推送 |
| `data/myshare.txt` | 自选股票池 |
| `data/hot_concepts.txt` | 热门概念配置 |
| `data/trading_plan.csv` | 生成的交易计划 |
| `data/concept_strength.csv` | 当日最强概念榜单 |
| `data/positions.json` | 持仓记录 |
| `config/notification_config.json` | 推送配置 |
| `tools/check_holdings.py` | 持仓快速扫描工具 |
| `tools/analyze_stock.py` | 个股深度诊断工具 |
| `src/quant/basic_filters.py` | 基本面过滤器（PE/PB/上市时间） |
| `src/quant/market_regime.py` | 市场状态识别（波动率分析） |
| `src/quant/risk_metrics.py` | 风险指标计算 |
| `src/quant/fund_control_detector.py` | 资金流向评分器（主力资金活跃度加分） |
| `update_holdings.py` | 账户数据手动更新脚本 |
| `outputs/` | 图表/报告输出目录 |

---

## 🔧 常见问题

### Q: 运行报错 `ModuleNotFoundError`
```bash
# 激活虚拟环境
source venv/bin/activate
```

### Q: 数据获取失败
网络问题或数据源限制，稍后重试即可。

### Q: 如何修改止损止盈比例？
编辑 `config/config.py` 中的 `STOP_LOSS_RATIO` 和 `TAKE_PROFIT_RATIO`。

### Q: 如何添加新股票到自选池？
编辑 `data/myshare.txt`，每行一个股票代码。

### Q: 回测的收益率为什么比预期低？
系统已加入滑点（0.1%）、佣金（万三）、印花税（千一）的交易成本，更接近实际交易。

---

## 📊 策略说明

### 分层策略（默认启用）

系统自动将股票分为两层，采用差异化策略：

| 分层 | 股票类型 | 筛选条件 | 止损 | 止盈 |
|------|----------|----------|------|------|
| 💰 稳健层 | 价值趋势股 | PE(0-50) + PB(≤5) + 站上MA20 + 量比≥1.3 | -5% | +15% |
| 🚀 激进层 | 热门资金股 | (PE>80 & 换手>8%) 或 (动量>25%) 或 (量比>3) 或 热门概念 + **资金流向加分** | -8% | +25% |

### 传统单层策略

使用 `--no-layer` 参数切换到传统模式：

#### 买入条件（需同时满足至少2条）
1. ✅ **动能趋势**：收盘价站上20日均线 + 成交量放大1.2倍
2. ✅ **突破确认**：前4日均在均线上方，最新日回踩不破
3. ✅ **量价健康**：排除价涨量缩的背离情况

#### 卖出条件（满足任一即卖出）
1. 🔴 **止损**：跌破止损价（ATR动态止损 或 固定5%）
2. 🟢 **止盈**：涨幅达到15%
3. 🟡 **移动止盈**：从最高点回落8%

### 大盘风控
当沪深300跌破60日均线时，停止推荐新股票。

---

## 🎓 进阶用法

### 批量回测多只股票并导出

```bash
PYTHONPATH=src python -c "
import pandas as pd
from quant.backtester import backtest_stock

stocks = ['000001', '600036', '002352', '601212', '000002']
all_trades = []

for code in stocks:
    trades = backtest_stock(code, '')
    all_trades.extend(trades)

# 导出到CSV
df = pd.DataFrame(all_trades)
df.to_csv('data/all_trades.csv', index=False)
print(f'共 {len(all_trades)} 笔交易，已保存到 data/all_trades.csv')
"
```

### 定时运行（每日收盘后）

```bash
# 添加到 crontab（每天17:00运行）
# crontab -e
# 0 17 * * 1-5 cd ~/workspace/量化 && source venv/bin/activate && PYTHONPATH=src python -m quant.main >> log.txt 2>&1
```

---

## ⚠️ 免责声明

本工具仅供学习和研究使用，不构成任何投资建议。股市有风险，投资需谨慎。作者不对任何因使用本工具造成的损失负责。

---

**Happy Trading! 🚀**
