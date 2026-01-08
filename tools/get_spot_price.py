import sys
import os
import pandas as pd
import akshare as ak
import json

# 将项目根目录添加到路径
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(BASE_DIR)

def load_holdings():
    """从 positions.json 加载持仓"""
    pos_path = os.path.join(BASE_DIR, 'data', 'positions.json')
    if os.path.exists(pos_path):
        try:
            with open(pos_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return list(data.keys())
                return [item['code'] for item in data]
        except:
            pass
    return []

def get_spot_price(symbols=None):
    if not symbols:
        symbols = load_holdings()
    
    if not symbols:
        print("未发现持仓，请输入代码。")
        return

    print(f"\n{'代码':<8} {'名称':<12} {'最新价':<8} {'涨跌额':<8} {'涨跌幅':<8}")
    print("-" * 50)

    # 分类处理
    stocks = [s for s in symbols if not s.startswith(('15', '51', '58'))]
    etfs = [s for s in symbols if s.startswith(('15', '51', '58'))]

    if stocks:
        try:
            stock_spot = ak.stock_zh_a_spot_em()
            for s in stocks:
                row = stock_spot[stock_spot['代码'] == s]
                if not row.empty:
                    print(f"{s:<8} {row['名称'].values[0]:<12} {row['最新价'].values[0]:<8.3f} {row['涨跌额'].values[0]:<8.3f} {row['涨跌幅'].values[0]:>6.2f}%")
        except Exception as e:
            print(f"获取股票行情失败: {e}")

    if etfs:
        try:
            etf_spot = ak.fund_etf_spot_em()
            for s in etfs:
                row = etf_spot[etf_spot['代码'] == s]
                if not row.empty:
                    print(f"{s:<8} {row['名称'].values[0]:<12} {row['最新价'].values[0]:<8.3f} {row['涨跌额'].values[0]:<8.3f} {row['涨跌幅'].values[0]:>6.2f}%")
        except Exception as e:
            print(f"获取 ETF 行情失败: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        get_spot_price(sys.argv[1:])
    else:
        get_spot_price()
