"""
风格漂移监控模块
通过计算沪深300与中证1000的相对强度(RPS)，判断市场风格
"""

import pandas as pd
from ..core.data_fetcher import get_stock_daily_history
from config.config import (
    RPS_LOOKBACK_DAYS,
    STYLE_SWITCH_THRESHOLD,
    MAX_CONSERVATIVE_RATIO,
    CONSERVATIVE_CAPITAL_RATIO
)

# 指数代码映射
INDEX_HS300 = 'sh000300'  # 沪深300 (代表大盘/价值)
INDEX_CSI1000 = 'sh000852' # 中证1000 (代表小盘/题材)
# 备用：如果取不到中证1000，可用中证500代替
INDEX_CSI500 = 'sh000905' 

class StyleMonitor:
    """
    市场风格监控器
    """
    
    def __init__(self):
        pass

    def get_index_return(self, index_code: str, days: int = 20) -> float:
        """
        获取指数近N日的收益率
        """
        df = get_stock_daily_history(index_code, days=days + 10)
        if df is None or df.empty or len(df) < days:
            return 0.0
            
        # 计算区间涨幅: (Latest Close - Start Close) / Start Close
        # 使用倒数第N天的收盘价作为基准
        try:
            latest_close = df.iloc[-1]['close']
            start_close = df.iloc[-days]['close']
            if start_close == 0:
                return 0.0
            return (latest_close - start_close) / start_close
        except Exception:
            return 0.0

    def check_style_drift(self) -> dict:
        """
        检查风格漂移情况
        
        Returns:
            dict: {
                'is_defensive': bool,       # 是否进入防守模式(大盘占优)
                'conservative_ratio': float, # 建议的稳健层权重
                'rps_diff': float,          # RPS差值 (HS300 - CSI1000)
                'hs300_ret': float,         # 沪深300涨幅
                'csi1000_ret': float,       # 中证1000涨幅
                'reason': str               # 原因说明
            }
        """
        # 1. 获取指数涨幅
        hs300_ret = self.get_index_return(INDEX_HS300, RPS_LOOKBACK_DAYS)
        
        # 优先尝试中证1000，如果没有数据则降级为中证500
        csi1000_ret = self.get_index_return(INDEX_CSI1000, RPS_LOOKBACK_DAYS)
        if csi1000_ret == 0.0:
             csi1000_ret = self.get_index_return(INDEX_CSI500, RPS_LOOKBACK_DAYS)
        
        # 2. 计算相对强度差值 (RPS Diff)
        # 这里简化处理，直接用收益率差值作为 RPS 差值的近似
        # 正值表示大盘强，负值表示小盘强
        rps_diff = hs300_ret - csi1000_ret
        
        # 3. 判断风格
        is_defensive = False
        suggested_ratio = CONSERVATIVE_CAPITAL_RATIO
        reason = "市场风格均衡"
        
        if rps_diff > STYLE_SWITCH_THRESHOLD:
            # 大盘股明显跑赢 -> 防守模式
            is_defensive = True
            suggested_ratio = MAX_CONSERVATIVE_RATIO
            reason = f"大盘股占优 (RPS差值 {rps_diff:.1%} > {STYLE_SWITCH_THRESHOLD:.1%})"
        elif rps_diff < -STYLE_SWITCH_THRESHOLD:
            # 小盘股明显跑赢 -> 维持激进或进一步激进(目前暂不调整激进上限)
            reason = f"小盘股占优 (RPS差值 {rps_diff:.1%})"
        
        return {
            'is_defensive': is_defensive,
            'conservative_ratio': suggested_ratio,
            'rps_diff': rps_diff,
            'hs300_ret': hs300_ret,
            'csi1000_ret': csi1000_ret,
            'reason': reason
        }

# 全局实例
style_monitor = StyleMonitor()
