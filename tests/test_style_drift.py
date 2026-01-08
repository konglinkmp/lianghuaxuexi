
import sys
import os
import pandas as pd
import unittest
from unittest.mock import MagicMock, patch

# 添加 src 到路径
sys.path.append(os.path.join(os.getcwd(), 'src'))

from quant.analysis.style_monitor import StyleMonitor, INDEX_HS300, INDEX_CSI1000
from quant.strategy.layer_strategy import LayerStrategy
from config.config import TOTAL_CAPITAL, CONSERVATIVE_CAPITAL_RATIO, MAX_CONSERVATIVE_RATIO

class TestStyleDrift(unittest.TestCase):
    def setUp(self):
        self.monitor = StyleMonitor()
        self.strategy = LayerStrategy(total_capital=100000)
        
    @patch('quant.analysis.style_monitor.get_stock_daily_history')
    def test_style_drift_detection(self, mock_get_history):
        # 模拟指数数据
        dates = pd.date_range(start='2024-01-01', periods=30)
        
        # 场景 1: 大盘强 (HS300 涨 20%, CSI1000 跌 10%)
        # RPS Diff = 0.2 - (-0.1) = 0.3 > 0.1 -> 触发防守
        df_hs300_bull = pd.DataFrame({'close': [100 * (1 + i*0.007) for i in range(30)]}, index=dates)
        df_csi1000_bear = pd.DataFrame({'close': [100 * (1 - i*0.0035) for i in range(30)]}, index=dates)
        
        def side_effect_bull(code, days=None):
            if code == INDEX_HS300: return df_hs300_bull
            if code == INDEX_CSI1000: return df_csi1000_bear
            return None
            
        mock_get_history.side_effect = side_effect_bull
        
        result = self.monitor.check_style_drift()
        print(f"\n[测试] 风格检测(大盘强): {result['reason']}")
        self.assertTrue(result['is_defensive'])
        self.assertEqual(result['conservative_ratio'], MAX_CONSERVATIVE_RATIO)
        
        # 场景 2: 小盘强 (HS300 跌, CSI1000 涨)
        # RPS Diff < 0 -> 不触发防守
        df_hs300_bear = pd.DataFrame({'close': [100 * (1 - i*0.001) for i in range(30)]}, index=dates)
        df_csi1000_bull = pd.DataFrame({'close': [100 * (1 + i*0.01) for i in range(30)]}, index=dates)
        
        def side_effect_bear(code, days=None):
            if code == INDEX_HS300: return df_hs300_bear
            if code == INDEX_CSI1000: return df_csi1000_bull
            return None
            
        mock_get_history.side_effect = side_effect_bear
        
        result = self.monitor.check_style_drift()
        print(f"\n[测试] 风格检测(小盘强): {result['reason']}")
        self.assertFalse(result['is_defensive'])
        self.assertEqual(result['conservative_ratio'], CONSERVATIVE_CAPITAL_RATIO)

    @patch('quant.analysis.style_monitor.StyleMonitor.check_style_drift')
    def test_strategy_integration(self, mock_check_drift):
        # 模拟触发防守模式
        mock_check_drift.return_value = {
            'is_defensive': True,
            'conservative_ratio': 0.8,
            'reason': '测试强制防守'
        }
        
        # 生成信号（会触发内部的权重调整）
        # 我们只需要 mock 一个空的 stock_pool
        empty_pool = pd.DataFrame(columns=['代码', '名称'])
        
        # 运行前检查默认值
        print(f"\n[测试] 调整前稳健层资金: {self.strategy.conservative_capital}")
        self.assertEqual(self.strategy.conservative_capital, 100000 * 0.2)
        
        self.strategy.generate_layer_signals(empty_pool, verbose=True, ignore_holdings=True)
        
        # 运行后检查调整值
        print(f"[测试] 调整后稳健层资金: {self.strategy.conservative_capital}")
        self.assertEqual(self.strategy.conservative_capital, 100000 * 0.8)
        self.assertAlmostEqual(self.strategy.aggressive_capital, 100000 * 0.2)

if __name__ == '__main__':
    unittest.main()
