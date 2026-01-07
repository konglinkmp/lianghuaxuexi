"""
幸存者偏差检测模块
检测回测数据是否存在幸存者偏差风险，并生成警告信息
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
import pandas as pd


@dataclass
class SurvivorshipBiasResult:
    """幸存者偏差检测结果"""
    has_risk: bool
    risk_level: str  # 'HIGH', 'MEDIUM', 'LOW'
    message: str
    recommendation: str
    details: dict

    def to_dict(self) -> dict:
        return {
            'has_risk': self.has_risk,
            'risk_level': self.risk_level,
            'message': self.message,
            'recommendation': self.recommendation,
            'details': self.details
        }


class SurvivorshipBiasChecker:
    """
    幸存者偏差检测器
    
    检测逻辑：
    1. 分析回测起始日期与当前日期的时间跨度
    2. 估算该时间段内可能的退市股票数量
    3. 根据时间跨度和市场情况评估风险等级
    """
    
    # 历史退市数据统计（近似值，用于估算）
    # 数据来源：A股历史退市公告统计
    HISTORICAL_DELIST_RATE = {
        2020: 16,  # 2020年退市公司数
        2021: 20,
        2022: 42,
        2023: 45,
        2024: 52,
        2025: 30,  # 预估
    }
    
    def __init__(self):
        pass
    
    def check(
        self,
        stock_pool: pd.DataFrame,
        backtest_start: str,
        backtest_end: Optional[str] = None
    ) -> SurvivorshipBiasResult:
        """
        检查回测是否存在幸存者偏差风险
        
        Args:
            stock_pool: 回测使用的股票池
            backtest_start: 回测起始日期（格式：YYYY-MM-DD）
            backtest_end: 回测结束日期，默认为今天
            
        Returns:
            SurvivorshipBiasResult: 检测结果
        """
        try:
            start_date = datetime.strptime(backtest_start, '%Y-%m-%d')
        except ValueError:
            start_date = datetime.strptime(backtest_start, '%Y%m%d')
        
        end_date = datetime.now() if backtest_end is None else datetime.strptime(backtest_end, '%Y-%m-%d')
        
        # 计算回测跨度（年）
        years_span = (end_date - start_date).days / 365.0
        
        # 估算期间退市股票数量
        estimated_delisted = self._estimate_delisted_count(start_date, end_date)
        
        # 计算股票池规模
        pool_size = len(stock_pool) if stock_pool is not None else 0
        
        # 评估风险等级
        risk_level, message, recommendation = self._evaluate_risk(
            years_span, estimated_delisted, pool_size
        )
        
        return SurvivorshipBiasResult(
            has_risk=risk_level in ['HIGH', 'MEDIUM'],
            risk_level=risk_level,
            message=message,
            recommendation=recommendation,
            details={
                'backtest_start': start_date.strftime('%Y-%m-%d'),
                'backtest_end': end_date.strftime('%Y-%m-%d'),
                'years_span': round(years_span, 2),
                'estimated_delisted_stocks': estimated_delisted,
                'pool_size': pool_size,
                'data_source': 'AKShare (仅含存续股票)'
            }
        )
    
    def _estimate_delisted_count(self, start: datetime, end: datetime) -> int:
        """估算期间退市股票数量"""
        total = 0
        for year in range(start.year, end.year + 1):
            yearly_count = self.HISTORICAL_DELIST_RATE.get(year, 30)  # 默认30
            # 根据月份调整（如果不是完整年份）
            if year == start.year:
                months = 12 - start.month + 1
                yearly_count = int(yearly_count * months / 12)
            if year == end.year:
                months = end.month
                yearly_count = int(yearly_count * months / 12)
            total += yearly_count
        return total
    
    def _evaluate_risk(
        self,
        years_span: float,
        estimated_delisted: int,
        pool_size: int
    ) -> tuple:
        """评估风险等级"""
        
        # 风险评估规则
        if years_span >= 3 or estimated_delisted >= 50:
            return (
                'HIGH',
                f'⚠️ 幸存者偏差风险【高】\n'
                f'   回测跨度 {years_span:.1f} 年，期间约 {estimated_delisted} 只股票退市。\n'
                f'   这些退市股票未纳入回测，实际收益率可能被高估 20-30%。',
                '强烈建议接入包含退市股票的专业数据源（如 Tushare Pro）进行验证。'
            )
        elif years_span >= 1 or estimated_delisted >= 20:
            return (
                'MEDIUM',
                f'⚠️ 幸存者偏差风险【中】\n'
                f'   回测跨度 {years_span:.1f} 年，期间约 {estimated_delisted} 只股票退市。\n'
                f'   部分历史踩雷股票未纳入回测。',
                '建议对比不同时间段的回测结果，关注策略稳定性。'
            )
        else:
            return (
                'LOW',
                f'✅ 幸存者偏差风险【低】\n'
                f'   回测跨度 {years_span:.1f} 年，期间约 {estimated_delisted} 只股票退市。\n'
                f'   短期回测影响较小。',
                '回测结果相对可靠，但仍建议定期验证。'
            )
    
    def format_warning(self, result: SurvivorshipBiasResult) -> str:
        """格式化警告信息用于报告输出"""
        lines = [
            '',
            '=' * 60,
            '📊 幸存者偏差风险评估',
            '=' * 60,
            result.message,
            '',
            f'💡 建议: {result.recommendation}',
            '',
            '📋 详细信息:',
            f'   - 回测起止: {result.details["backtest_start"]} → {result.details["backtest_end"]}',
            f'   - 回测跨度: {result.details["years_span"]} 年',
            f'   - 估算退市: ~{result.details["estimated_delisted_stocks"]} 只',
            f'   - 数据来源: {result.details["data_source"]}',
            '=' * 60,
        ]
        return '\n'.join(lines)


# 全局实例
survivorship_checker = SurvivorshipBiasChecker()


if __name__ == '__main__':
    # 测试
    import pandas as pd
    
    test_pool = pd.DataFrame({'代码': ['000001', '000002', '600000']})
    result = survivorship_checker.check(test_pool, '2022-01-01')
    
    print(survivorship_checker.format_warning(result))
