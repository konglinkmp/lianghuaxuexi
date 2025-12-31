"""
持仓跟踪与组合管理模块
实现持仓记录、行业分散控制、持仓数量限制
"""

import json
import os
from datetime import datetime
from collections import defaultdict
from typing import Optional, Tuple, List, Dict
import pandas as pd

from config.config import MAX_POSITIONS, MAX_SECTOR_POSITIONS, POSITION_FILE


class PositionTracker:
    """
    持仓跟踪器
    
    功能：
    1. 记录已买入的股票
    2. 跟踪止损/止盈价格
    3. 更新最高价（用于移动止盈）
    """
    
    def __init__(self, filepath: str = POSITION_FILE):
        self.filepath = filepath
        self.positions: Dict[str, dict] = {}
        self._ensure_directory()
        self._load()

    def _ensure_directory(self):
        """确保持仓文件所在目录存在"""
        directory = os.path.dirname(self.filepath)
        if directory:
            os.makedirs(directory, exist_ok=True)
    
    def _load(self):
        """从文件加载持仓记录"""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    self.positions = json.load(f)
            except Exception as e:
                print(f"[警告] 加载持仓文件失败: {e}")
                self.positions = {}
    
    def _save(self):
        """保存持仓记录到文件"""
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(self.positions, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            print(f"[警告] 保存持仓文件失败: {e}")
    
    def add_position(self, code: str, name: str, entry_price: float, 
                     shares: int, stop_loss: float, take_profit: float,
                     sector: str = "未知") -> bool:
        """
        添加持仓
        
        Args:
            code: 股票代码
            name: 股票名称
            entry_price: 买入价格
            shares: 买入股数
            stop_loss: 止损价
            take_profit: 止盈价
            sector: 所属行业
            
        Returns:
            bool: 是否添加成功
        """
        if code in self.positions:
            print(f"[警告] {code} 已在持仓中")
            return False
        
        self.positions[code] = {
            'name': name,
            'entry_price': entry_price,
            'shares': shares,
            'entry_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'highest_price': entry_price,
            'current_price': entry_price,
            'sector': sector,
            'status': 'holding'
        }
        
        self._save()
        print(f"[持仓] 已添加 {name}({code}) | 买入价:¥{entry_price:.2f} | "
              f"止损:¥{stop_loss:.2f} | 止盈:¥{take_profit:.2f}")
        return True
    
    def remove_position(self, code: str, exit_price: float, exit_reason: str) -> Optional[dict]:
        """
        移除持仓（卖出）
        
        Args:
            code: 股票代码
            exit_price: 卖出价格
            exit_reason: 卖出原因
            
        Returns:
            dict: 交易记录，如果不存在则返回None
        """
        if code not in self.positions:
            return None
        
        pos = self.positions.pop(code)
        
        # 计算盈亏
        pnl = (exit_price - pos['entry_price']) * pos['shares']
        pnl_pct = (exit_price / pos['entry_price'] - 1) * 100
        
        trade_record = {
            'code': code,
            'name': pos['name'],
            'entry_price': pos['entry_price'],
            'exit_price': exit_price,
            'shares': pos['shares'],
            'entry_date': pos['entry_date'],
            'exit_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'exit_reason': exit_reason,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'sector': pos['sector']
        }
        
        self._save()
        
        emoji = "🟢" if pnl > 0 else "🔴"
        print(f"{emoji} [卖出] {pos['name']}({code}) | {exit_reason} | "
              f"盈亏:¥{pnl:.2f} ({pnl_pct:+.2f}%)")
        
        return trade_record
    
    def update_price(self, code: str, current_price: float) -> Optional[str]:
        """
        更新持仓当前价格
        
        Args:
            code: 股票代码
            current_price: 当前价格
            
        Returns:
            str: 触发的信号（'stop_loss', 'take_profit', 'trailing_stop', None）
        """
        if code not in self.positions:
            return None
        
        pos = self.positions[code]
        pos['current_price'] = current_price
        
        # 更新最高价
        if current_price > pos['highest_price']:
            pos['highest_price'] = current_price
        
        # 检查止损
        if current_price <= pos['stop_loss']:
            return 'stop_loss'
        
        # 检查止盈
        if current_price >= pos['take_profit']:
            return 'take_profit'
        
        # 检查移动止盈（从最高点回落8%）
        trailing_stop = pos['highest_price'] * 0.92
        if pos['highest_price'] > pos['entry_price'] * 1.10 and current_price <= trailing_stop:
            return 'trailing_stop'
        
        self._save()
        return None
    
    def get_position(self, code: str) -> Optional[dict]:
        """获取单个持仓信息"""
        return self.positions.get(code)
    
    def get_all_positions(self) -> Dict[str, dict]:
        """获取所有持仓"""
        return self.positions.copy()
    
    def get_position_count(self) -> int:
        """获取当前持仓数量"""
        return len(self.positions)
    
    def get_sector_count(self, sector: str) -> int:
        """获取某行业的持仓数量"""
        return sum(1 for p in self.positions.values() if p.get('sector') == sector)
    
    def print_positions(self):
        """打印当前持仓摘要"""
        if not self.positions:
            print("\n📭 当前无持仓")
            return
        
        print(f"\n📊 当前持仓 ({len(self.positions)}/{MAX_POSITIONS})")
        print("-" * 80)
        
        total_value = 0
        total_pnl = 0
        
        for code, pos in self.positions.items():
            current = pos.get('current_price', pos['entry_price'])
            pnl = (current - pos['entry_price']) * pos['shares']
            pnl_pct = (current / pos['entry_price'] - 1) * 100
            total_value += current * pos['shares']
            total_pnl += pnl
            
            emoji = "🟢" if pnl >= 0 else "🔴"
            print(f"{emoji} {pos['name']}({code}) | "
                  f"成本:¥{pos['entry_price']:.2f} | 现价:¥{current:.2f} | "
                  f"盈亏:{pnl_pct:+.2f}% | {pos['shares']}股 | {pos.get('sector', '未知')}")
        
        print("-" * 80)
        print(f"💰 总市值:¥{total_value:,.2f} | 总盈亏:¥{total_pnl:+,.2f}")


class PortfolioManager:
    """
    组合管理器
    
    功能：
    1. 持仓数量限制
    2. 行业分散控制
    3. 买入前检查
    """
    
    def __init__(self, position_tracker: PositionTracker,
                 max_positions: int = MAX_POSITIONS,
                 max_sector_positions: int = MAX_SECTOR_POSITIONS):
        self.tracker = position_tracker
        self.max_positions = max_positions
        self.max_sector_positions = max_sector_positions
    
    def can_add_position(self, code: str, sector: str = "未知") -> Tuple[bool, str]:
        """
        检查是否可以新增持仓
        
        Args:
            code: 股票代码
            sector: 所属行业
            
        Returns:
            tuple: (是否可以买入, 原因说明)
        """
        # 检查是否已持有
        if self.tracker.get_position(code):
            return False, f"{code} 已在持仓中"
        
        # 检查总持仓数量
        if self.tracker.get_position_count() >= self.max_positions:
            return False, f"持仓数量已达上限({self.max_positions}只)"
        
        # 检查行业集中度
        if sector != "未知" and self.tracker.get_sector_count(sector) >= self.max_sector_positions:
            return False, f"行业「{sector}」持仓已达上限({self.max_sector_positions}只)"
        
        return True, "可以买入"
    
    def filter_recommendations(self, recommendations: List[dict]) -> List[dict]:
        """
        过滤推荐列表，只保留可以买入的股票
        
        Args:
            recommendations: 推荐股票列表
            
        Returns:
            list: 过滤后的推荐列表
        """
        filtered = []
        sector_counts = defaultdict(int)
        
        # 先统计现有持仓的行业分布
        for pos in self.tracker.get_all_positions().values():
            sector_counts[pos.get('sector', '未知')] += 1
        
        current_count = self.tracker.get_position_count()
        
        for rec in recommendations:
            code = rec.get('code', rec.get('代码', ''))
            sector = rec.get('sector', rec.get('行业', '未知'))
            
            # 检查总数量
            if current_count + len(filtered) >= self.max_positions:
                print(f"[限制] 已达最大持仓数量({self.max_positions}只)，停止推荐")
                break
            
            # 检查是否已持有
            if self.tracker.get_position(code):
                continue
            
            # 检查行业集中度
            if sector_counts[sector] >= self.max_sector_positions:
                print(f"[限制] {rec.get('name', rec.get('名称', code))} 所属行业「{sector}」已达上限")
                continue
            
            filtered.append(rec)
            sector_counts[sector] += 1
        
        return filtered


# 创建全局实例
position_tracker = PositionTracker()
portfolio_manager = PortfolioManager(position_tracker)


if __name__ == "__main__":
    # 测试
    print("=== 持仓跟踪器测试 ===")
    
    tracker = PositionTracker("data/test_positions.json")
    manager = PortfolioManager(tracker, max_positions=5, max_sector_positions=2)
    
    # 测试添加持仓
    tracker.add_position("000001", "平安银行", 10.50, 1000, 9.98, 12.08, "银行")
    tracker.add_position("600036", "招商银行", 32.50, 500, 30.88, 37.38, "银行")
    tracker.add_position("000002", "万科A", 15.20, 800, 14.44, 17.48, "房地产")
    
    # 打印持仓
    tracker.print_positions()
    
    # 测试检查
    can_buy, reason = manager.can_add_position("601398", "银行")
    print(f"\n能否买入工商银行(银行): {can_buy} - {reason}")
    
    can_buy, reason = manager.can_add_position("600519", "白酒")
    print(f"能否买入贵州茅台(白酒): {can_buy} - {reason}")
    
    # 清理测试文件
    if os.path.exists("data/test_positions.json"):
        os.remove("data/test_positions.json")
