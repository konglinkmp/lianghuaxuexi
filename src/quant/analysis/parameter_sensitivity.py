"""
参数敏感性分析模块
对策略参数进行网格测试，评估参数稳定性
"""

import itertools
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

import pandas as pd
import numpy as np


@dataclass
class SensitivityResult:
    """敏感性分析结果"""
    param_combination: Dict[str, Any]
    sharpe_ratio: float
    total_return: float
    max_drawdown: float
    win_rate: float
    trade_count: int


@dataclass
class SensitivityReport:
    """敏感性分析报告"""
    results: List[SensitivityResult] = field(default_factory=list)
    best_params: Optional[Dict[str, Any]] = None
    stability_score: float = 0.0
    
    def to_dataframe(self) -> pd.DataFrame:
        """转换为 DataFrame"""
        records = []
        for r in self.results:
            record = r.param_combination.copy()
            record['sharpe_ratio'] = r.sharpe_ratio
            record['total_return'] = r.total_return
            record['max_drawdown'] = r.max_drawdown
            record['win_rate'] = r.win_rate
            record['trade_count'] = r.trade_count
            records.append(record)
        return pd.DataFrame(records)


class ParameterSensitivityAnalyzer:
    """
    参数敏感性分析器
    
    通过网格搜索测试不同参数组合的策略表现，
    评估参数稳定性，识别过拟合风险。
    """
    
    # 默认测试参数范围
    DEFAULT_PARAM_RANGES = {
        'MA_SHORT': [15, 18, 20, 22, 25],
        'STOP_LOSS_RATIO': [0.03, 0.05, 0.07],
        'TAKE_PROFIT_RATIO': [0.10, 0.15, 0.20],
        'VOLUME_RATIO_THRESHOLD': [1.0, 1.2, 1.5],
    }
    
    def __init__(self, base_params: Optional[Dict] = None):
        """
        初始化分析器
        
        Args:
            base_params: 基准参数（未测试的参数使用此值）
        """
        self.base_params = base_params or {}
    
    def run_sensitivity_test(
        self,
        stock_pool: pd.DataFrame,
        param_ranges: Optional[Dict[str, List]] = None,
        metric: str = 'sharpe_ratio',
        max_workers: int = 4,
        verbose: bool = True
    ) -> SensitivityReport:
        """
        对指定参数范围进行网格测试
        
        Args:
            stock_pool: 股票池
            param_ranges: 参数测试范围，格式 {'param_name': [val1, val2, ...]}
            metric: 用于评估的主指标
            max_workers: 并行进程数
            verbose: 是否打印进度
            
        Returns:
            SensitivityReport: 分析报告
        """
        if param_ranges is None:
            param_ranges = self.DEFAULT_PARAM_RANGES
        
        # 生成所有参数组合
        param_names = list(param_ranges.keys())
        param_values = list(param_ranges.values())
        combinations = list(itertools.product(*param_values))
        
        if verbose:
            total = len(combinations)
            print(f"\n🔬 参数敏感性分析")
            print(f"   测试参数: {param_names}")
            print(f"   组合总数: {total}")
            print("=" * 60)
        
        results = []
        
        # 逐个测试参数组合
        for idx, combo in enumerate(combinations):
            params = dict(zip(param_names, combo))
            
            if verbose and (idx + 1) % 5 == 0:
                print(f"   进度: {idx + 1}/{len(combinations)}")
            
            try:
                result = self._run_single_backtest(stock_pool, params)
                results.append(result)
            except Exception as e:
                if verbose:
                    print(f"   [警告] 参数组合 {params} 测试失败: {e}")
        
        # 生成报告
        report = SensitivityReport(results=results)
        
        if results:
            # 找到最佳参数
            best = max(results, key=lambda x: getattr(x, metric, 0))
            report.best_params = best.param_combination
            
            # 计算稳定性分数
            report.stability_score = self._calculate_stability_score(results, metric)
        
        return report
    
    def _run_single_backtest(
        self,
        stock_pool: pd.DataFrame,
        params: Dict[str, Any]
    ) -> SensitivityResult:
        """运行单次回测"""
        # 动态修改配置（通过临时猴子补丁）
        import config.config as config_module
        
        # 保存原始值
        original_values = {}
        for key, value in params.items():
            if hasattr(config_module, key):
                original_values[key] = getattr(config_module, key)
                setattr(config_module, key, value)
        
        try:
            # 执行回测
            from .backtester import run_backtest
            
            result = run_backtest(
                stock_pool,
                verbose=False,
                parallel=False,
                use_adaptive=False
            )
            
            metrics = result.get_metrics()
            
            return SensitivityResult(
                param_combination=params.copy(),
                sharpe_ratio=metrics.get('sharpe_ratio', 0),
                total_return=metrics.get('total_return', 0),
                max_drawdown=metrics.get('max_drawdown', 0),
                win_rate=metrics.get('win_rate', 0),
                trade_count=metrics.get('total_trades', 0)
            )
        finally:
            # 恢复原始值
            for key, value in original_values.items():
                setattr(config_module, key, value)
    
    def _calculate_stability_score(
        self,
        results: List[SensitivityResult],
        metric: str
    ) -> float:
        """
        计算参数稳定性分数 (0-100)
        
        稳定性 = 100 - (标准差 / 均值) * 100
        如果不同参数组合的结果差异很大，说明策略对参数敏感，稳定性差
        """
        values = [getattr(r, metric, 0) for r in results]
        if not values:
            return 0.0
        
        mean_val = np.mean(values)
        std_val = np.std(values)
        
        if mean_val == 0:
            return 50.0  # 无法计算，返回中间值
        
        cv = std_val / abs(mean_val)  # 变异系数
        stability = max(0, min(100, 100 - cv * 100))
        
        return round(stability, 1)
    
    def print_report(self, report: SensitivityReport) -> None:
        """打印分析报告"""
        print("\n" + "=" * 70)
        print("📊 参数敏感性分析报告")
        print("=" * 70)
        
        if not report.results:
            print("   无测试结果")
            return
        
        # 稳定性评估
        stability = report.stability_score
        if stability >= 70:
            level = "✅ 高 (策略稳定)"
            emoji = "🟢"
        elif stability >= 40:
            level = "⚠️ 中 (需关注)"
            emoji = "🟡"
        else:
            level = "🔴 低 (过拟合风险)"
            emoji = "🔴"
        
        print(f"\n{emoji} 参数稳定性: {stability:.1f}/100 - {level}")
        
        # 最佳参数
        if report.best_params:
            print(f"\n🏆 最佳参数组合:")
            for key, value in report.best_params.items():
                print(f"   - {key}: {value}")
        
        # 结果汇总表
        df = report.to_dataframe()
        if not df.empty:
            print(f"\n📋 测试结果汇总 (共 {len(df)} 组):")
            print("-" * 70)
            
            # 按夏普比率排序，显示前5和后5
            df_sorted = df.sort_values('sharpe_ratio', ascending=False)
            
            print("\n【表现最好的 5 组】")
            top5 = df_sorted.head(5)
            for _, row in top5.iterrows():
                params_str = ", ".join(f"{k}={v}" for k, v in row.items() 
                                       if k not in ['sharpe_ratio', 'total_return', 'max_drawdown', 'win_rate', 'trade_count'])
                print(f"   Sharpe={row['sharpe_ratio']:.2f} | 收益={row['total_return']:.1f}% | {params_str}")
            
            print("\n【表现最差的 5 组】")
            bottom5 = df_sorted.tail(5)
            for _, row in bottom5.iterrows():
                params_str = ", ".join(f"{k}={v}" for k, v in row.items() 
                                       if k not in ['sharpe_ratio', 'total_return', 'max_drawdown', 'win_rate', 'trade_count'])
                print(f"   Sharpe={row['sharpe_ratio']:.2f} | 收益={row['total_return']:.1f}% | {params_str}")
        
        # 风险提示
        print("\n" + "-" * 70)
        if stability < 40:
            print("⚠️ 警告: 策略对参数变化非常敏感，存在过拟合风险！")
            print("   建议: 简化策略逻辑，减少参数数量，或使用更长的回测周期验证。")
        elif stability < 70:
            print("⚠️ 提示: 策略对部分参数较为敏感，建议进一步验证。")
            print("   建议: 关注参数变化对收益的影响，避免使用极端参数值。")
        else:
            print("✅ 策略参数稳定性良好，过拟合风险较低。")
        
        print("=" * 70)
    
    def save_report(self, report: SensitivityReport, filepath: str) -> None:
        """保存报告到 CSV"""
        df = report.to_dataframe()
        df.to_csv(filepath, index=False, encoding='utf-8-sig')
        print(f"\n[信息] 敏感性分析报告已保存至: {filepath}")


# 全局实例
sensitivity_analyzer = ParameterSensitivityAnalyzer()


if __name__ == '__main__':
    # 测试
    print("参数敏感性分析模块测试...")
    
    # 构造测试股票池
    test_pool = pd.DataFrame({
        '代码': ['000001', '600000', '000002'],
        '名称': ['平安银行', '浦发银行', '万科A']
    })
    
    # 小范围测试
    small_ranges = {
        'MA_SHORT': [18, 20, 22],
        'STOP_LOSS_RATIO': [0.04, 0.05, 0.06],
    }
    
    report = sensitivity_analyzer.run_sensitivity_test(
        test_pool,
        param_ranges=small_ranges,
        verbose=True
    )
    
    sensitivity_analyzer.print_report(report)
