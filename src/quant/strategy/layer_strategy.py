"""
分层策略引擎
实现稳健层和激进层的差异化选股与风控逻辑
"""

from typing import Dict, List, Tuple
import pandas as pd
import numpy as np
from .stock_classifier import (
    stock_classifier,
    STOCK_TYPE_HOT_MONEY,
    STOCK_TYPE_VALUE_TREND,
    LAYER_AGGRESSIVE,
    LAYER_CONSERVATIVE,
)
from .news_risk_analyzer import news_risk_analyzer
import json
import os
from ..trade.position_tracker import position_tracker
from ..core.data_fetcher import get_stock_daily_history, get_stock_industry
from .strategy import calculate_ma, calculate_atr
from ..risk.risk_control import get_risk_control_state
from ..risk.risk_positioning import calculate_position_size, estimate_adv_amount
from ..core.data_fetcher import get_stock_concepts
from config.config import (
    TOTAL_CAPITAL,
    CONSERVATIVE_CAPITAL_RATIO,
    AGGRESSIVE_CAPITAL_RATIO,
    CONSERVATIVE_STOP_LOSS,
    CONSERVATIVE_TAKE_PROFIT,
    CONSERVATIVE_TRAILING_STOP,
    CONSERVATIVE_MAX_POSITIONS,
    CONSERVATIVE_POSITION_RATIO,
    AGGRESSIVE_STOP_LOSS,
    AGGRESSIVE_TAKE_PROFIT,
    AGGRESSIVE_TRAILING_STOP,
    AGGRESSIVE_MAX_POSITIONS,
    AGGRESSIVE_POSITION_RATIO,
    RISK_BUDGET_CONSERVATIVE,
    RISK_BUDGET_AGGRESSIVE,
    MAX_SINGLE_POSITION_RATIO,
    RISK_CONTRIBUTION_LIMIT,
    LIQUIDITY_ADV_LIMIT,
)


