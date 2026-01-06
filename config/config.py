"""
全局配置参数
"""

# ============ 策略参数 ============
# 止损比例（跌幅超过此比例触发止损）
STOP_LOSS_RATIO = 0.05  # 5%

# 固定止盈目标
TAKE_PROFIT_RATIO = 0.15  # 15%

# 均线周期
MA_SHORT = 20  # 短期均线（用于判断趋势）
MA_LONG = 60   # 长期均线（用于判断大盘风险）

# 成交量放大倍数阈值
VOLUME_RATIO_THRESHOLD = 1.2

# 价格偏离均线最大比例（超过此比例视为追高，不买入）
MAX_PRICE_DEVIATION = 0.03  # 3%

# 移动止盈：从最高点回落此比例后止盈
TRAILING_STOP_RATIO = 0.08  # 8%

# ============ 资金管理 ============
# 单笔仓位占总资金比例
POSITION_RATIO = 0.10  # 10%

# 总资金（用于计算建议仓位金额，可自行修改）
TOTAL_CAPITAL = 100000  # 10万

# ============ 数据配置 ============
# 历史数据获取天数（需足够计算均线）
HISTORY_DAYS = 120

# 新股上市天数阈值（剔除上市不满N天的股票）
NEW_STOCK_DAYS = 365  # 1年

# ============ 输出配置 ============
# CSV输出文件名
OUTPUT_CSV = "data/trading_plan.csv"

# ============ 指数代码 ============
# 沪深300指数代码
HS300_CODE = "sh000300"

# ============ 持仓管理 ============
# 最大同时持仓数量
MAX_POSITIONS = 10

# 同一行业最大持仓数量
MAX_SECTOR_POSITIONS = 3

# 持仓记录文件
POSITION_FILE = "data/positions.json"

# ============ 基本面筛选 ============
# 最大市盈率（剔除过高估值）
MAX_PE = 50

# 最大市净率（避免过度泡沫）
MAX_PB = 5

# 最小上市年限（避开次新股）
MIN_LIST_YEARS = 2

# ============ 分层策略配置 ============
# 分层策略总开关
ENABLE_TWO_LAYER_STRATEGY = True

# 资金分配
CONSERVATIVE_CAPITAL_RATIO = 0.70  # 稳健层资金比例
AGGRESSIVE_CAPITAL_RATIO = 0.30    # 激进层资金比例

# 股票分类阈值 - 热门资金股
HOT_STOCK_MIN_PE = 80              # 热门股最小PE
HOT_STOCK_MIN_TURNOVER = 8.0       # 最小换手率(%)
HOT_STOCK_MIN_MOMENTUM = 25.0      # 最小10日涨幅(%)
HOT_STOCK_VOLUME_RATIO = 3.0       # 成交量放大倍数

# 股票分类阈值 - 价值趋势股
VALUE_STOCK_MAX_PE = 50            # 价值股最大PE
VALUE_STOCK_MAX_PB = 5.0           # 价值股最大PB
VALUE_STOCK_MIN_VOLUME_RATIO = 1.3 # 最小成交量放大

# 稳健层风控参数
CONSERVATIVE_STOP_LOSS = 0.05      # 稳健层止损-5%
CONSERVATIVE_TAKE_PROFIT = 0.15    # 稳健层止盈+15%
CONSERVATIVE_TRAILING_STOP = 0.08  # 稳健层移动止盈-8%
CONSERVATIVE_MAX_POSITIONS = 5     # 稳健层最大持仓数
CONSERVATIVE_POSITION_RATIO = 0.12 # 稳健层单只仓位比例

# 激进层风控参数
AGGRESSIVE_STOP_LOSS = 0.08        # 激进层止损-8%
AGGRESSIVE_TAKE_PROFIT = 0.25      # 激进层止盈+25%
AGGRESSIVE_TRAILING_STOP = 0.10    # 激进层移动止盈-10%
AGGRESSIVE_MAX_POSITIONS = 3       # 激进层最大持仓数
AGGRESSIVE_POSITION_RATIO = 0.08   # 激进层单只仓位比例
AGGRESSIVE_MAX_HOLDING_DAYS = 10   # 激进层最大持仓天数

# 热门概念配置文件
HOT_CONCEPTS_FILE = "data/hot_concepts.txt"
