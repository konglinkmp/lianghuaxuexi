"""
盘中实时监控脚本
功能：
1. 监控持仓股票：止损、止盈、移动止盈
2. 监控计划股票：达到买入价提醒
3. 监控大盘风险：沪深300跌破60日均线
"""

import time
import pandas as pd
import akshare as ak
from datetime import datetime
import argparse
import sys
import os

# 添加项目根目录到 path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.quant.trade.position_tracker import position_tracker
from src.quant.utils.notifier import notification_manager
from src.quant.core.data_fetcher import get_index_daily_history
from src.quant.strategy.strategy import calculate_ma
from config.config import OUTPUT_CSV, HS300_CODE, MA_LONG

# 警报冷却时间（秒），防止重复发送
ALERT_COOLDOWN = 300 
_alert_history = {}

# 全局缓存
_ma60_cache = {
    'date': None,
    'value': None
}

def get_cached_ma60():
    """获取缓存的MA60，每天只计算一次"""
    global _ma60_cache
    today = datetime.now().strftime('%Y-%m-%d')
    
    if _ma60_cache['date'] == today and _ma60_cache['value'] is not None:
        return _ma60_cache['value']
        
    try:
        # 获取历史数据计算MA60
        # 注意：这里只需要历史收盘价，不需要实时数据
        # 使用 get_index_daily_history 会去获取最新数据，可能会慢
        # 我们只需要昨天及之前的数据
        hist_df = get_index_daily_history(HS300_CODE, days=MA_LONG + 20)
        if hist_df.empty:
            return None
            
        hist_df['ma60'] = calculate_ma(hist_df, MA_LONG)
        # 取最后一个有效值（应该是昨天的MA60，因为今天的收盘价还没出来/或者刚出来）
        # 如果是盘中，get_index_daily_history 返回的最后一条可能是昨天的数据（取决于接口更新时间）
        # 我们假设最后一条是最近的有效MA60
        ma60 = hist_df['ma60'].iloc[-1]
        
        _ma60_cache['date'] = today
        _ma60_cache['value'] = ma60
        print(f"[信息] 更新MA60基准: {ma60:.2f}")
        return ma60
    except Exception as e:
        print(f"[错误] 计算MA60失败: {e}")
        return None

def check_market_risk_realtime() -> bool:
    """
    检查大盘实时风险
    逻辑：获取沪深300实时价格，对比MA60
    """
    try:
        last_ma60 = get_cached_ma60()
        if last_ma60 is None:
            return False
        
        # 获取实时价格
        # 尝试使用新浪接口获取指数实时行情（速度较快）
        # ak.stock_zh_index_spot_sina(symbol="sh000300")
        try:
            spot_df = ak.stock_zh_index_spot_sina(symbol=HS300_CODE)
            current_price = float(spot_df.iloc[0]['最新价'])
        except AttributeError:
            # 如果新浪接口不可用，尝试备用接口
            # 比如 stock_zh_index_spot_em (东方财富)
            try:
                # 注意：em接口可能返回所有指数，需要过滤
                # 或者 ak.stock_zh_index_spot()
                # 这里做个简单的降级：如果获取不到实时，就跳过
                return False
            except:
                return False
        except Exception:
            return False
        
        if current_price < last_ma60:
            send_alert_once(
                "market_risk", 
                f"⚠️ 大盘风险警告", 
                f"沪深300({current_price}) 跌破 MA60({last_ma60:.2f})，建议暂停开仓"
            )
            return True
            
        return False
        
    except Exception as e:
        print(f"[错误] 检查大盘风险失败: {e}")
        return False

def get_realtime_quotes(codes: list) -> dict:
    """
    获取指定股票的实时行情
    Returns: {code: {'price': float, 'name': str, 'pct': float}}
    """
    if not codes:
        return {}
        
    try:
        # 获取全市场实时行情（akshare目前最稳定的实时接口）
        # 耗时约1-2秒
        df = ak.stock_zh_a_spot_em()
        
        quotes = {}
        # 过滤需要的股票
        target_df = df[df['代码'].isin(codes)]
        
        for _, row in target_df.iterrows():
            quotes[row['代码']] = {
                'price': float(row['最新价']),
                'name': row['名称'],
                'pct': float(row['涨跌幅'])
            }
            
        return quotes
    except Exception as e:
        print(f"[错误] 获取实时行情失败: {e}")
        return {}

def send_alert_once(key: str, title: str, content: str):
    """发送警报（带冷却机制）"""
    global _alert_history
    now = time.time()
    
    if key in _alert_history:
        last_time = _alert_history[key]
        if now - last_time < ALERT_COOLDOWN:
            return
            
    print(f"\n[警报] {title} - {content}")
    success = notification_manager.send_alert(key.split(':')[0], f"{title}\n{content}")
    if success:
        _alert_history[key] = now