class LayerStrategy:
    """
    分层策略引擎
    
    将资金分为两层：
    - 稳健层（70%）：配置价值趋势股，追求稳定收益
    - 激进层（30%）：配置热门资金股，追求超额收益
    """
    
    def __init__(self, total_capital: float = TOTAL_CAPITAL):
        """
        初始化分层策略
        
        Args:
            total_capital: 总资金 (默认值，如果 account_status.json 存在则优先使用)
        """
        self.default_total_capital = total_capital
        self.total_capital = total_capital
        self.conservative_capital = total_capital * CONSERVATIVE_CAPITAL_RATIO
        self.aggressive_capital = total_capital * AGGRESSIVE_CAPITAL_RATIO
        
        # 运行时状态
        self.held_stocks = set()
        self.conservative_used = 0.0
        self.aggressive_used = 0.0
        self.conservative_count = 0
        self.aggressive_count = 0

    def _load_account_status(self):
        """加载账户资金状态"""
        try:
            if os.path.exists("data/account_status.json"):
                with open("data/account_status.json", "r", encoding="utf-8") as f:
                    status = json.load(f)
                    if "current_capital" in status:
                        self.total_capital = float(status["current_capital"])
                        # 重新计算分层资金
                        self.conservative_capital = self.total_capital * CONSERVATIVE_CAPITAL_RATIO
                        self.aggressive_capital = self.total_capital * AGGRESSIVE_CAPITAL_RATIO
                        return True
        except Exception as e:
            print(f"[警告] 读取账户状态失败: {e}")
        return False

    def _load_positions_status(self, stock_pool: pd.DataFrame):
        """
        加载持仓状态并计算已用资金
        需要传入 stock_pool 以便对持仓股票进行分类（判断是稳健层还是激进层）
        """
        self.held_stocks = set()
        self.conservative_used = 0.0
        self.aggressive_used = 0.0
        self.conservative_count = 0
        self.aggressive_count = 0
        
        try:
            if os.path.exists("data/positions.json"):
                with open("data/positions.json", "r", encoding="utf-8") as f:
                    positions = json.load(f)
                    
                for code, pos in positions.items():
                    self.held_stocks.add(code)
                    market_value = pos.get("shares", 0) * pos.get("current_price", 0)
                    
                    # 尝试判断持仓股票的类型
                    # 如果在股票池里，用分类器判断
                    # 如果不在，默认归为稳健层（保守估计）
                    layer = LAYER_CONSERVATIVE
                    
                    # 简单的分类逻辑：如果有 stock_type 字段则直接用，否则尝试分类
                    if "stock_type" in pos: # 假设 positions.json 里未来会存这个
                         if pos["stock_type"] == "HOT_MONEY":
                             layer = LAYER_AGGRESSIVE
                    else:
                        # 尝试从股票池获取信息
                        # 这里为了简化，我们假设如果它符合激进层特征就是激进层
                        # 但因为没有历史数据，这里只能做一个近似估计
                        # 或者我们简单地根据板块判断？
                        # 最稳妥的方式：默认它是稳健层，占用稳健层额度
                        pass

                    if layer == LAYER_AGGRESSIVE:
                        self.aggressive_used += market_value
                        self.aggressive_count += 1
                    else:
                        self.conservative_used += market_value
                        self.conservative_count += 1
                        
        except Exception as e:
            print(f"[警告] 读取持仓状态失败: {e}")
    
    def generate_layer_signals(self, stock_pool: pd.DataFrame,
                                verbose: bool = True,
                                risk_state=None,
                                strength_filter=None,
                                ignore_holdings: bool = False) -> Dict:
        """
        为股票池生成分层交易信号
        
        Args:
            stock_pool: 股票池DataFrame，包含 代码、名称
            verbose: 是否打印进度
            
        Returns:
            Dict: 分层交易信号
                {
                    'conservative': [股票信号列表],
                    'aggressive': [股票信号列表],
                    'summary': {统计信息}
                }
        """
        # 1. 初始化资金和持仓状态
        if not ignore_holdings:
            self._load_account_status()
            self._load_positions_status(stock_pool)
            if verbose:
                print(f"[资金] 总资产: ¥{self.total_capital:,.2f}")
                print(f"[持仓] 已占用: 稳健层 ¥{self.conservative_used:,.2f} ({self.conservative_count}只) | 激进层 ¥{self.aggressive_used:,.2f} ({self.aggressive_count}只)")
        else:
            # 重置为默认状态
            self.total_capital = self.default_total_capital
            self.conservative_capital = self.total_capital * CONSERVATIVE_CAPITAL_RATIO
            self.aggressive_capital = self.total_capital * AGGRESSIVE_CAPITAL_RATIO
            self.held_stocks = set()
            self.conservative_used = 0.0
            self.aggressive_used = 0.0
            self.conservative_count = 0
            self.aggressive_count = 0
            if verbose:
                print(f"[模式] 忽略持仓，使用默认资金配置: ¥{self.total_capital:,.2f}")

        if risk_state is None:
            risk_state = get_risk_control_state(self.total_capital)

        if not risk_state.can_trade:
            if verbose:
                print(f"[风控] {risk_state.summary()}")
                print("⛔ 风控限制：暂停新开仓")
            return {
                "conservative": [],
                "aggressive": [],
                "summary": {
                    "conservative_count": 0,
                    "aggressive_count": 0,
                    "conservative_max": CONSERVATIVE_MAX_POSITIONS,
                    "aggressive_max": AGGRESSIVE_MAX_POSITIONS,
                    "conservative_capital": self.conservative_capital,
                    "aggressive_capital": self.aggressive_capital,
                    "total_signals": 0,
                    "risk_state": risk_state.summary(),
                },
            }

        if verbose:
            print(f"[风控] {risk_state.summary()}")
            print(f"\n[分层策略] 资金分配: 稳健层 ¥{self.conservative_capital:,.0f} | 激进层 ¥{self.aggressive_capital:,.0f}")
        
        conservative_signals = []
        aggressive_signals = []
        
        total = len(stock_pool)
        
        conservative_capital = self.conservative_capital * risk_state.max_total_exposure
        aggressive_capital = self.aggressive_capital * risk_state.max_total_exposure
        
        # 扣除已用资金
        conservative_allocated = self.conservative_used
        aggressive_allocated = self.aggressive_used
        
        # 扣除已用数量
        conservative_signals_count = self.conservative_count
        aggressive_signals_count = self.aggressive_count

        for idx, row in stock_pool.iterrows():
            code = row['代码']
            name = row['名称']
            
            if verbose and (idx + 1) % 50 == 0:
                print(f"[分层进度] {idx + 1}/{total} ({(idx+1)/total*100:.1f}%)")
            
            try:
                # 获取历史数据
                df = get_stock_daily_history(code)
                if df is None or df.empty or len(df) < 25:
                    continue
                
                # 过滤已持仓
                if code in self.held_stocks:
                    continue
                
                # 分类股票
                classification = stock_classifier.classify_stock(code, df)
                layer = classification['layer']
                stock_type = classification['type']

                # 跳过普通股
                if layer not in [LAYER_AGGRESSIVE, LAYER_CONSERVATIVE]:
                    continue

                if layer == LAYER_AGGRESSIVE and aggressive_signals_count >= AGGRESSIVE_MAX_POSITIONS:
                    continue
                if layer == LAYER_CONSERVATIVE and conservative_signals_count >= CONSERVATIVE_MAX_POSITIONS:
                    continue
                
                # 获取最新价格
                latest = df.iloc[-1]
                close_price = latest['close']
                
                # 获取行业信息
                industry = get_stock_industry(code)
                concepts = get_stock_concepts(code)
                industry_ok = concept_ok = False
                strength_label = ""
                if strength_filter is not None:
                    industry_ok, concept_ok, strength_label = strength_filter.strength_flags(
                        industry, concepts
                    )
                    if not strength_filter.is_allowed(industry, concepts, layer=layer):
                        continue
                
                # 计算MA20
                ma20 = calculate_ma(df, 20).iloc[-1] if len(df) >= 20 else close_price
                
                # 根据分层获取参数并计算止损止盈
                layer_params = self._get_layer_parameters(layer)
                
                # 计算止损止盈价格
                stop_loss_price = round(close_price * (1 - layer_params['stop_loss']), 2)
                take_profit_price = round(close_price * (1 + layer_params['take_profit']), 2)
                
                # 计算建议仓位（风险预算）
                layer_max_positions = layer_params['max_positions']
                risk_budget_ratio = (
                    RISK_BUDGET_AGGRESSIVE if layer == LAYER_AGGRESSIVE else RISK_BUDGET_CONSERVATIVE
                )
                remaining_capital = (
                    aggressive_capital - aggressive_allocated
                    if layer == LAYER_AGGRESSIVE
                    else conservative_capital - conservative_allocated
                )
                if remaining_capital <= 0:
                    continue

                adv_amount = estimate_adv_amount(df, close_price)
                size_result = calculate_position_size(
                    price=close_price,
                    stop_loss=stop_loss_price,
                    total_capital=self.total_capital,
                    risk_budget_ratio=risk_budget_ratio,
                    risk_scale=risk_state.risk_scale,
                    max_position_ratio=MAX_SINGLE_POSITION_RATIO,
                    max_positions=layer_max_positions,
                    adv_amount=adv_amount,
                    liquidity_limit=LIQUIDITY_ADV_LIMIT,
                    risk_contribution_limit=RISK_CONTRIBUTION_LIMIT,
                    remaining_capital=remaining_capital,
                )
                position_size = size_result.shares
                if position_size < 100:
                    continue
                position_amount = position_size * close_price

                if layer == LAYER_AGGRESSIVE:
                    aggressive_allocated += position_amount
                else:
                    conservative_allocated += position_amount
                
                # AI 风险分析 (仅对通过初步筛选的股票进行)
                ai_risk = news_risk_analyzer.analyze_risk(code, name)
                
                # 如果是 HIGH 风险，直接剔除
                if ai_risk.get('risk_level') == 'HIGH':
                    if verbose:
                        print(f"[AI风险] {name}({code}) 识别为高风险: {ai_risk.get('risk_reason')}，已剔除")
                    continue

                # 构建信号
                concept_text = "，".join(concepts) if concepts else ""
                signal = {
                    '代码': code,
                    '名称': name,
                    '板块': industry or '未知',
                    '行业名称': industry or '未知',
                    '概念列表': concept_text,
                    '行业强势': "强" if industry_ok else "弱",
                    '概念强势': "强" if concept_ok else "弱",
                    '板块强度': strength_label,
                    'stock_type': stock_type,
                    'layer': layer,
                    '收盘价': round(close_price, 2),
                    '建议买入价': round(close_price, 2),
                    '止损价': stop_loss_price,
                    '止盈价': take_profit_price,
                    'MA20': round(ma20, 2),
                    '建议股数': position_size,
                    '建议金额': round(position_amount, 2),
                    '仓位比例': f"{position_amount / self.total_capital * 100:.1f}%",
                    'score': classification['score'],
                    'reasons': '; '.join(classification['reasons'][:2]),  # 只保留前2个原因
                    'ai_risk_level': ai_risk.get('risk_level', 'LOW'),
                    'ai_risk_reason': ai_risk.get('risk_reason', ''),
                    'ai_risk_details': ai_risk.get('details', '')
                }
                
                # 分配到对应层
                if layer == LAYER_AGGRESSIVE:
                    if aggressive_signals_count < AGGRESSIVE_MAX_POSITIONS:
                        aggressive_signals.append(signal)
                        aggressive_signals_count += 1
                else:
                    if conservative_signals_count < CONSERVATIVE_MAX_POSITIONS:
                        conservative_signals.append(signal)
                        conservative_signals_count += 1
                
                # 检查是否已达上限
                if (conservative_signals_count >= CONSERVATIVE_MAX_POSITIONS and 
                    aggressive_signals_count >= AGGRESSIVE_MAX_POSITIONS):
                    if verbose:
                        print("[分层策略] 两层均已达到最大持仓数，停止分析")
                    break
                    
            except Exception as e:
                if verbose:
                    print(f"[警告] 分析 {code} 时出错: {e}")
                continue
        
        # 按分数排序（高分优先）
        conservative_signals.sort(key=lambda x: x['score'], reverse=True)
        aggressive_signals.sort(key=lambda x: x['score'], reverse=True)
        
        # 构建汇总信息
        summary = {
            'conservative_count': len(conservative_signals),
            'aggressive_count': len(aggressive_signals),
            'conservative_max': CONSERVATIVE_MAX_POSITIONS,
            'aggressive_max': AGGRESSIVE_MAX_POSITIONS,
            'conservative_capital': self.conservative_capital,
            'aggressive_capital': self.aggressive_capital,
            'total_signals': len(conservative_signals) + len(aggressive_signals),
            'risk_state': risk_state.summary(),
        }
        
        return {
            'conservative': conservative_signals,
            'aggressive': aggressive_signals,
            'summary': summary
        }
    
    def _get_layer_parameters(self, layer: str) -> Dict:
        """
        获取对应分层的风控参数
        
        Args:
            layer: 分层类型
            
        Returns:
            Dict: 风控参数
        """
        if layer == LAYER_AGGRESSIVE:
            return {
                'stop_loss': AGGRESSIVE_STOP_LOSS,
                'take_profit': AGGRESSIVE_TAKE_PROFIT,
                'trailing_stop': AGGRESSIVE_TRAILING_STOP,
                'max_positions': AGGRESSIVE_MAX_POSITIONS,
                'position_ratio': AGGRESSIVE_POSITION_RATIO,
                'layer_name': '激进层',
                'layer_emoji': '🚀'
            }
        else:
            return {
                'stop_loss': CONSERVATIVE_STOP_LOSS,
                'take_profit': CONSERVATIVE_TAKE_PROFIT,
                'trailing_stop': CONSERVATIVE_TRAILING_STOP,
                'max_positions': CONSERVATIVE_MAX_POSITIONS,
                'position_ratio': CONSERVATIVE_POSITION_RATIO,
                'layer_name': '稳健层',
                'layer_emoji': '💰'
            }
    
    def format_layer_plans(self, layer_signals: Dict) -> pd.DataFrame:
        """
        将分层信号格式化为DataFrame
        
        Args:
            layer_signals: generate_layer_signals 的返回值
            
        Returns:
            DataFrame: 合并后的交易计划
        """
        all_plans = []
        
        # 添加稳健层
        for signal in layer_signals['conservative']:
            all_plans.append(signal)
        
        # 添加激进层
        for signal in layer_signals['aggressive']:
            all_plans.append(signal)
        
        if not all_plans:
            return pd.DataFrame()
        
        return pd.DataFrame(all_plans)
    
    def check_layer_correlation(
        self,
        conservative_stocks: List[str],
        aggressive_stocks: List[str],
        lookback_days: int = 60
    ) -> Dict:
        """
        检测稳健层和激进层股票的相关性
        
        如果两层股票高度相关，在大跌时可能同时亏损，无法分散风险
        
        Args:
            conservative_stocks: 稳健层股票代码列表
            aggressive_stocks: 激进层股票代码列表
            lookback_days: 相关性计算回看天数
            
        Returns:
            Dict: {
                'avg_correlation': float,  # 平均相关系数
                'risk_level': 'HIGH' | 'MEDIUM' | 'LOW',
                'warning': str,  # 警告信息
                'detail': str   # 详细说明
            }
        """
        if not conservative_stocks or not aggressive_stocks:
            return {
                'avg_correlation': 0.0,
                'risk_level': 'LOW',
                'warning': '',
                'detail': '单层股票不足，跳过相关性检测'
            }
        
        # 收集收益率序列
        all_returns = {}
        
        for code in conservative_stocks + aggressive_stocks:
            try:
                df = get_stock_daily_history(code, days=lookback_days + 10)
                if df is not None and len(df) >= lookback_days:
                    returns = df['close'].pct_change().dropna().tail(lookback_days)
                    all_returns[code] = returns
            except Exception:
                continue
        
        if len(all_returns) < 2:
            return {
                'avg_correlation': 0.0,
                'risk_level': 'LOW',
                'warning': '',
                'detail': '有效数据不足，跳过相关性检测'
            }
        
        # 计算跨层相关性
        correlations = []
        
        for cons_code in conservative_stocks:
            if cons_code not in all_returns:
                continue
            for aggr_code in aggressive_stocks:
                if aggr_code not in all_returns:
                    continue
                
                try:
                    cons_returns = all_returns[cons_code]
                    aggr_returns = all_returns[aggr_code]
                    
                    # 对齐索引
                    common_idx = cons_returns.index.intersection(aggr_returns.index)
                    if len(common_idx) < 20:
                        continue
                    
                    corr = cons_returns.loc[common_idx].corr(aggr_returns.loc[common_idx])
                    if not np.isnan(corr):
                        correlations.append(corr)
                except Exception:
                    continue
        
        if not correlations:
            return {
                'avg_correlation': 0.0,
                'risk_level': 'LOW',
                'warning': '',
                'detail': '无法计算相关性'
            }
        
        avg_corr = np.mean(correlations)
        
        # 评估风险等级
        if avg_corr > 0.7:
            risk_level = 'HIGH'
            warning = f'⚠️ 层间相关性过高 ({avg_corr:.2f})，分散效果有限'
            detail = '稳健层和激进层股票高度相关，在市场下跌时可能同时亏损。建议选择相关性更低的股票。'
        elif avg_corr > 0.5:
            risk_level = 'MEDIUM'
            warning = f'⚠️ 层间相关性偏高 ({avg_corr:.2f})'
            detail = '两层股票存在一定相关性，分散效果一般。'
        else:
            risk_level = 'LOW'
            warning = ''
            detail = f'层间相关性正常 ({avg_corr:.2f})，分散效果良好。'
        
        return {
            'avg_correlation': round(avg_corr, 3),
            'risk_level': risk_level,
            'warning': warning,
            'detail': detail
        }


# 创建全局策略实例
layer_strategy = LayerStrategy()


if __name__ == "__main__":
    # 测试
    from .stock_pool import get_final_pool
    
    print("测试分层策略引擎...")
    
    # 获取一小部分股票测试
    pool = get_final_pool(use_custom=False, skip_new_stock_filter=True)
    test_pool = pool.head(50)
    
    signals = layer_strategy.generate_layer_signals(test_pool, verbose=True)
    
    print(f"\n稳健层推荐: {signals['summary']['conservative_count']}只")
    for s in signals['conservative']:
        print(f"  {s['名称']} ({s['代码']}) - {s['stock_type']}")
    
    print(f"\n激进层推荐: {signals['summary']['aggressive_count']}只")
    for s in signals['aggressive']:
        print(f"  {s['名称']} ({s['代码']}) - {s['stock_type']}")
