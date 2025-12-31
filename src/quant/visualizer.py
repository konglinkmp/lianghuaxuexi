"""
可视化报告模块
生成回测结果的可视化图表
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
from typing import Optional
import os

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'STHeiti']
plt.rcParams['axes.unicode_minus'] = False


def generate_equity_curve(trades: list, initial_capital: float = 100000) -> pd.DataFrame:
    """
    生成资金曲线数据
    
    Args:
        trades: 交易记录列表
        initial_capital: 初始资金
        
    Returns:
        DataFrame: 包含日期和资金的数据
    """
    if not trades:
        return pd.DataFrame()
    
    df = pd.DataFrame(trades)
    
    # 按退出日期排序
    df['exit_date'] = pd.to_datetime(df['exit_date'])
    df = df.sort_values('exit_date').reset_index(drop=True)
    
    # 计算累计收益
    df['cumulative_pnl_pct'] = (1 + df['pnl_pct']).cumprod()
    df['equity'] = initial_capital * df['cumulative_pnl_pct']
    
    return df


def generate_monthly_returns(trades: list) -> pd.DataFrame:
    """
    生成月度收益数据
    
    Args:
        trades: 交易记录列表
        
    Returns:
        DataFrame: 月度收益透视表
    """
    if not trades:
        return pd.DataFrame()
    
    df = pd.DataFrame(trades)
    df['exit_date'] = pd.to_datetime(df['exit_date'])
    df['year'] = df['exit_date'].dt.year
    df['month'] = df['exit_date'].dt.month
    
    # 按年月汇总收益
    monthly = df.groupby(['year', 'month'])['pnl_pct'].sum().reset_index()
    monthly['pnl_pct'] = monthly['pnl_pct'] * 100  # 转为百分比
    
    # 创建透视表
    pivot = monthly.pivot(index='month', columns='year', values='pnl_pct')
    pivot.index = ['1月', '2月', '3月', '4月', '5月', '6月', 
                   '7月', '8月', '9月', '10月', '11月', '12月'][:len(pivot)]
    
    return pivot


def plot_performance_report(trades: list, 
                            output_path: str = "outputs/backtest_report.png",
                            initial_capital: float = 100000) -> str:
    """
    生成可视化回测报告
    
    Args:
        trades: 交易记录列表
        output_path: 输出图片路径
        initial_capital: 初始资金
        
    Returns:
        str: 生成的图片路径
    """
    if not trades:
        print("[警告] 无交易记录，无法生成报告")
        return ""

    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    df = pd.DataFrame(trades)
    df['exit_date'] = pd.to_datetime(df['exit_date'])
    df = df.sort_values('exit_date').reset_index(drop=True)
    
    # 创建画布
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('量化策略回测报告', fontsize=16, fontweight='bold')
    
    # 1. 资金曲线
    ax1 = axes[0, 0]
    cumulative = (1 + df['pnl_pct']).cumprod()
    equity = initial_capital * cumulative
    ax1.plot(df['exit_date'], equity, 'b-', linewidth=1.5, label='资金曲线')
    ax1.axhline(y=initial_capital, color='gray', linestyle='--', alpha=0.5, label='初始资金')
    ax1.fill_between(df['exit_date'], initial_capital, equity, 
                     where=(equity >= initial_capital), alpha=0.3, color='green')
    ax1.fill_between(df['exit_date'], initial_capital, equity, 
                     where=(equity < initial_capital), alpha=0.3, color='red')
    ax1.set_title('资金曲线', fontsize=12)
    ax1.set_xlabel('日期')
    ax1.set_ylabel('资金 (¥)')
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)
    
    # 2. 收益分布直方图
    ax2 = axes[0, 1]
    pnl_pct = df['pnl_pct'] * 100
    bins = np.arange(-20, 25, 2.5)
    colors = ['red' if x < 0 else 'green' for x in bins[:-1]]
    n, bins_out, patches = ax2.hist(pnl_pct, bins=bins, edgecolor='white', alpha=0.7)
    for i, patch in enumerate(patches):
        if bins_out[i] < 0:
            patch.set_facecolor('red')
        else:
            patch.set_facecolor('green')
    ax2.axvline(x=0, color='black', linestyle='-', linewidth=1)
    ax2.axvline(x=pnl_pct.mean(), color='blue', linestyle='--', 
                label=f'平均收益: {pnl_pct.mean():.2f}%')
    ax2.set_title('单笔收益分布', fontsize=12)
    ax2.set_xlabel('收益率 (%)')
    ax2.set_ylabel('交易次数')
    ax2.legend()
    ax2.grid(True, alpha=0.3, axis='y')
    
    # 3. 月度收益柱状图
    ax3 = axes[1, 0]
    df['month'] = df['exit_date'].dt.to_period('M')
    monthly_returns = df.groupby('month')['pnl_pct'].sum() * 100
    colors = ['green' if x >= 0 else 'red' for x in monthly_returns.values]
    bars = ax3.bar(range(len(monthly_returns)), monthly_returns.values, color=colors, alpha=0.7)
    ax3.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
    ax3.set_title('月度收益', fontsize=12)
    ax3.set_xlabel('月份')
    ax3.set_ylabel('收益率 (%)')
    ax3.set_xticks(range(len(monthly_returns)))
    ax3.set_xticklabels([str(m)[-5:] for m in monthly_returns.index], rotation=45)
    ax3.grid(True, alpha=0.3, axis='y')
    
    # 4. 关键指标摘要
    ax4 = axes[1, 1]
    ax4.axis('off')
    
    # 计算指标
    total_trades = len(df)
    wins = len(df[df['pnl_pct'] > 0])
    win_rate = wins / total_trades * 100 if total_trades > 0 else 0
    
    gross_profit = df[df['pnl_pct'] > 0]['pnl_pct'].sum()
    gross_loss = abs(df[df['pnl_pct'] < 0]['pnl_pct'].sum())
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    total_return = (cumulative.iloc[-1] - 1) * 100 if len(cumulative) > 0 else 0
    
    # 最大回撤
    rolling_max = cumulative.cummax()
    drawdowns = (cumulative - rolling_max) / rolling_max
    max_drawdown = abs(drawdowns.min()) * 100 if len(drawdowns) > 0 else 0
    
    # 平均持仓天数
    avg_holding = df['holding_days'].mean() if 'holding_days' in df.columns else 0
    
    # 绘制指标表格
    metrics_text = f"""
    ╔══════════════════════════════════════╗
    ║         📊 回测核心指标               ║
    ╠══════════════════════════════════════╣
    ║  📈 总交易次数:     {total_trades:>6} 次        ║
    ║  🎯 胜率:           {win_rate:>6.1f}%         ║
    ║  💰 盈亏比:         {profit_factor:>6.2f}          ║
    ║  📉 最大回撤:       {max_drawdown:>6.1f}%         ║
    ║  💵 累计收益:       {total_return:>6.1f}%         ║
    ║  ⏱️  平均持仓:       {avg_holding:>6.1f} 天        ║
    ╚══════════════════════════════════════╝
    """
    
    ax4.text(0.1, 0.5, metrics_text, transform=ax4.transAxes, 
             fontsize=11, fontfamily='monospace', verticalalignment='center',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    
    print(f"[信息] 可视化报告已保存至: {output_path}")
    return output_path


def plot_drawdown_curve(trades: list, output_path: str = "outputs/drawdown.png") -> str:
    """
    绘制回撤曲线
    
    Args:
        trades: 交易记录列表
        output_path: 输出图片路径
        
    Returns:
        str: 生成的图片路径
    """
    if not trades:
        return ""

    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    df = pd.DataFrame(trades)
    df['exit_date'] = pd.to_datetime(df['exit_date'])
    df = df.sort_values('exit_date').reset_index(drop=True)
    
    cumulative = (1 + df['pnl_pct']).cumprod()
    rolling_max = cumulative.cummax()
    drawdowns = (cumulative - rolling_max) / rolling_max * 100
    
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.fill_between(df['exit_date'], 0, drawdowns, color='red', alpha=0.5)
    ax.plot(df['exit_date'], drawdowns, 'r-', linewidth=1)
    ax.axhline(y=-15, color='orange', linestyle='--', label='警戒线 (-15%)')
    ax.set_title('回撤曲线', fontsize=12)
    ax.set_xlabel('日期')
    ax.set_ylabel('回撤 (%)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    
    print(f"[信息] 回撤曲线已保存至: {output_path}")
    return output_path


if __name__ == "__main__":
    # 测试数据
    from .backtester import backtest_stock
    
    print("测试可视化模块...")
    
    # 获取测试交易数据
    trades = backtest_stock("000001", "平安银行")
    trades += backtest_stock("600036", "招商银行")
    
    if trades:
        print(f"共 {len(trades)} 笔交易")
        plot_performance_report(trades, "outputs/test_report.png")
        plot_drawdown_curve(trades, "outputs/test_drawdown.png")
    else:
        print("无交易数据")
