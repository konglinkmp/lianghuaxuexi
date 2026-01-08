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
TOTAL_CAPITAL = 64248  # 6.4万

# ============ 风控参数（v1.0） ============
# 总回撤控制
MAX_DRAWDOWN_HARD = 0.20        # 总回撤硬线（20%）
DRAWDOWN_REDUCE_LEVEL_1 = 0.12  # 降仓线1（12%）
DRAWDOWN_REDUCE_LEVEL_2 = 0.16  # 降仓线2（16%）
DRAWDOWN_REDUCE_TARGET_L1 = 0.60  # 触发线1后总仓位上限
DRAWDOWN_REDUCE_TARGET_L2 = 0.30  # 触发线2后总仓位上限

# 月度回撤控制
MONTHLY_DRAWDOWN_SOFT = 0.08    # 月度软线（8%）
MONTHLY_DRAWDOWN_HARD = 0.12    # 月度硬线（12%）
MONTHLY_RISK_SCALE = 0.50       # 触发软线后风险预算缩放
MONTHLY_COOLDOWN_DAYS = 5       # 月度硬线触发后冷却天数

# 风险预算与仓位上限
ENABLE_RISK_BUDGET = True
RISK_BUDGET_CONSERVATIVE = 0.0030  # 单笔风险预算（稳健层）0.30%
RISK_BUDGET_AGGRESSIVE = 0.0050    # 单笔风险预算（激进层）0.50%
RISK_BUDGET_DEFAULT = 0.0030       # 单层策略默认风险预算

# 单票与流动性限制
MAX_SINGLE_POSITION_RATIO = 0.40   # 单票最大仓位（占总资金）
RISK_CONTRIBUTION_LIMIT = 0.25     # 单票风险贡献上限（占组合风险预算）
LIQUIDITY_ADV_LIMIT = 0.05         # 单票仓位不超过20日成交额的5%

# 回撤控制开关（需配合账户净值输入）
ENABLE_DRAWDOWN_CONTROL = True

# ============ 竞价过滤参数 ============
AUCTION_GAP_UP_CANCEL = 0.03      # 高开超过3%取消买入
AUCTION_GAP_DOWN_CANCEL = 0.02    # 低开超过2%取消买入
AUCTION_GAP_UP_REPRICE = 0.01     # 高开超过1%则重新定触发价
AUCTION_REPRICE_SLIPPAGE = 0.005  # 触发价上浮滑点
AUCTION_MIN_VOLUME_RATIO = 0.5    # 竞价量比低于0.5取消
AUCTION_LIMIT_BUFFER = 0.98       # 接近涨跌停的缓冲比例

# ============ 风格基准（组合加权） ============
ENABLE_STYLE_BENCHMARK = True
STYLE_LOOKBACK_DAYS = 120
STYLE_INDEX_CODES = {
    "hs300": "sh000300",
    "csi500": "sh000905",
    "csi1000": "sh000852",
}
STYLE_CAP_THRESHOLDS = {
    "large": 100_000_000_000,  # 1000亿
    "mid": 30_000_000_000,     # 300亿
}
STYLE_BUCKET_MAP = {
    "large": "hs300",
    "mid": "csi500",
    "small": "csi1000",
}
STYLE_DEFAULT_WEIGHTS = {
    "hs300": 0.5,
    "csi1000": 0.5,
}

# ============ 板块强度过滤 ============
ENABLE_SECTOR_STRENGTH_FILTER = True
SECTOR_STRENGTH_LOOKBACK = 20
SECTOR_STRENGTH_TOP_PCT = 0.20
SECTOR_STRENGTH_REQUIRE_EXCESS = True
SECTOR_STRENGTH_REQUIRE_BOTH = True
SECTOR_STRENGTH_APPLY_LAYERS = "aggressive"  # aggressive / all
SECTOR_STRENGTH_ALLOW_NO_CONCEPT = True
SECTOR_STRENGTH_CACHE_FILE = "data/processed/sector_strength.json"

# 概念强度榜单输出
ENABLE_CONCEPT_STRENGTH_REPORT = True
CONCEPT_STRENGTH_TOP_N = 20
CONCEPT_STRENGTH_OUTPUT_FILE = "data/reports/concept_strength.csv"

# ============ 数据配置 ============
# 历史数据获取天数（需足够计算均线）
HISTORY_DAYS = 120

