import sys
import os
import pandas as pd
import akshare as ak

# 将项目根目录添加到路径
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(BASE_DIR)
sys.path.append(os.path.join(BASE_DIR, 'src'))

def analyze_stock(symbol):
    print(f"\n{'='*20} {symbol} 深度诊断报告 {'='*20}")
    
    # 1. 基本面
    try:
        info = ak.stock_individual_info_em(symbol=symbol)
        print("\n[1. 基本面信息]")
        for _, row in info.iterrows():
            if row['item'] in ['总市值', '流通市值', '行业', '上市时间']:
                print(f" - {row['item']}: {row['value']}")
    except:
        print(" - 无法获取基本面数据")

    # 2. 最近 10 日走势
    try:
        # 自动判断是 ETF 还是个股
        if symbol.startswith(('15', '51', '58')):
            df = ak.fund_etf_hist_em(symbol=symbol, period="daily", adjust="qfq")
        else:
            df = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq")
            
        if df.empty:
            print("\n[2. 行情数据] 暂无数据")
            return

        print("\n[2. 最近 10 日走势]")
        recent = df.tail(10).copy()
        recent = recent.rename(columns={'日期': 'date', '收盘': 'close', '涨跌幅': 'pct_chg', '成交量': 'volume'})
        print(recent[['date', 'close', 'pct_chg', 'volume']].to_string(index=False))
        
        # 3. 技术面简评
        latest_price = recent.iloc[-1]['close']
        avg_price = recent['close'].mean()
        print("\n[3. 技术面简评]")
        if latest_price > avg_price:
            print(f" - 当前价格(¥{latest_price})高于10日均价(¥{avg_price:.2f})，短期走势偏强。")
        else:
            print(f" - 当前价格(¥{latest_price})低于10日均价(¥{avg_price:.2f})，短期处于回调中。")
            
    except Exception as e:
        print(f"\n[错误] 分析失败: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使用方法: python tools/analyze_stock.py <股票代码>")
        print("示例: python tools/analyze_stock.py 002196")
    else:
        analyze_stock(sys.argv[1])
