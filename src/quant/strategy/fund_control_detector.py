"""
资金流向评分模块
评估主力资金活跃度，作为正向加分项

主力资金活跃特征（正向信号）：
1. 成交量放大：成交量大于2倍均量
2. 换手率活跃：换手率>5%
3. 价格强势：站上MA20且放量
4. 主力资金净流入：通过akshare资金流向接口

@author saiki
"""

import pandas as pd
import numpy as np
from typing import Dict, List
from datetime import datetime
import logging
import akshare as ak
from ..core.data_fetcher import get_stock_daily_history, get_stock_turnover_rate
from .strategy import calculate_ma
from config.config import HISTORY_DAYS

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FundFlowScorer:
    """
    资金流向评分器

    通过多维度分析评估主力资金活跃度：
    - 成交量分析：放量程度
    - 换手率分析：交投活跃度
    - 价格趋势：强势特征
    - 资金流向：主力资金净流入
    """

    def __init__(self):
        """初始化评分器"""
        # 评分参数
        self.volume_amplify_threshold = 2.0   # 成交量放大倍数阈值
        self.turnover_active_threshold = 5.0  # 活跃换手率阈值(%)
        self.volume_amplify_score = 5         # 成交量放大加分
        self.turnover_active_score = 5        # 换手率活跃加分
        self.price_strong_score = 5           # 价格强势加分
        self.main_fund_inflow_score = 10      # 主力资金净流入加分

    def calculate_score(self, symbol: str, df: pd.DataFrame = None) -> Dict:
        """
        计算股票的资金流向评分

        Args:
            symbol: 股票代码
            df: 历史数据DataFrame，如果为None则自动获取

        Returns:
            Dict: 评分结果
                {
                    'fund_flow_score': float,   # 资金流向总分 (0-25)
                    'reasons': List[str],       # 加分原因列表
                    'details': Dict             # 各项评分详情
                }
        """
        result = {
            'fund_flow_score': 0.0,
            'reasons': [],
            'details': {}
        }

        try:
            # 获取历史数据
            if df is None or df.empty:
                df = get_stock_daily_history(symbol, days=HISTORY_DAYS)
                if df is None or df.empty:
                    return result

            if len(df) < 20:
                return result

            total_score = 0.0

            # 1. 成交量放大评分
            volume_result = self._score_volume_amplify(df)
            result['details']['volume'] = volume_result
            if volume_result['score'] > 0:
                total_score += volume_result['score']
                result['reasons'].append(volume_result['reason'])

            # 2. 换手率活跃评分
            turnover_result = self._score_turnover_active(symbol)
            result['details']['turnover'] = turnover_result
            if turnover_result['score'] > 0:
                total_score += turnover_result['score']
                result['reasons'].append(turnover_result['reason'])

            # 3. 价格强势评分
            price_result = self._score_price_strong(df)
            result['details']['price'] = price_result
            if price_result['score'] > 0:
                total_score += price_result['score']
                result['reasons'].append(price_result['reason'])

            # 4. 主力资金净流入评分
            fund_result = self._score_main_fund_inflow(symbol)
            result['details']['main_fund'] = fund_result
            if fund_result['score'] > 0:
                total_score += fund_result['score']
                result['reasons'].append(fund_result['reason'])

            result['fund_flow_score'] = total_score
            return result

        except Exception as e:
            logger.warning(f"计算 {symbol} 资金流向评分失败: {e}")
            return result

    def _score_volume_amplify(self, df: pd.DataFrame) -> Dict:
        """
        成交量放大评分

        成交量 > 2倍20日均量：+5分
        """
        result = {'score': 0.0, 'reason': '', 'ratio': 0.0}

        try:
            if len(df) < 20:
                return result

            current_volume = df['volume'].iloc[-1]
            avg_volume = df['volume'].iloc[-21:-1].mean()

            if avg_volume > 0:
                ratio = current_volume / avg_volume
                result['ratio'] = round(ratio, 2)

                if ratio >= self.volume_amplify_threshold:
                    result['score'] = self.volume_amplify_score
                    result['reason'] = f"成交量放大{ratio:.1f}倍"

        except Exception as e:
            logger.debug(f"成交量评分失败: {e}")

        return result

    def _score_turnover_active(self, symbol: str) -> Dict:
        """
        换手率活跃评分

        换手率 > 5%：+5分
        """
        result = {'score': 0.0, 'reason': '', 'turnover': 0.0}

        try:
            turnover = get_stock_turnover_rate(symbol)
            result['turnover'] = turnover

            if turnover >= self.turnover_active_threshold:
                result['score'] = self.turnover_active_score
                result['reason'] = f"换手率活跃{turnover:.1f}%"

        except Exception as e:
            logger.debug(f"换手率评分失败: {e}")

        return result

    def _score_price_strong(self, df: pd.DataFrame) -> Dict:
        """
        价格强势评分

        站上MA20且放量：+5分
        """
        result = {'score': 0.0, 'reason': '', 'above_ma20': False}

        try:
            if len(df) < 20:
                return result

            ma20 = calculate_ma(df, 20).iloc[-1]
            close = df['close'].iloc[-1]
            
            # 检查是否站上MA20
            above_ma20 = close > ma20
            result['above_ma20'] = above_ma20

            # 检查是否放量
            current_volume = df['volume'].iloc[-1]
            avg_volume = df['volume'].iloc[-21:-1].mean()
            is_volume_up = current_volume > avg_volume * 1.2

            if above_ma20 and is_volume_up:
                result['score'] = self.price_strong_score
                result['reason'] = f"站上MA20且放量"

        except Exception as e:
            logger.debug(f"价格强势评分失败: {e}")

        return result

    def _score_main_fund_inflow(self, symbol: str) -> Dict:
        """
        主力资金净流入评分

        使用akshare获取主力资金流向数据
        主力净流入 > 0：+10分
        """
        result = {'score': 0.0, 'reason': '', 'net_inflow': 0.0}

        try:
            # 获取个股资金流向数据
            # 使用 stock_individual_fund_flow 接口
            df_fund = ak.stock_individual_fund_flow(stock=symbol, market="sh" if symbol.startswith('6') else "sz")
            
            if df_fund is not None and not df_fund.empty:
                # 获取最近一日的主力净流入
                # 列名可能是 '主力净流入-净额' 或类似
                latest = df_fund.iloc[-1]
                
                # 尝试不同的列名
                net_inflow = 0.0
                for col in ['主力净流入-净额', '主力净流入', '超大单净流入', '大单净流入']:
                    if col in df_fund.columns:
                        val = latest.get(col, 0)
                        if pd.notna(val):
                            net_inflow = float(val)
                            break
                
                result['net_inflow'] = net_inflow

                if net_inflow > 0:
                    result['score'] = self.main_fund_inflow_score
                    # 转换为万
                    net_inflow_wan = net_inflow / 10000
                    result['reason'] = f"主力资金净流入{net_inflow_wan:.0f}万"

        except Exception as e:
            logger.debug(f"主力资金流向获取失败: {e}")

        return result

    def batch_score(self, symbols: List[str], verbose: bool = False) -> pd.DataFrame:
        """
        批量计算资金流向评分

        Args:
            symbols: 股票代码列表
            verbose: 是否打印进度

        Returns:
            DataFrame: 评分结果
        """
        results = []

        for i, symbol in enumerate(symbols):
            if verbose and (i + 1) % 20 == 0:
                print(f"[资金流向评分进度] {i + 1}/{len(symbols)} ({(i+1)/len(symbols)*100:.1f}%)")

            try:
                score_result = self.calculate_score(symbol)
                results.append({
                    '代码': symbol,
                    'fund_flow_score': score_result['fund_flow_score'],
                    'reasons': '; '.join(score_result['reasons'])
                })
            except Exception as e:
                logger.warning(f"批量评分 {symbol} 失败: {e}")
                results.append({
                    '代码': symbol,
                    'fund_flow_score': 0.0,
                    'reasons': f'评分失败: {e}'
                })

        return pd.DataFrame(results)


# 创建全局评分器实例
fund_flow_scorer = FundFlowScorer()


def get_fund_flow_score(symbol: str, df: pd.DataFrame = None) -> float:
    """
    获取股票的资金流向评分（便捷函数）

    Args:
        symbol: 股票代码
        df: 历史数据（可选）

    Returns:
        float: 资金流向评分 (0-25)
    """
    result = fund_flow_scorer.calculate_score(symbol, df)
    return result['fund_flow_score']


if __name__ == "__main__":
    # 测试资金流向评分器
    print("测试资金流向评分器...")

    test_symbols = ['000001', '600519', '300750']

    for symbol in test_symbols:
        print(f"\n评分 {symbol}...")
        result = fund_flow_scorer.calculate_score(symbol)
        print(f"  资金流向总分: {result['fund_flow_score']}")
        print(f"  加分原因: {result['reasons']}")
        print(f"  评分详情: {result['details']}")