# 新股上市天数阈值（剔除上市不满N天的股票）
NEW_STOCK_DAYS = 365  # 1年

# ============ 输出配置 ============
# CSV输出文件名
OUTPUT_CSV = "data/reports/trading_plan.csv"

# ============ 指数代码 ============
# 沪深300指数代码
HS300_CODE = "sh000300"

# ============ 持仓管理 ============
# 最大同时持仓数量
MAX_POSITIONS = 10

# 同一行业最大持仓数量
MAX_SECTOR_POSITIONS = 3

# 持仓记录文件
POSITION_FILE = "data/runtime/positions.json"

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
CONSERVATIVE_CAPITAL_RATIO = 0.10  # 稳健层资金比例 (从0.20调低)
AGGRESSIVE_CAPITAL_RATIO = 0.90    # 激进层资金比例 (从0.80调高)

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
CONSERVATIVE_MAX_POSITIONS = 2     # 稳健层最大持仓数 (从5调低)
CONSERVATIVE_POSITION_RATIO = 0.12 # 稳健层单只仓位比例

# 激进层风控参数
AGGRESSIVE_STOP_LOSS = 0.08        # 激进层止损-8%
AGGRESSIVE_TAKE_PROFIT = 0.25      # 激进层止盈+25%
AGGRESSIVE_TRAILING_STOP = 0.10    # 激进层移动止盈-10%
AGGRESSIVE_MAX_POSITIONS = 8       # 激进层最大持仓数 (从3调高)
AGGRESSIVE_POSITION_RATIO = 0.08   # 激进层单只仓位比例
AGGRESSIVE_MAX_HOLDING_DAYS = 10   # 激进层最大持仓天数

# 热门概念配置文件
HOT_CONCEPTS_FILE = "data/processed/hot_concepts.txt"

# ============ 数据库配置 ============
DB_PATH = "data/storage/stock_data.db"

# ============ MACD技术指标配置 ============
MACD_FAST_PERIOD = 12         # 快线周期
MACD_SLOW_PERIOD = 26         # 慢线周期
MACD_SIGNAL_PERIOD = 9        # 信号线周期
MACD_CROSS_LOOKBACK = 3       # 金叉/死叉检测回溯天数
MACD_DIVERGENCE_LOOKBACK = 20 # 背离检测回溯天数
MACD_GOLDEN_CROSS_SCORE = 15  # 金叉加分
MACD_DIVERGENCE_SCORE = 20    # 背离加分
MACD_ZERO_AXIS_SCORE = 5      # DIF/DEA零轴之上加分

# ============ 专家见解与情绪因子 ============
# 专家情绪调节因子 (-1.0 到 1.0)
# -1.0: 极度悲观，0.0: 中性，1.0: 极度乐观
EXPERT_SENTIMENT_OVERRIDE = 0.0

# 是否监控中小盘风险 (中证1000/2000)
MONITOR_SMALL_CAP_RISK = True

# 回踩买入参考均线周期
PULLBACK_MA_PERIOD = 5

# 价格偏离5日线比例阈值（超过此比例视为追高，建议等待回踩）
PULLBACK_DEVIATION_THRESHOLD = 0.02  # 2%

# ============ 组合风控参数 (v2.0) ============
# 单一行业最大持仓市值比例（占总资产）
MAX_INDUSTRY_POSITION_RATIO = 0.30  # 30%

# 持仓相关性风控
MAX_CORRELATION_THRESHOLD = 0.70    # 平均相关系数阈值
CORRELATION_LOOKBACK_DAYS = 60      # 计算相关性的回溯天数

# ============ 风格漂移监控参数 (v2.1) ============
RPS_LOOKBACK_DAYS = 20              # RPS计算回溯天数
STYLE_SWITCH_THRESHOLD = 0.1        # 风格切换阈值 (RPS差值 > 0.1 视为大盘占优)
MAX_CONSERVATIVE_RATIO = 0.8        # 防守模式下稳健层最大比例

# ============ 交易执行增强参数 (v2.2) ============
AUCTION_WITHDRAWAL_LIMIT = 0.3      # 竞价撤单率阈值 (预留)
INTRADAY_DIVE_THRESHOLD = -0.02     # 尾盘跳水阈值 (-2%)



