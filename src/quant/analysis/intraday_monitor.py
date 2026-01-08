"""
日内交易监控模块
负责监控竞价异常（诱多）和盘中特定时间窗效应（如14:00跳水）
"""

import pandas as pd
import numpy as np
from ..core.data_fetcher import get_stock_daily_history
from config.config import INTRADAY_DIVE_THRESHOLD

class IntradayMonitor:
    """
    日内监控器
    """
    
    def __init__(self):
        pass

    def check_1400_dive(self, code: str) -> dict:
        """
        检查昨日是否存在 14:00 后跳水现象
        
        Args:
            code: 股票代码
            
        Returns:
            dict: {
                'has_dive': bool,
                'dive_pct': float,
                'warning': str
            }
        """
        # 由于没有分钟级数据接口，这里使用日线数据的上影线或特定逻辑作为近似替代
        # 或者如果有分钟数据文件，可以读取
        # 暂时方案：检查昨日是否"冲高回落"且收盘接近最低价
        
        df = get_stock_daily_history(code, days=5)
        if df is None or df.empty:
            return {'has_dive': False, 'dive_pct': 0.0, 'warning': ''}
            
        # 获取昨日数据
        try:
            yesterday = df.iloc[-1]
            open_p = yesterday['open']
            close_p = yesterday['close']
            high_p = yesterday['high']
            low_p = yesterday['low']
            
            # 计算实体和上影线
            body = abs(close_p - open_p)
            upper_shadow = high_p - max(open_p, close_p)
            
            # 简单的"跳水"特征：
            # 1. 曾大幅上涨 (High > Open * 1.03)
            # 2. 收盘回落显著 (Close < High * 0.98)
            # 3. 收盘价接近当日最低 (Close - Low < (High - Low) * 0.2)
            
            is_high_dive = False
            dive_pct = 0.0
            
            if high_p > open_p * 1.03:
                dive_pct = (close_p / high_p) - 1
                if dive_pct < INTRADAY_DIVE_THRESHOLD:
                    # 进一步检查是否收在低位
                    range_len = high_p - low_p
                    if range_len > 0 and (close_p - low_p) / range_len < 0.3:
                        is_high_dive = True
            
            if is_high_dive:
                return {
                    'has_dive': True,
                    'dive_pct': dive_pct,
                    'warning': f"昨日冲高回落{dive_pct*100:.1f}%，警惕尾盘惯性杀跌"
                }
                
        except Exception:
            pass
            
        return {'has_dive': False, 'dive_pct': 0.0, 'warning': ''}

    def check_auction_anomaly(self, code: str, current_open: float, pre_close: float) -> dict:
        """
        检查竞价异常（如高开低量诱多）
        
        Args:
            code: 股票代码
            current_open: 当前开盘价
            pre_close: 昨日收盘价
            
        Returns:
            dict: {
                'is_anomaly': bool,
                'warning': str
            }
        """
        # 需要结合成交量判断，但开盘前可能拿不到准确的竞价成交量
        # 这里仅做价格层面的简单预警：大幅高开
        
        pct_chg = (current_open / pre_close) - 1
        
        if pct_chg > 0.04: # 高开超过 4%
            return {
                'is_anomaly': True,
                'warning': f"大幅高开 {pct_chg*100:.1f}%，需关注竞价成交量是否匹配，谨防诱多"
            }
            
        return {'is_anomaly': False, 'warning': ''}

# 全局实例
intraday_monitor = IntradayMonitor()
