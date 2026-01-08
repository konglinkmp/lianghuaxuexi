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

def get_stock_daily_history(symbol: str, days: int = 120) -> pd.DataFrame:
    """获取股票历史数据"""
    end_date = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
    try:
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
        if df.empty: return pd.DataFrame()
        df = df.rename(columns={'日期': 'date', '收盘': 'close', '最高': 'high', '最低': 'low', '成交量': 'volume'})
        df['date'] = pd.to_datetime(df['date'])
        return df
    except:
        return pd.DataFrame()

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

def get_ma_data(df: pd.DataFrame, window: int) -> float:
    """计算指定窗口的均线值"""
    if len(df) < window:
        return 0.0
    return df['close'].rolling(window=window).mean().iloc[-1]

def load_holdings():
    """从 positions.json 加载持仓"""
    pos_path = os.path.join(BASE_DIR, 'data', 'positions.json')
    if os.path.exists(pos_path):
        try:
            with open(pos_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 兼容字典格式和列表格式
                if isinstance(data, dict):
                    return [{"code": k, "name": v.get('name', k), "type": "etf" if k.startswith(('15', '51', '58')) else "stock"} for k, v in data.items()]
                return data
        except Exception as e:
            print(f"加载持仓文件失败: {e}")
    
    # 默认示例
    return [
        {"code": "159813", "name": "半导体 ETF", "type": "etf"},
        {"code": "588760", "name": "科创人工智能 ETF", "type": "etf"},
        {"code": "000547", "name": "航天发展", "type": "stock"}
    ]

def main():
    holdings = load_holdings()
    print(f"\n{'代码':<8} {'名称':<12} {'现价':<8} {'MA5':<8} {'MA20':<8} {'MA5偏离':<8} {'趋势'}")
    print("-" * 75)

    for item in holdings:
        code = item['code']
        name = item.get('name', '未知')
        is_etf = item.get('type') == 'etf' or code.startswith(('15', '51', '58'))
        
        try:
            df = get_etf_daily_history(code) if is_etf else get_stock_daily_history(code)
            if df.empty:
                print(f"{code:<8} {name:<12} {'无数据':<8}")
                continue
            
            latest_price = df.iloc[-1]['close']
            ma5 = get_ma_data(df, 5)
            ma20 = get_ma_data(df, 20)
            
            dist_ma5 = ((latest_price - ma5) / ma5 * 100) if ma5 > 0 else 0
            status = "✅ 趋势上" if latest_price > ma20 else "❌ 趋势下"
            
            # 偏离度预警
            alert = ""
            if dist_ma5 > 3:
                alert = "⚠️ 偏离过高"
            elif dist_ma5 < -3:
                alert = "📉 跌破均线"

            print(f"{code:<8} {name:<12} {latest_price:<8.3f} {ma5:<8.3f} {ma20:<8.3f} {dist_ma5:>6.2f}%   {status} {alert}")
        except Exception as e:
            print(f"{code:<8} {name:<12} 错误: {e}")

if __name__ == "__main__":
    main()
