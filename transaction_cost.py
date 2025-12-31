"""
交易成本模型
计算滑点、佣金、印花税等交易成本
"""


class TransactionCostModel:
    """
    交易成本模型
    
    包含：
    - 佣金：万三（0.03%）
    - 印花税：千一（0.1%，仅卖出时收取）
    - 滑点：千一（0.1%）
    """
    
    def __init__(self, 
                 commission_rate: float = 0.0003,  # 佣金万三
                 stamp_tax: float = 0.001,          # 印花税千一
                 slippage: float = 0.001,           # 滑点千一
                 min_commission: float = 5.0):      # 最低佣金5元
        self.commission_rate = commission_rate
        self.stamp_tax = stamp_tax
        self.slippage = slippage
        self.min_commission = min_commission
    
    def calculate_buy_cost(self, price: float, shares: int) -> tuple:
        """
        计算买入成本
        
        Args:
            price: 买入价格
            shares: 买入股数
            
        Returns:
            tuple: (实际成交价, 佣金, 总成本)
        """
        # 滑点：买入时价格略高
        actual_price = price * (1 + self.slippage)
        
        # 交易金额
        trade_amount = actual_price * shares
        
        # 佣金（至少5元）
        commission = max(trade_amount * self.commission_rate, self.min_commission)
        
        # 总成本 = 交易金额 + 佣金
        total_cost = trade_amount + commission
        
        return actual_price, commission, total_cost
    
    def calculate_sell_cost(self, price: float, shares: int) -> tuple:
        """
        计算卖出成本
        
        Args:
            price: 卖出价格
            shares: 卖出股数
            
        Returns:
            tuple: (实际成交价, 佣金, 印花税, 净收入)
        """
        # 滑点：卖出时价格略低
        actual_price = price * (1 - self.slippage)
        
        # 交易金额
        trade_amount = actual_price * shares
        
        # 佣金（至少5元）
        commission = max(trade_amount * self.commission_rate, self.min_commission)
        
        # 印花税（仅卖出时收取）
        stamp = trade_amount * self.stamp_tax
        
        # 净收入 = 交易金额 - 佣金 - 印花税
        net_income = trade_amount - commission - stamp
        
        return actual_price, commission, stamp, net_income
    
    def calculate_round_trip_cost(self, buy_price: float, sell_price: float, shares: int) -> dict:
        """
        计算一轮完整交易的成本和收益
        
        Args:
            buy_price: 买入价格
            sell_price: 卖出价格
            shares: 股数
            
        Returns:
            dict: 包含各项成本和收益的字典
        """
        # 买入成本
        buy_actual, buy_comm, total_cost = self.calculate_buy_cost(buy_price, shares)
        
        # 卖出收入
        sell_actual, sell_comm, stamp, net_income = self.calculate_sell_cost(sell_price, shares)
        
        # 毛利润（不考虑成本）
        gross_profit = (sell_price - buy_price) * shares
        
        # 实际利润
        actual_profit = net_income - total_cost
        
        # 总成本
        total_transaction_cost = buy_comm + sell_comm + stamp + \
                                  (buy_actual - buy_price) * shares + \
                                  (sell_price - sell_actual) * shares
        
        return {
            'buy_price': buy_price,
            'buy_actual_price': buy_actual,
            'sell_price': sell_price,
            'sell_actual_price': sell_actual,
            'shares': shares,
            'buy_commission': buy_comm,
            'sell_commission': sell_comm,
            'stamp_tax': stamp,
            'slippage_cost': (buy_actual - buy_price + sell_price - sell_actual) * shares,
            'total_cost': total_transaction_cost,
            'gross_profit': gross_profit,
            'actual_profit': actual_profit,
            'gross_return_pct': (sell_price / buy_price - 1) * 100,
            'actual_return_pct': (actual_profit / total_cost) * 100
        }


# 创建默认的成本模型实例
default_cost_model = TransactionCostModel()


if __name__ == "__main__":
    # 测试
    model = TransactionCostModel()
    
    print("=== 交易成本模型测试 ===")
    print()
    
    # 模拟一笔交易
    buy_price = 10.00
    sell_price = 11.50  # 上涨15%
    shares = 1000
    
    result = model.calculate_round_trip_cost(buy_price, sell_price, shares)
    
    print(f"买入价: ¥{result['buy_price']:.2f}")
    print(f"实际买入价（含滑点）: ¥{result['buy_actual_price']:.2f}")
    print(f"卖出价: ¥{result['sell_price']:.2f}")
    print(f"实际卖出价（含滑点）: ¥{result['sell_actual_price']:.2f}")
    print(f"股数: {result['shares']}")
    print()
    print(f"买入佣金: ¥{result['buy_commission']:.2f}")
    print(f"卖出佣金: ¥{result['sell_commission']:.2f}")
    print(f"印花税: ¥{result['stamp_tax']:.2f}")
    print(f"滑点成本: ¥{result['slippage_cost']:.2f}")
    print(f"总交易成本: ¥{result['total_cost']:.2f}")
    print()
    print(f"毛利润: ¥{result['gross_profit']:.2f} ({result['gross_return_pct']:.2f}%)")
    print(f"实际利润: ¥{result['actual_profit']:.2f} ({result['actual_return_pct']:.2f}%)")
