"""
组合风控模块
实现行业集中度限制和持仓相关性检查
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
from ..core.data_fetcher import get_stock_industry, get_stock_daily_history
from config.config import (
    MAX_INDUSTRY_POSITION_RATIO,
    MAX_CORRELATION_THRESHOLD,
    CORRELATION_LOOKBACK_DAYS,
    TOTAL_CAPITAL
)

class PortfolioRiskManager:
    """
    组合风控管理器
    """
    
    def __init__(self, total_capital: float = TOTAL_CAPITAL):
        self.total_capital = total_capital

    def check_industry_concentration(
        self, 
        current_positions: Dict, 
        planned_buys: List[Dict]
    ) -> Tuple[bool, str, List[str]]:
        """
        检查行业集中度
        
        Args:
            current_positions: 当前持仓字典 {code: {market_value: float, industry: str, ...}}
            planned_buys: 计划买入列表 [{code, industry, amount, ...}]
            
        Returns:
            (是否通过, 拒绝原因, 被拒绝的股票代码列表)
        """
        # 1. 统计当前各行业持仓市值
        industry_exposure = {}
        
        # 处理当前持仓
        for code, pos in current_positions.items():
            industry = pos.get('industry', '未知')
            # 如果持仓信息里没有行业，尝试获取
            if industry == '未知':
                industry = get_stock_industry(code) or '未知'
                
            market_value = pos.get('market_value', 0.0)
            if market_value == 0:
                # 尝试用 shares * current_price
                market_value = pos.get('shares', 0) * pos.get('current_price', 0)
                
            industry_exposure[industry] = industry_exposure.get(industry, 0.0) + market_value

        # 2. 模拟加入计划买入后的行业分布
        rejected_stocks = []
        limit_amount = self.total_capital * MAX_INDUSTRY_POSITION_RATIO
        
        # 按计划顺序逐个检查
        # 注意：这里是一个简单的贪心检查，如果前面的买入导致行业满额，后面的同行业股票会被拒绝
        
        # 先复制一份当前的行业敞口，用于模拟
        simulated_exposure = industry_exposure.copy()
        
        for plan in planned_buys:
            code = plan.get('代码')
            industry = plan.get('行业名称') or plan.get('板块') or '未知'
            amount = plan.get('建议金额', 0.0)
            
            current_ind_val = simulated_exposure.get(industry, 0.0)
            
            # 检查是否超限
            if current_ind_val + amount > limit_amount:
                rejected_stocks.append(code)
                # 不更新 simulated_exposure，因为这个买入被拒绝了
            else:
                simulated_exposure[industry] = current_ind_val + amount
        
        if rejected_stocks:
            return False, f"行业集中度超限 (> {MAX_INDUSTRY_POSITION_RATIO*100:.0f}%)", rejected_stocks
            
        return True, "行业集中度正常", []

    def check_correlation_risk(
        self, 
        current_positions: List[str], 
        planned_buys: List[str]
    ) -> Tuple[bool, str, float]:
        """
        检查持仓相关性风险
        
        Args:
            current_positions: 当前持仓股票代码列表
            planned_buys: 计划买入股票代码列表
            
        Returns:
            (是否通过, 警告信息, 平均相关系数)
        """
        all_codes = list(set(current_positions + planned_buys))
        if len(all_codes) < 2:
            return True, "标的过少，无需检查相关性", 0.0
            
        # 获取历史收益率数据
        returns_dict = {}
        for code in all_codes:
            df = get_stock_daily_history(code, days=CORRELATION_LOOKBACK_DAYS + 10)
            if df is not None and not df.empty and len(df) >= CORRELATION_LOOKBACK_DAYS:
                # 计算日收益率
                ret = df['close'].pct_change().dropna().tail(CORRELATION_LOOKBACK_DAYS)
                returns_dict[code] = ret
                
        if len(returns_dict) < 2:
            return True, "有效历史数据不足", 0.0
            
        # 构建收益率矩阵
        df_returns = pd.DataFrame(returns_dict)
        
        # 计算相关系数矩阵
        corr_matrix = df_returns.corr()
        
        # 提取上三角矩阵（不含对角线）的平均值
        # np.triu_indices_from(corr_matrix, k=1) 获取上三角索引
        upper_indices = np.triu_indices_from(corr_matrix, k=1)
        correlations = corr_matrix.values[upper_indices]
        
        if len(correlations) == 0:
            return True, "无法计算相关性", 0.0
            
        avg_corr = np.mean(correlations)
        
        if avg_corr > MAX_CORRELATION_THRESHOLD:
            return False, f"组合平均相关性过高 ({avg_corr:.2f} > {MAX_CORRELATION_THRESHOLD})", avg_corr
            
        return True, f"组合相关性正常 ({avg_corr:.2f})", avg_corr

# 全局实例
portfolio_risk_manager = PortfolioRiskManager()
