import sys
import os
import pandas as pd
import akshare as ak
import json
from datetime import datetime, timedelta

# 将项目根目录添加到路径
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(BASE_DIR)
sys.path.append(os.path.join(BASE_DIR, 'src'))

try:
    from quant.data_fetcher import get_stock_daily_history
    from quant.strategy import get_latest_ma20
    from config.config import POSITION_FILE
except ImportError:
    print("警告: 无法导入项目模块，将使用独立模式运行")

def get_etf_daily_history(symbol: str, days: int = 120) -> pd.DataFrame:
    """获取 ETF 历史数据"""
    end_date = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
    try:
        df = ak.fund_etf_hist_em(symbol=symbol, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
        if df.empty: return pd.DataFrame()
        df = df.rename(columns={'日期': 'date', '收盘': 'close', '最高': 'high', '最低': 'low', '成交量': 'volume'})
        df['date'] = pd.to_datetime(df['date'])
        return df
    except:
        return pd.DataFrame()

def load_holdings():
    """从配置文件加载持仓，如果不存在则使用默认示例"""
    pos_path = os.path.join(BASE_DIR, 'data', 'positions.json')
    if os.path.exists(pos_path):
        try:
            with open(pos_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    
    # 默认示例（用户当前持仓）
    return [
        {"code": "159813", "name": "半导体 ETF", "type": "etf"},
        {"code": "588060", "name": "科创 50 ETF", "type": "etf"},
        {"code": "000547", "name": "航天发展", "type": "stock"},
        {"code": "588760", "name": "科创人工智能 ETF", "type": "etf"},
        {"code": "002352", "name": "顺丰控股", "type": "stock"}
    ]

def main():
    holdings = load_holdings()
    print(f"\n{'代码':<10} {'名称':<15} {'现价':<10} {'MA20':<10} {'趋势状态':<10}")
    print("-" * 65)

    for item in holdings:
        code = item['code']
        name = item.get('name', '未知')
        is_etf = item.get('type') == 'etf' or code.startswith(('15', '51', '58'))
        
        try:
            df = get_etf_daily_history(code) if is_etf else get_stock_daily_history(code)
            if df.empty:
                print(f"{code:<10} {name:<15} {'无数据':<10}")
                continue
            
            latest_price = df.iloc[-1]['close']
            ma20 = get_latest_ma20(df)
            status = "✅ 趋势上" if latest_price > ma20 else "❌ 趋势下"
            print(f"{code:<10} {name:<15} {latest_price:<10.3f} {ma20:<10.3f} {status}")
        except Exception as e:
            print(f"{code:<10} {name:<15} 错误: {e}")

if __name__ == "__main__":
    main()
