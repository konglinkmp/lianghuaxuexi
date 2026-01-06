"""
分层策略引擎
实现稳健层和激进层的差异化选股与风控逻辑
"""

from typing import Dict, List
import pandas as pd
from .stock_classifier import (
    stock_classifier,
    STOCK_TYPE_HOT_MONEY,
    STOCK_TYPE_VALUE_TREND,
    LAYER_AGGRESSIVE,
    LAYER_CONSERVATIVE,
)
from .data_fetcher import get_stock_daily_history, get_stock_industry
from .strategy import calculate_ma, calculate_atr
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
            total_capital: 总资金
        """
        self.total_capital = total_capital
        self.conservative_capital = total_capital * CONSERVATIVE_CAPITAL_RATIO
        self.aggressive_capital = total_capital * AGGRESSIVE_CAPITAL_RATIO
    
    def generate_layer_signals(self, stock_pool: pd.DataFrame, 
                                verbose: bool = True) -> Dict:
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
        if verbose:
            print(f"\n[分层策略] 资金分配: 稳健层 ¥{self.conservative_capital:,.0f} | 激进层 ¥{self.aggressive_capital:,.0f}")
        
        conservative_signals = []
        aggressive_signals = []
        
        total = len(stock_pool)
        
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
                
                # 分类股票
                classification = stock_classifier.classify_stock(code, df)
                layer = classification['layer']
                stock_type = classification['type']
                
                # 跳过普通股
                if layer not in [LAYER_AGGRESSIVE, LAYER_CONSERVATIVE]:
                    continue
                
                # 获取最新价格
                latest = df.iloc[-1]
                close_price = latest['close']
                
                # 获取行业信息
                industry = get_stock_industry(code)
                
                # 计算MA20
                ma20 = calculate_ma(df, 20).iloc[-1] if len(df) >= 20 else close_price
                
                # 根据分层获取参数并计算止损止盈
                layer_params = self._get_layer_parameters(layer)
                
                # 计算止损止盈价格
                stop_loss_price = round(close_price * (1 - layer_params['stop_loss']), 2)
                take_profit_price = round(close_price * (1 + layer_params['take_profit']), 2)
                
                # 计算建议仓位
                position_size = self._calculate_position_size(layer, close_price)
                position_amount = position_size * close_price
                
                # 构建信号
                signal = {
                    '代码': code,
                    '名称': name,
                    '板块': industry or '未知',
                    'stock_type': stock_type,
                    'layer': layer,
                    '收盘价': round(close_price, 2),
                    '建议买入价': round(close_price, 2),
                    '止损价': stop_loss_price,
                    '止盈价': take_profit_price,
                    'MA20': round(ma20, 2),
                    '建议股数': position_size,
                    '建议金额': round(position_amount, 2),
                    '仓位比例': f"{layer_params['position_ratio'] * 100:.0f}%",
                    'score': classification['score'],
                    'reasons': '; '.join(classification['reasons'][:2])  # 只保留前2个原因
                }
                
                # 分配到对应层
                if layer == LAYER_AGGRESSIVE:
                    if len(aggressive_signals) < AGGRESSIVE_MAX_POSITIONS:
                        aggressive_signals.append(signal)
                else:
                    if len(conservative_signals) < CONSERVATIVE_MAX_POSITIONS:
                        conservative_signals.append(signal)
                
                # 检查是否已达上限
                if (len(conservative_signals) >= CONSERVATIVE_MAX_POSITIONS and 
                    len(aggressive_signals) >= AGGRESSIVE_MAX_POSITIONS):
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
            'total_signals': len(conservative_signals) + len(aggressive_signals)
        }
        
        return {
            'conservative': conservative_signals,
            'aggressive': aggressive_signals,
            'summary': summary
        }
    
    def _calculate_position_size(self, layer: str, price: float) -> int:
        """
        根据分层计算建议股数
        
        Args:
            layer: 分层类型 AGGRESSIVE/CONSERVATIVE
            price: 股票价格
            
        Returns:
            int: 建议股数（100的整数倍）
        """
        if layer == LAYER_AGGRESSIVE:
            capital = self.aggressive_capital
            position_ratio = AGGRESSIVE_POSITION_RATIO
        else:
            capital = self.conservative_capital
            position_ratio = CONSERVATIVE_POSITION_RATIO
        
        # 计算单笔仓位金额
        position_amount = capital * position_ratio
        
        # 计算股数（向下取整到100股）
        shares = int(position_amount / price / 100) * 100
        
        # 至少100股
        return max(shares, 100)
    
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
