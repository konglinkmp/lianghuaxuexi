"""
回撤控制器模块
当资金回撤超过阈值时，暂停新开仓
"""

import json
import os
from datetime import datetime
from typing import Tuple, Optional


class DrawdownController:
    """
    回撤控制器
    
    功能：
    1. 跟踪资金峰值
    2. 计算当前回撤
    3. 超过阈值时暂停交易
    """
    
    def __init__(self, 
                 max_drawdown: float = 0.15,  # 最大回撤阈值15%
                 initial_capital: float = 100000,
                 state_file: str = "data/drawdown_state.json"):
        self.max_drawdown = max_drawdown
        self.initial_capital = initial_capital
        self.state_file = state_file

        self._ensure_directory()
        
        # 从文件加载状态
        self._load_state()
    
    def _load_state(self):
        """加载状态"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    self.peak_capital = state.get('peak_capital', self.initial_capital)
                    self.current_capital = state.get('current_capital', self.initial_capital)
                    self.is_paused = state.get('is_paused', False)
                    self.pause_reason = state.get('pause_reason', '')
                    return
            except Exception as e:
                print(f"[警告] 加载回撤状态失败: {e}")
        
        # 默认状态
        self.peak_capital = self.initial_capital
        self.current_capital = self.initial_capital
        self.is_paused = False
        self.pause_reason = ''

    def _ensure_directory(self):
        """确保存储目录存在"""
        directory = os.path.dirname(self.state_file)
        if directory:
            os.makedirs(directory, exist_ok=True)
    
    def _save_state(self):
        """保存状态"""
        state = {
            'peak_capital': self.peak_capital,
            'current_capital': self.current_capital,
            'is_paused': self.is_paused,
            'pause_reason': self.pause_reason,
            'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[警告] 保存回撤状态失败: {e}")
    
    def update_capital(self, new_capital: float) -> Tuple[bool, str]:
        """
        更新当前资金
        
        Args:
            new_capital: 最新资金
            
        Returns:
            tuple: (是否允许交易, 状态信息)
        """
        self.current_capital = new_capital
        
        # 更新峰值
        if new_capital > self.peak_capital:
            self.peak_capital = new_capital
            # 如果之前是暂停状态，创新高后恢复
            if self.is_paused:
                self.is_paused = False
                self.pause_reason = ''
                print("✅ 资金创新高，恢复交易")
        
        # 计算回撤
        drawdown = self.get_current_drawdown()
        
        # 检查是否超过阈值
        if drawdown > self.max_drawdown:
            self.is_paused = True
            self.pause_reason = f"回撤{drawdown*100:.1f}%超过阈值{self.max_drawdown*100:.0f}%"
            self._save_state()
            return False, f"⚠️ {self.pause_reason}，暂停新开仓"
        
        self._save_state()
        return True, f"✅ 当前回撤: {drawdown*100:.1f}%（阈值{self.max_drawdown*100:.0f}%）"
    
    def get_current_drawdown(self) -> float:
        """
        获取当前回撤比例
        
        Returns:
            float: 回撤比例 (0-1)
        """
        if self.peak_capital <= 0:
            return 0.0
        return (self.peak_capital - self.current_capital) / self.peak_capital
    
    def can_trade(self) -> Tuple[bool, str]:
        """
        检查是否允许交易
        
        Returns:
            tuple: (是否允许, 原因)
        """
        if self.is_paused:
            return False, f"⛔ 交易暂停: {self.pause_reason}"
        return True, "✅ 可以交易"
    
    def force_resume(self):
        """
        强制恢复交易（用于手动干预）
        """
        self.is_paused = False
        self.pause_reason = ''
        self._save_state()
        print("✅ 已强制恢复交易")
    
    def reset(self, new_capital: Optional[float] = None):
        """
        重置控制器状态
        
        Args:
            new_capital: 新的初始资金（可选）
        """
        if new_capital is not None:
            self.initial_capital = new_capital
        
        self.peak_capital = self.initial_capital
        self.current_capital = self.initial_capital
        self.is_paused = False
        self.pause_reason = ''
        self._save_state()
        print(f"✅ 已重置回撤控制器，初始资金: ¥{self.initial_capital:,.2f}")
    
    def print_status(self):
        """打印当前状态"""
        drawdown = self.get_current_drawdown()
        status_emoji = "🟢" if not self.is_paused else "🔴"
        
        print("\n" + "=" * 50)
        print("📉 回撤控制器状态")
        print("=" * 50)
        print(f"  初始资金: ¥{self.initial_capital:,.2f}")
        print(f"  资金峰值: ¥{self.peak_capital:,.2f}")
        print(f"  当前资金: ¥{self.current_capital:,.2f}")
        print(f"  当前回撤: {drawdown*100:.2f}%")
        print(f"  回撤阈值: {self.max_drawdown*100:.0f}%")
        print(f"  交易状态: {status_emoji} {'暂停' if self.is_paused else '正常'}")
        if self.is_paused:
            print(f"  暂停原因: {self.pause_reason}")
        print("=" * 50)


# 创建全局实例
drawdown_controller = DrawdownController()


if __name__ == "__main__":
    # 测试
    print("=== 回撤控制器测试 ===\n")
    
    controller = DrawdownController(
        max_drawdown=0.15,
        initial_capital=100000,
        state_file="data/test_drawdown.json"
    )
    
    # 模拟资金变化
    capital_series = [
        100000, 105000, 110000, 108000, 112000,  # 正常上涨
        106000, 100000, 95000, 92000,            # 开始回撤
        90000,                                     # 接近阈值
    ]
    
    for capital in capital_series:
        can_trade, msg = controller.update_capital(capital)
        print(f"资金: ¥{capital:,} | {msg}")
    
    print()
    controller.print_status()
    
    # 模拟继续下跌触发暂停
    print("\n--- 继续下跌 ---")
    can_trade, msg = controller.update_capital(85000)  # 15%回撤
    print(f"资金: ¥85,000 | {msg}")
    
    # 检查是否允许交易
    can, reason = controller.can_trade()
    print(f"\n能否交易: {reason}")
    
    # 清理测试文件
    if os.path.exists("data/test_drawdown.json"):
        os.remove("data/test_drawdown.json")
