"""
A股量化交易决策辅助工具 - 主程序入口

功能：
1. 检查大盘风险（沪深300 vs MA60）
2. 遍历股票池筛选买入信号
3. 生成并输出"明日操作清单"

使用方法：
    PYTHONPATH=src python -m quant.main                    # 使用全A股（剔除ST）
    PYTHONPATH=src python -m quant.main --custom           # 使用自定义股票池 data/myshare.txt
    PYTHONPATH=src python -m quant.main --custom --file data/pool.txt  # 指定自定义股票池文件
    PYTHONPATH=src python -m quant.main --no-adaptive      # 禁用自适应参数
"""

import argparse
import os
from datetime import datetime
from .stock_pool import get_final_pool
from .strategy import check_market_risk
from .plan_generator import generate_trading_plan, print_trading_plan, save_trading_plan
from .market_regime import adaptive_strategy
from .data_fetcher import get_index_daily_history
from config.config import TOTAL_CAPITAL


def print_header():
    """打印程序头部信息"""
    print("\n" + "=" * 70)
    print("🚀 A股量化交易决策辅助工具")
    print(f"📅 运行时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"💰 资金配置：¥{TOTAL_CAPITAL:,.0f}")
    print("=" * 70)


def update_market_regime() -> str:
    try:
        index_df = get_index_daily_history()
        if index_df.empty:
            return ""

        result = adaptive_strategy.update_regime(index_df["close"])
        adaptive_strategy.print_status()
        return result.get("regime_name", "")
    except Exception as exc:
        print(f"[警告] 市场状态识别失败: {exc}")
        return ""


def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='A股量化交易决策辅助工具')
    parser.add_argument('--custom', action='store_true', 
                        help='使用自定义股票池')
    parser.add_argument('--file', type=str, default='data/myshare.txt',
                        help='自定义股票池文件路径（默认: data/myshare.txt）')
    parser.add_argument('--limit', type=int, default=0,
                        help='限制分析股票数量（0表示不限制，用于测试）')
    parser.add_argument('--skip-risk-check', action='store_true',
                        help='跳过大盘风险检查')
    parser.add_argument('--no-adaptive', action='store_true',
                        help='禁用市场状态自适应参数')
    parser.add_argument('--no-layer', action='store_true',
                        help='禁用分层策略，使用传统单层策略')
    
    args = parser.parse_args()
    
    # 打印头部
    print_header()
    
    # Step 1: 检查大盘风险
    if not args.skip_risk_check:
        print("\n📈 正在检查大盘风险...")
        is_risky, msg = check_market_risk()
        print(msg)
        
        if is_risky:
            print("\n⛔ 由于大盘风险较大，本次停止选股。")
            print("💡 建议：检查持仓中是否有需要止损的股票。")
            return
    else:
        print("\n⏭️ 已跳过大盘风险检查")
    
    # Step 1.5: 更新市场状态（可选）
    market_status = ""
    if args.no_adaptive:
        adaptive_strategy.reset()
        print("\n⏭️ 已禁用自适应参数")
    else:
        print("\n🧭 正在识别市场状态...")
        market_status = update_market_regime()

    # Step 2: 获取股票池
    print("\n📊 正在获取股票池...")
    
    if args.custom:
        if not os.path.exists(args.file):
            print(f"[错误] 自定义股票池文件不存在: {args.file}")
            print("请创建该文件，每行一个股票代码，例如：")
            print("000001")
            print("600000")
            return
    
    stock_pool = get_final_pool(
        use_custom=args.custom, 
        custom_file=args.file,
        skip_new_stock_filter=True  # 跳过新股过滤以加速
    )
    
    if stock_pool.empty:
        print("[错误] 获取股票池失败")
        return
    
    # 如果指定了限制数量
    if args.limit > 0:
        stock_pool = stock_pool.head(args.limit)
        print(f"[信息] 已限制分析数量为前 {args.limit} 只股票")
    
    # Step 3: 生成交易计划
    print(f"\n🔍 正在分析 {len(stock_pool)} 只股票，请稍候...")
    
    # 根据命令行参数决定是否使用分层策略
    use_layer = not args.no_layer
    plan = generate_trading_plan(stock_pool, verbose=True, use_layer_strategy=use_layer)
    
    # Step 4: 输出结果
    print_trading_plan(plan, market_status=market_status)
    save_trading_plan(plan)
    
    print("\n✅ 分析完成！")


if __name__ == "__main__":
    main()
