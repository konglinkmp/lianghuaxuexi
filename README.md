# 📈 A股量化交易决策辅助工具

一个基于 Python 的 A 股量化交易决策辅助系统，帮助你筛选股票、生成交易计划、回测策略效果。

---

## 🚀 快速开始

```bash
# 1. 进入项目目录
cd ~/workspace/量化

# 2. 激活虚拟环境
source venv/bin/activate

# 3. 运行主程序
PYTHONPATH=src python -m quant.main
```

---

## 📋 功能一览

| 功能 | 说明 | 命令 |
|------|------|------|
| 生成交易计划 | 筛选明日可买入的股票 | `PYTHONPATH=src python -m quant.main` |
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

# 运行主程序（默认分析2000只股票）
PYTHONPATH=src python -m quant.main
```

**输出结果：**
- 终端显示符合条件的股票列表
- 自动保存到 `data/trading_plan.csv` 文件

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
| `TOTAL_CAPITAL` | 100000 | 总资金（用于计算仓位） |
| `POSITION_RATIO` | 0.10 | 单笔仓位比例（10%） |

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
| `src/quant/backtester.py` | 回测引擎 |
| `src/quant/transaction_cost.py` | 交易成本模型 |
| `src/quant/position_tracker.py` | 持仓跟踪 |
| `src/quant/drawdown_controller.py` | 回撤控制 |
| `src/quant/visualizer.py` | 可视化报告 |
| `src/quant/notifier.py` | 消息推送 |
| `data/myshare.txt` | 自选股票池 |
| `data/trading_plan.csv` | 生成的交易计划 |
| `data/positions.json` | 持仓记录 |
| `config/notification_config.json` | 推送配置 |
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

### 买入条件（需同时满足至少2条）
1. ✅ **动能趋势**：收盘价站上20日均线 + 成交量放大1.2倍
2. ✅ **突破确认**：前4日均在均线上方，最新日回踩不破
3. ✅ **量价健康**：排除价涨量缩的背离情况

### 卖出条件（满足任一即卖出）
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
