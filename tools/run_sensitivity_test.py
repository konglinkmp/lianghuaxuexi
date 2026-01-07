#!/usr/bin/env python
"""
参数敏感性测试命令行工具

用法:
    python tools/run_sensitivity_test.py --stocks data/myshare.txt
    python tools/run_sensitivity_test.py --limit 10 --output outputs/sensitivity.csv
"""

import argparse
import sys
import os

# 添加项目根目录到路径（包含 src 和 config）
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'src'))

import pandas as pd


def main():
    parser = argparse.ArgumentParser(description="参数敏感性测试工具")
    parser.add_argument(
        '--stocks', 
        type=str, 
        default='data/myshare.txt',
        help='股票池文件路径'
    )
    parser.add_argument(
        '--limit', 
        type=int, 
        default=0,
        help='限制测试股票数量（0=全部）'
    )
    parser.add_argument(
        '--output', 
        type=str, 
        default='outputs/sensitivity_report.csv',
        help='输出报告路径'
    )
    parser.add_argument(
        '--quick', 
        action='store_true',
        help='快速模式（减少参数组合）'
    )
    
    args = parser.parse_args()
    
    print("🔬 参数敏感性测试工具")
    print("=" * 60)
    
    # 加载股票池
    from quant.core.stock_pool import load_custom_pool
    from quant.core.data_fetcher import get_all_a_stock_list
    from quant.analysis.parameter_sensitivity import sensitivity_analyzer
    
    custom_codes = load_custom_pool(args.stocks)
    
    if custom_codes:
        print(f"[信息] 从 {args.stocks} 加载 {len(custom_codes)} 只股票")
        all_stocks = get_all_a_stock_list()
        if not all_stocks.empty:
            stock_pool = all_stocks[all_stocks['代码'].isin(custom_codes)].reset_index(drop=True)
        else:
            print("[错误] 无法获取股票列表")
            return
    else:
        print("[信息] 使用默认测试股票池")
        stock_pool = pd.DataFrame({
            '代码': ['000001', '600000', '000002', '600036', '601318'],
            '名称': ['平安银行', '浦发银行', '万科A', '招商银行', '中国平安']
        })
    
    # 限制数量
    if args.limit > 0:
        stock_pool = stock_pool.head(args.limit)
        print(f"[信息] 限制测试前 {args.limit} 只股票")
    
    print(f"[信息] 测试股票池: {len(stock_pool)} 只")
    
    # 定义参数范围
    if args.quick:
        param_ranges = {
            'MA_SHORT': [18, 20, 22],
            'STOP_LOSS_RATIO': [0.04, 0.05, 0.06],
        }
    else:
        param_ranges = {
            'MA_SHORT': [15, 18, 20, 22, 25],
            'STOP_LOSS_RATIO': [0.03, 0.05, 0.07],
            'TAKE_PROFIT_RATIO': [0.10, 0.15, 0.20],
            'VOLUME_RATIO_THRESHOLD': [1.0, 1.2, 1.5],
        }
    
    # 运行测试
    report = sensitivity_analyzer.run_sensitivity_test(
        stock_pool,
        param_ranges=param_ranges,
        verbose=True
    )
    
    # 打印报告
    sensitivity_analyzer.print_report(report)
    
    # 保存报告
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    sensitivity_analyzer.save_report(report, args.output)
    
    print(f"\n✅ 测试完成！")


if __name__ == '__main__':
    main()
