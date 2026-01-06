"""
股票分类器模块
根据多维度特征将股票分类为：热门资金股、价值趋势股、普通股
"""

import os
from typing import Dict, List, Set
import pandas as pd
from ..core.data_fetcher import (
    get_stock_fundamental,
    get_stock_turnover_rate,
    get_stock_concepts,
    calculate_momentum,
    calculate_volume_ratio,
)
from .fund_control_detector import get_fund_flow_score
from .strategy import calculate_ma
from .technical_indicators import get_macd_score
from config.config import (
    HOT_STOCK_MIN_PE,
    HOT_STOCK_MIN_TURNOVER,
    HOT_STOCK_MIN_MOMENTUM,
    HOT_STOCK_VOLUME_RATIO,
    VALUE_STOCK_MAX_PE,
    VALUE_STOCK_MAX_PB,
    VALUE_STOCK_MIN_VOLUME_RATIO,
    HOT_CONCEPTS_FILE,
)


# 股票类型常量
STOCK_TYPE_HOT_MONEY = "HOT_MONEY"       # 热门资金股
STOCK_TYPE_VALUE_TREND = "VALUE_TREND"   # 价值趋势股
STOCK_TYPE_NORMAL = "NORMAL"             # 普通股

# 分层常量
LAYER_AGGRESSIVE = "AGGRESSIVE"           # 激进层
LAYER_CONSERVATIVE = "CONSERVATIVE"       # 稳健层
LAYER_NONE = "NONE"                       # 不参与


