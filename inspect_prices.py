import akshare as ak
import pandas as pd
import sys
import os

# 动态添加路径
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(script_dir, 'src'))

from quant.core.data_fetcher import get_stock_daily_history

def inspect():
    stocks = {
        '600410': '华胜天成',
        '002050': '三花智控',
        '002195': '岩山科技',
        '601336': '新华保险'
    }
    
    print("="*50)
    print("盘中紧急风控检查 (1月14日 开盘期)")
    print("="*50)
    
    try:
        spot_df = ak.stock_zh_a_spot_em()
    except Exception as e:
        print(f"获取实时行情失败: {e}")
        return

    for code, name in stocks.items():
        # 获取 MA5
        try:
            hist_df = get_stock_daily_history(code, days=15)
            ma5 = hist_df['close'].rolling(5).mean().iloc[-1]
        except:
            ma5 = 0
            
        # 获取现价
        row = spot_df[spot_df['代码'] == code]
        if not row.empty:
            price = row['最新价'].values[0]
            pct = row['涨跌幅'].values[0]
            
            status = "🟢 正常 (MA5之上)" if price >= ma5 else "🔴 破位 (MA5之下)"
            action = "纠错卖出" if code == '600410' and price < ma5 else "持仓观察"
            
            print(f"{name}({code}): 现价:{price:.2f} ({pct:+.2f}%) | MA5:{ma5:.2f} | {status} | 建议:{action}")
        else:
            print(f"{name}({code}): 未获取到实时数据")
    print("="*50)

if __name__ == "__main__":
    inspect()
