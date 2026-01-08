
import sys
import os
import pandas as pd
import unittest
from unittest.mock import MagicMock, patch

# 添加 src 到路径
sys.path.append(os.path.join(os.getcwd(), 'src'))

from quant.analysis.intraday_monitor import IntradayMonitor

class TestIntradayMonitor(unittest.TestCase):
    def setUp(self):
        self.monitor = IntradayMonitor()
        
    @patch('quant.analysis.intraday_monitor.get_stock_daily_history')
    def test_1400_dive_detection(self, mock_get_history):
        # 模拟昨日数据：冲高回落，尾盘跳水
        # Open=10, High=10.5 (+5%), Close=10.1 (+1%), Low=10.0
        # 满足 High > Open * 1.03
        # Dive Pct = (10.1 / 10.5) - 1 = -3.8% < -2%
        # Close near Low: (10.1 - 10.0) / (10.5 - 10.0) = 0.2 < 0.3
        
        df_dive = pd.DataFrame({
            'open': [10.0],
            'high': [10.5],
            'low': [10.0],
            'close': [10.1]
        })
        
        mock_get_history.return_value = df_dive
        
        result = self.monitor.check_1400_dive('000001')
        print(f"\n[测试] 尾盘跳水检测: {result['warning']}")
        self.assertTrue(result['has_dive'])
        self.assertLess(result['dive_pct'], -0.02)
        
    def test_auction_anomaly(self):
        # 模拟大幅高开
        # PreClose=10, Open=10.5 (+5%)
        result = self.monitor.check_auction_anomaly('000001', 10.5, 10.0)
        print(f"\n[测试] 竞价异常检测(高开): {result['warning']}")
        self.assertTrue(result['is_anomaly'])
        
        # 模拟正常开盘
        # PreClose=10, Open=10.1 (+1%)
        result = self.monitor.check_auction_anomaly('000001', 10.1, 10.0)
        print(f"\n[测试] 竞价异常检测(正常): {result['warning']}")
        self.assertFalse(result['is_anomaly'])

if __name__ == '__main__':
    unittest.main()
