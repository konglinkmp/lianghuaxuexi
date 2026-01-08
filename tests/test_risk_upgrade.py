
import sys
import os
import pandas as pd
import unittest
from unittest.mock import MagicMock, patch

# 添加 src 到路径
sys.path.append(os.path.join(os.getcwd(), 'src'))

from quant.risk.portfolio_risk import PortfolioRiskManager
from config.config import MAX_INDUSTRY_POSITION_RATIO, TOTAL_CAPITAL

class TestPortfolioRisk(unittest.TestCase):
    def setUp(self):
        self.manager = PortfolioRiskManager(total_capital=100000)
        
    def test_industry_concentration_limit(self):
        # 模拟当前持仓: 2.5万 半导体
        current_positions = {
            '000001': {'market_value': 25000, 'industry': '半导体'}
        }
        
        # 计划再买入 1万 半导体
        # 总计 = 3.5万 > 3万 (10万的30%) -> 应该被拒绝
        planned_buys = [
            {'代码': '000002', '行业名称': '半导体', '建议金额': 10000}
        ]
        
        passed, reason, rejected = self.manager.check_industry_concentration(current_positions, planned_buys)
        
        print(f"\n[测试] 行业集中度检查: {reason}")
        self.assertFalse(passed)
        self.assertIn('000002', rejected)
        
    def test_industry_concentration_pass(self):
        # 模拟当前持仓: 1万 半导体
        current_positions = {
            '000001': {'market_value': 10000, 'industry': '半导体'}
        }
        
        # 计划再买入 1万 半导体
        # 总计 = 2万 < 3万 -> 应该通过
        planned_buys = [
            {'代码': '000002', '行业名称': '半导体', '建议金额': 10000}
        ]
        
        passed, reason, rejected = self.manager.check_industry_concentration(current_positions, planned_buys)
        
        print(f"\n[测试] 行业集中度检查(通过): {reason}")
        self.assertTrue(passed)
        self.assertEqual(len(rejected), 0)

    @patch('quant.risk.portfolio_risk.get_stock_daily_history')
    def test_correlation_risk(self, mock_get_history):
        # 模拟3只股票的历史数据
        # A 和 B 高度相关，C 不相关
        dates = pd.date_range(start='2024-01-01', periods=100)
        
        # 股票 A: 线性增长
        df_a = pd.DataFrame({'close': [10 + i*0.1 for i in range(100)]}, index=dates)
        
        # 股票 B: 类似 A (高相关)
        df_b = pd.DataFrame({'close': [20 + i*0.2 + (i%2)*0.01 for i in range(100)]}, index=dates)
        
        # 股票 C: 随机/正弦波 (低相关)
        import numpy as np
        df_c = pd.DataFrame({'close': [15 + np.sin(i) for i in range(100)]}, index=dates)
        
        def side_effect(code, days=None):
            if code == 'A': return df_a
            if code == 'B': return df_b
            if code == 'C': return df_c
            return None
            
        mock_get_history.side_effect = side_effect
        
        # 用例 1: A 和 B -> 高相关
        passed, warning, avg_corr = self.manager.check_correlation_risk(['A'], ['B'])
        print(f"\n[测试] 相关性检查(高相关): {avg_corr:.2f} - {warning}")
        self.assertFalse(passed)
        self.assertGreater(avg_corr, 0.7)
        
        # 用例 2: A 和 C -> 低相关
        passed, warning, avg_corr = self.manager.check_correlation_risk(['A'], ['C'])
        print(f"\n[测试] 相关性检查(低相关): {avg_corr:.2f} - {warning}")
        self.assertTrue(passed)
        self.assertLess(avg_corr, 0.7)

if __name__ == '__main__':
    unittest.main()