class StockClassifier:
    """
    股票分类器
    
    根据以下特征自动分类股票：
    - 热门资金股：高PE+高换手率 或 强动量 或 巨量放大 或 热门概念
    - 价值趋势股：合理估值+站上均线+温和放量
    - 普通股：不符合以上条件
    """
    
    def __init__(self):
        """初始化分类器"""
        self.hot_concepts = self._load_hot_concepts()
    
    def _load_hot_concepts(self) -> Set[str]:
        """
        从配置文件加载热门概念列表
        
        Returns:
            Set[str]: 热门概念集合
        """
        concepts = set()
        
        # 尝试从配置文件加载
        file_path = HOT_CONCEPTS_FILE
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        # 跳过空行和注释
                        if line and not line.startswith('#'):
                            concepts.add(line)
            except Exception:
                pass
        
        # 默认热门概念（兜底）
        if not concepts:
            concepts = {
                '人工智能', '半导体', '军工航天', '新能源车',
                '数据要素', '算力租赁', '华为概念', '机器人', '创新药'
            }
        
        return concepts
    
    def classify_stock(self, symbol: str, price_data: pd.DataFrame) -> Dict:
        """
        对单只股票进行分类
        
        Args:
            symbol: 股票代码
            price_data: 历史价格数据DataFrame（包含close, volume等）
            
        Returns:
            Dict: 分类结果
                {
                    'type': 'HOT_MONEY' | 'VALUE_TREND' | 'NORMAL',
                    'score': float,  # 分类置信度分数 0-100
                    'reasons': list, # 分类原因列表
                    'layer': 'AGGRESSIVE' | 'CONSERVATIVE' | 'NONE'
                }
        """
        result = {
            'type': STOCK_TYPE_NORMAL,
            'score': 0.0,
            'reasons': [],
            'layer': LAYER_NONE
        }
        
        if price_data is None or price_data.empty:
            result['reasons'].append('无价格数据')
            return result
        
        # 检查是否为热门资金股
        hot_result = self._is_hot_money_stock(symbol, price_data)
        if hot_result['is_hot']:
            result['type'] = STOCK_TYPE_HOT_MONEY
            result['score'] = hot_result['score']
            result['reasons'] = hot_result['reasons']
            result['layer'] = LAYER_AGGRESSIVE
            return result
        
        # 检查是否为价值趋势股
        value_result = self._is_value_trend_stock(symbol, price_data)
        if value_result['is_value']:
            result['type'] = STOCK_TYPE_VALUE_TREND
            result['score'] = value_result['score']
            result['reasons'] = value_result['reasons']
            result['layer'] = LAYER_CONSERVATIVE
            return result
        
        # 普通股
        result['reasons'].append('不符合热门资金股或价值趋势股条件')
        return result
    
    def _is_hot_money_stock(self, symbol: str, df: pd.DataFrame) -> Dict:
        """
        判断是否为热门资金股
        
        满足以下任一条件即可：
        1. PE > 80 且 换手率 > 8%
        2. 10日动量 > 25%
        3. 成交量 > 3倍均量
        4. 属于热门概念板块
        
        Args:
            symbol: 股票代码
            df: 历史价格数据
            
        Returns:
            Dict: {'is_hot': bool, 'score': float, 'reasons': list}
        """
        result = {'is_hot': False, 'score': 0.0, 'reasons': []}
        score = 0.0
        
        # 获取基本面数据
        fundamental = get_stock_fundamental(symbol)
        pe = fundamental.get('pe')
        
        # 获取换手率
        turnover = get_stock_turnover_rate(symbol)
        
        # 计算动量
        momentum = calculate_momentum(df, days=10)
        
        # 计算成交量放大倍数
        volume_ratio = calculate_volume_ratio(df, period=20)
        
        # 条件1：高PE + 高换手率
        if pe is not None and pe > HOT_STOCK_MIN_PE and turnover > HOT_STOCK_MIN_TURNOVER:
            score += 30
            result['reasons'].append(f'高PE({pe:.1f})+高换手率({turnover:.1f}%)')
        
        # 条件2：强动量
        if momentum > HOT_STOCK_MIN_MOMENTUM:
            score += 35
            result['reasons'].append(f'10日涨幅强劲({momentum:.1f}%)')
        
        # 条件3：巨量放大
        if volume_ratio > HOT_STOCK_VOLUME_RATIO:
            score += 25
            result['reasons'].append(f'成交量异常放大({volume_ratio:.1f}倍)')
        
        # 条件4：热门概念
        if self._check_hot_concept(symbol):
            score += 20
            result['reasons'].append('属于热门概念板块')
        
        # 条件5：资金流向加分（主力资金活跃）
        fund_score = get_fund_flow_score(symbol, df)
        if fund_score > 0:
            score += fund_score
            result['reasons'].append(f'资金流向活跃+{fund_score:.0f}分')
        
        # 条件6：MACD技术指标加分
        macd_score, macd_reasons = get_macd_score(df)
        if macd_score > 0:
            score += macd_score
        result['reasons'].extend(macd_reasons)
        
        # 任一条件满足且分数达标即为热门资金股
        if score >= 20:
            result['is_hot'] = True
            result['score'] = min(score, 100)
        
        return result
    
    def _is_value_trend_stock(self, symbol: str, df: pd.DataFrame) -> Dict:
        """
        判断是否为价值趋势股
        
        需同时满足以下条件：
        1. 0 < PE <= 50
        2. PB <= 5
        3. 价格站上20日均线
        4. 成交量放大 >= 1.3倍
        
        Args:
            symbol: 股票代码
            df: 历史价格数据
            
        Returns:
            Dict: {'is_value': bool, 'score': float, 'reasons': list}
        """
        result = {'is_value': False, 'score': 0.0, 'reasons': []}
        conditions_met = 0
        score = 0.0
        
        # 获取基本面数据
        fundamental = get_stock_fundamental(symbol)
        pe = fundamental.get('pe')
        pb = fundamental.get('pb')
        
        # 条件1：PE合理
        if pe is not None and 0 < pe <= VALUE_STOCK_MAX_PE:
            conditions_met += 1
            score += 25
            result['reasons'].append(f'PE合理({pe:.1f})')
        else:
            result['reasons'].append(f'PE不符合({pe})')
            return result  # PE必须满足
        
        # 条件2：PB合理
        if pb is not None and 0 < pb <= VALUE_STOCK_MAX_PB:
            conditions_met += 1
            score += 25
            result['reasons'].append(f'PB合理({pb:.2f})')
        else:
            result['reasons'].append(f'PB不符合({pb})')
            return result  # PB必须满足
        
        # 条件3：站上MA20
        if len(df) >= 20:
            ma20 = calculate_ma(df, 20).iloc[-1]
            close = df['close'].iloc[-1]
            if close > ma20:
                conditions_met += 1
                score += 25
                result['reasons'].append(f'站上MA20({close:.2f}>{ma20:.2f})')
            else:
                result['reasons'].append(f'未站上MA20')
                return result
        
        # 条件4：成交量放大
        volume_ratio = calculate_volume_ratio(df, period=20)
        if volume_ratio >= VALUE_STOCK_MIN_VOLUME_RATIO:
            conditions_met += 1
            score += 25
            result['reasons'].append(f'成交量放大({volume_ratio:.1f}倍)')
        else:
            result['reasons'].append(f'成交量不足({volume_ratio:.1f}倍)')
            return result
        
        # 条件5（辅助加分）：MACD金叉确认趋势
        macd_score, macd_reasons = get_macd_score(df)
        if macd_score > 0:
            # 价值趋势股的MACD加分减半（辅助作用）
            bonus = min(macd_score * 0.5, 15)
            score += bonus
            result['reasons'].append(f'MACD趋势确认+{bonus:.0f}分')
        # 记录MACD风险提示（但不影响分数）
        for reason in macd_reasons:
            if '⚠️' in reason:
                result['reasons'].append(reason)
        
        # 所有条件都满足
        if conditions_met >= 4:
            result['is_value'] = True
            result['score'] = score
        
        return result
    
    def _check_hot_concept(self, symbol: str) -> bool:
        """
        检查股票是否属于热门概念板块
        
        Args:
            symbol: 股票代码
            
        Returns:
            bool: 是否属于热门概念
        """
        stock_concepts = get_stock_concepts(symbol)
        
        for concept in stock_concepts:
            # 检查是否包含热门概念关键词
            for hot in self.hot_concepts:
                if hot in concept or concept in hot:
                    return True
        
        return False
    
    def batch_classify(self, stock_pool: pd.DataFrame, verbose: bool = False) -> pd.DataFrame:
        """
        批量分类股票池
        
        Args:
            stock_pool: 股票池DataFrame，需包含 代码、名称 列
            verbose: 是否打印进度
            
        Returns:
            DataFrame: 带有分类结果的股票池
        """
        from .data_fetcher import get_stock_daily_history
        
        results = []
        total = len(stock_pool)
        
        for idx, row in stock_pool.iterrows():
            code = row['代码']
            name = row['名称']
            
            if verbose and (idx + 1) % 50 == 0:
                print(f"[分类进度] {idx + 1}/{total} ({(idx+1)/total*100:.1f}%)")
            
            try:
                # 获取历史数据
                df = get_stock_daily_history(code)
                
                # 分类
                classification = self.classify_stock(code, df)
                
                results.append({
                    '代码': code,
                    '名称': name,
                    'stock_type': classification['type'],
                    'layer': classification['layer'],
                    'score': classification['score'],
                    'reasons': '; '.join(classification['reasons'])
                })
            except Exception as e:
                if verbose:
                    print(f"[警告] 分类 {code} 失败: {e}")
                results.append({
                    '代码': code,
                    '名称': name,
                    'stock_type': STOCK_TYPE_NORMAL,
                    'layer': LAYER_NONE,
                    'score': 0.0,
                    'reasons': f'分类失败: {e}'
                })
        
        return pd.DataFrame(results)


# 创建全局分类器实例
stock_classifier = StockClassifier()


if __name__ == "__main__":
    # 测试
    from .data_fetcher import get_stock_daily_history
    
    print("测试股票分类器...")
    
    # 测试单只股票分类
    test_codes = ['000001', '300750', '603259']
    
    for code in test_codes:
        df = get_stock_daily_history(code)
        result = stock_classifier.classify_stock(code, df)
        print(f"\n{code}: {result['type']} -> {result['layer']}")
        print(f"  分数: {result['score']}")
        print(f"  原因: {result['reasons']}")