def monitor_holdings(quotes: dict):
    """监控持仓"""
    positions = position_tracker.get_all_positions()
    if not positions:
        return
        
    for code, pos in positions.items():
        if code not in quotes:
            continue
            
        current_price = quotes[code]['price']
        pct = quotes[code]['pct']
        name = pos['name']
        
        # 更新持仓跟踪器里的价格（用于移动止盈计算）
        signal = position_tracker.update_price(code, current_price)
        
        # 1. 止损
        if signal == 'stop_loss':
            send_alert_once(
                f"stop_loss:{code}",
                f"🔴 止损触达: {name}",
                f"现价: {current_price} (跌幅{pct}%) <= 止损价: {pos['stop_loss']}\n请及时卖出！"
            )
            
        # 2. 止盈
        elif signal == 'take_profit':
            send_alert_once(
                f"take_profit:{code}",
                f"🟢 止盈触达: {name}",
                f"现价: {current_price} (涨幅{pct}%) >= 止盈价: {pos['take_profit']}\n建议落袋为安！"
            )
            
        # 3. 移动止盈
        elif signal == 'trailing_stop':
            send_alert_once(
                f"trailing_stop:{code}",
                f"📉 移动止盈触发: {name}",
                f"现价: {current_price} 从高点回落\n建议卖出保住利润！"
            )

def monitor_plan(quotes: dict):
    """监控交易计划"""
    if not os.path.exists(OUTPUT_CSV):
        return
        
    try:
        plan_df = pd.read_csv(OUTPUT_CSV, dtype={'代码': str})
    except Exception:
        return
        
    for _, row in plan_df.iterrows():
        code = row['代码']
        if code not in quotes:
            continue
            
        # 如果已经持仓，就不监控买入信号了
        if position_tracker.get_position(code):
            continue
            
        current_price = quotes[code]['price']
        buy_price = row.get('建议买入价', 0)
        name = row['名称']
        
        # 简单的买入监控：价格低于等于建议买入价（假设是限价单逻辑）
        # 或者：价格上涨突破关键位？
        # 这里假设：如果现价接近建议买入价（+/- 1%），提示关注
        if buy_price > 0 and abs(current_price - buy_price) / buy_price < 0.01:
             send_alert_once(
                f"buy_signal:{code}",
                f"👀 买入机会: {name}",
                f"现价: {current_price} 接近建议买入价: {buy_price}\n请关注！"
            )

def run_monitor(interval: int = 60):
    """运行监控循环"""
    print(f"🚀 启动盘中监控 (间隔 {interval}秒)...")
    print("按 Ctrl+C 停止")
    
    while True:
        try:
            now = datetime.now()
            current_time = now.strftime("%H:%M:%S")
            
            # 交易时间判断 (9:30-11:30, 13:00-15:00)
            # 简单判断，不考虑节假日
            is_trading_time = (
                (now.hour == 9 and now.minute >= 30) or
                (now.hour == 10) or
                (now.hour == 11 and now.minute <= 30) or
                (now.hour >= 13 and now.hour < 15)
            )
            
            if not is_trading_time:
                print(f"[{current_time}] 非交易时间，休眠中...", end='\r')
                time.sleep(interval)
                continue
                
            print(f"[{current_time}] 正在监控...", end='\r')
            
            # 1. 检查大盘
            check_market_risk_realtime()
            
            # 2. 获取关注股票列表
            holdings = list(position_tracker.get_all_positions().keys())
            
            plan_codes = []
            if os.path.exists(OUTPUT_CSV):
                try:
                    df = pd.read_csv(OUTPUT_CSV, dtype={'代码': str})
                    plan_codes = df['代码'].tolist()
                except:
                    pass
            
            all_codes = list(set(holdings + plan_codes))
            
            if not all_codes:
                print(f"[{current_time}] 无关注股票", end='\r')
                time.sleep(interval)
                continue
                
            # 3. 获取行情
            quotes = get_realtime_quotes(all_codes)
            
            # 4. 监控逻辑
            monitor_holdings(quotes)
            monitor_plan(quotes)
            
            time.sleep(interval)
            
        except KeyboardInterrupt:
            print("\n🛑 监控已停止")
            break
        except Exception as e:
            print(f"\n[错误] 监控循环异常: {e}")
            time.sleep(interval)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="盘中实时监控")
    parser.add_argument("--interval", type=int, default=60, help="监控间隔(秒)")
    parser.add_argument("--once", action="store_true", help="只运行一次")
    args = parser.parse_args()
    
    if args.once:
        print("执行单次监控...")
        # 强制执行，忽略时间检查
        check_market_risk_realtime()
        
        holdings = list(position_tracker.get_all_positions().keys())
        plan_codes = []
        if os.path.exists(OUTPUT_CSV):
            try:
                df = pd.read_csv(OUTPUT_CSV, dtype={'代码': str})
                plan_codes = df['代码'].tolist()
            except:
                pass
        all_codes = list(set(holdings + plan_codes))
        
        if all_codes:
            quotes = get_realtime_quotes(all_codes)
            monitor_holdings(quotes)
            monitor_plan(quotes)
        print("完成")
    else:
        run_monitor(args.interval)
