"""
交易计划生成器
遍历股票池，生成"明日操作清单"
支持分层策略（稳健层+激进层）
"""

import os
import pandas as pd
from datetime import datetime
from ..core.data_fetcher import get_stock_daily_history, get_stock_industry
from .basic_filters import check_fundamental
from .strategy import (
    check_buy_signal,
    calculate_stop_loss,
    calculate_take_profit,
    get_latest_ma20,
)
from ..analysis.market_regime import adaptive_strategy
from ..risk.risk_control import get_risk_control_state
from ..risk.risk_positioning import calculate_position_size, estimate_adv_amount
from .sector_strength import build_sector_strength_filter
from .style_benchmark import get_style_benchmark_series
from config.config import (
    TOTAL_CAPITAL, OUTPUT_CSV, MAX_POSITIONS,
    RISK_BUDGET_DEFAULT,
    MAX_SINGLE_POSITION_RATIO,
    RISK_CONTRIBUTION_LIMIT,
    LIQUIDITY_ADV_LIMIT,
    ENABLE_TWO_LAYER_STRATEGY,
    CONSERVATIVE_STOP_LOSS, CONSERVATIVE_TAKE_PROFIT, CONSERVATIVE_MAX_POSITIONS,
    AGGRESSIVE_STOP_LOSS, AGGRESSIVE_TAKE_PROFIT, AGGRESSIVE_MAX_POSITIONS,
)
from ..trade.position_tracker import position_tracker, portfolio_manager
from .layer_strategy import LayerStrategy, LAYER_AGGRESSIVE, LAYER_CONSERVATIVE
from .news_risk_analyzer import news_risk_analyzer


def generate_trading_plan(stock_pool: pd.DataFrame, verbose: bool = True,
                          use_position_limit: bool = True,
                          use_layer_strategy: bool = None,
                          ignore_holdings: bool = False) -> pd.DataFrame:
    """
    生成交易计划
    
    Args:
        stock_pool: 股票池DataFrame，包含 代码、名称
        verbose: 是否打印进度
        use_position_limit: 是否应用持仓数量限制
        use_layer_strategy: 是否使用分层策略（None表示使用配置文件设置）
        ignore_holdings: 是否忽略当前持仓（仅分层策略有效）
        
    Returns:
        DataFrame: 交易计划列表
    """
    # 判断是否使用分层策略
    enable_layer = use_layer_strategy if use_layer_strategy is not None else ENABLE_TWO_LAYER_STRATEGY
    
    risk_state = get_risk_control_state(TOTAL_CAPITAL)
    strength_filter = build_sector_strength_filter(stock_pool)

    if enable_layer:
        plan_df = _generate_layer_trading_plan(
            stock_pool,
            verbose,
            risk_state=risk_state,
            strength_filter=strength_filter,
            ignore_holdings=ignore_holdings,
        )
    else:
        plan_df = _generate_single_layer_plan(
            stock_pool,
            verbose,
            use_position_limit,
            risk_state=risk_state,
            strength_filter=strength_filter,
        )

    plan_df = _attach_style_weights(plan_df)
    return plan_df


def _format_style_weights(weights: dict) -> str:
    if not weights:
        return ""
    return ", ".join(f"{k}:{v:.2f}" for k, v in weights.items())


def _attach_style_weights(plan_df: pd.DataFrame) -> pd.DataFrame:
    if plan_df is None or plan_df.empty:
        return plan_df

    _, info = get_style_benchmark_series()
    weights = info.get("weights") if info else None
    weight_text = _format_style_weights(weights)
    if weight_text:
        plan_df = plan_df.copy()
        plan_df["风格基准权重"] = weight_text
    return plan_df


def _generate_layer_trading_plan(stock_pool: pd.DataFrame, verbose: bool = True,
                                 risk_state=None, strength_filter=None,
                                 ignore_holdings: bool = False) -> pd.DataFrame:
    """
    使用分层策略生成交易计划
    """
    if verbose:
        print("\n🔄 使用分层策略（稳健层+激进层）")
    
    strategy = LayerStrategy(TOTAL_CAPITAL)
    layer_signals = strategy.generate_layer_signals(
        stock_pool,
        verbose=verbose,
        risk_state=risk_state,
        strength_filter=strength_filter,
        ignore_holdings=ignore_holdings,
    )
    
    # 层间相关性检测
    if verbose and layer_signals['conservative'] and layer_signals['aggressive']:
        cons_codes = [s['代码'] for s in layer_signals['conservative']]
        aggr_codes = [s['代码'] for s in layer_signals['aggressive']]
        
        corr_result = strategy.check_layer_correlation(cons_codes, aggr_codes)
        if corr_result['warning']:
            print(f"\n{corr_result['warning']}")
            print(f"   {corr_result['detail']}")
    
    # 格式化为DataFrame
    return strategy.format_layer_plans(layer_signals)


def _generate_single_layer_plan(stock_pool: pd.DataFrame, verbose: bool = True,
                                 use_position_limit: bool = True,
                                 risk_state=None,
                                 strength_filter=None) -> pd.DataFrame:
    """
    使用单层策略生成交易计划（原有逻辑）
    """
    if verbose:
        print("\n🔄 使用单层策略（传统模式）")
    if risk_state is None:
        risk_state = get_risk_control_state(TOTAL_CAPITAL)

    if not risk_state.can_trade:
        if verbose:
            print(f"[风控] {risk_state.summary()}")
            print("⛔ 风控限制：暂停新开仓")
        return pd.DataFrame()

    if verbose and risk_state.reasons:
        print(f"[风控] {risk_state.summary()}")

    plans = []
    total = len(stock_pool)

    params = adaptive_strategy.get_current_params()
    max_positions = params.max_positions or MAX_POSITIONS

    # 同步到持仓管理器（保持限制一致）
    portfolio_manager.max_positions = max_positions

    # 获取当前持仓数量
    current_positions = position_tracker.get_position_count()
    remaining_slots = max(max_positions - current_positions, 0)
    
    if verbose and use_position_limit:
        print(f"[持仓] 当前持仓 {current_positions}/{max_positions}，还可买入 {remaining_slots} 只")
    
    max_capital = TOTAL_CAPITAL * risk_state.max_total_exposure
    allocated_capital = 0.0

    for idx, row in stock_pool.iterrows():
        code = row['代码']
        name = row['名称']
        
        if verbose and (idx + 1) % 50 == 0:
            progress = (idx + 1) / total * 100
            print(f"[进度] 已分析 {idx + 1}/{total} 只股票 ({progress:.1f}%)...")
        
        # 检查是否还能继续推荐
        if use_position_limit and len(plans) >= remaining_slots:
            if verbose:
                print(f"[限制] 已达可推荐上限({remaining_slots}只)，停止分析")
            break
        
        try:
            # 获取历史数据
            df = get_stock_daily_history(code)
            
            if df.empty or len(df) < 25:  # 数据不足
                continue
            
            # 检查买入信号
            if not check_buy_signal(df):
                continue
            
            # 检查基本面
            passed, reason = check_fundamental(code)
            if not passed:
                if verbose:
                    print(f"[基本面] {name}({code}) 不符合: {reason}")
                continue
            
            # 检查是否已持有
            if use_position_limit and position_tracker.get_position(code):
                if verbose:
                    print(f"[跳过] {name}({code}) 已在持仓中")
                continue
            
            # 获取最新数据
            latest = df.iloc[-1]
            close_price = latest['close']
            
            # 计算MA20
            ma20 = get_latest_ma20(df)
            
            # 计算止损止盈（使用ATR动态止损）
            stop_loss = calculate_stop_loss(close_price, ma20, df)
            take_profit = calculate_take_profit(close_price)
            
            # AI 风险分析
            ai_risk = news_risk_analyzer.analyze_risk(code, name)
            if ai_risk.get('risk_level') == 'HIGH':
                if verbose:
                    print(f"[AI风险] {name}({code}) 识别为高风险: {ai_risk.get('risk_reason')}，已剔除")
                continue
            
            remaining_capital = max_capital - allocated_capital
            if remaining_capital <= 0:
                if verbose:
                    print("[风控] 已达到总仓位上限，停止推荐")
                break

            adv_amount = estimate_adv_amount(df, close_price)
            size_result = calculate_position_size(
                price=close_price,
                stop_loss=stop_loss,
                total_capital=TOTAL_CAPITAL,
                risk_budget_ratio=RISK_BUDGET_DEFAULT,
                risk_scale=risk_state.risk_scale,
                max_position_ratio=MAX_SINGLE_POSITION_RATIO,
                max_positions=max_positions,
                adv_amount=adv_amount,
                liquidity_limit=LIQUIDITY_ADV_LIMIT,
                risk_contribution_limit=RISK_CONTRIBUTION_LIMIT,
                remaining_capital=remaining_capital,
            )

            suggested_shares = size_result.shares
            if suggested_shares < 100:
                continue

            position_amount = suggested_shares * close_price
            allocated_capital += position_amount
            actual_position_ratio = position_amount / TOTAL_CAPITAL

            # 获取板块信息
            industry = get_stock_industry(code)
            concepts = []
            industry_ok = concept_ok = False
            strength_label = ""
            if strength_filter is not None:
                try:
                    from .data_fetcher import get_stock_concepts
                    concepts = get_stock_concepts(code)
                except Exception:
                    concepts = []
                industry_ok, concept_ok, strength_label = strength_filter.strength_flags(
                    industry, concepts
                )
                if not strength_filter.is_allowed(industry, concepts, layer="AGGRESSIVE"):
                    continue
            
            concept_text = "，".join(concepts) if concepts else ""
            plans.append({
                '代码': code,
                '名称': name,
                '板块': industry or '未知',
                '行业名称': industry or '未知',
                '概念列表': concept_text,
                '行业强势': "强" if industry_ok else "弱",
                '概念强势': "强" if concept_ok else "弱",
                '板块强度': strength_label,
                '收盘价': round(close_price, 2),
                '建议买入价': round(close_price, 2),  # 以收盘价作为参考
                '止损价': round(stop_loss, 2),
                '止盈价': round(take_profit, 2),
                'MA20': round(ma20, 2),
                '建议股数': suggested_shares,
                '建议金额': round(position_amount, 2),
                '仓位比例': f"{actual_position_ratio * 100:.1f}%",
                'ai_risk_level': ai_risk.get('risk_level', 'LOW'),
                'ai_risk_reason': ai_risk.get('risk_reason', ''),
                'ai_risk_details': ai_risk.get('details', '')
            })
            
        except Exception as e:
            if verbose:
                print(f"[警告] 分析 {code} 时出错: {e}")
            continue
    
    return pd.DataFrame(plans)


def print_trading_plan(plan_df: pd.DataFrame, market_status: str = ""):
    """
    在终端打印交易计划
    
    Args:
        plan_df: 交易计划DataFrame
        market_status: 市场状态信息（可选）
    """
    if plan_df.empty:
        print("\n" + "=" * 60)
        print("📋 明日操作清单：无符合条件的股票")
        print("=" * 60)
        print("\n💡 可能原因：")
        print("   1. 当前无符合分类条件的股票")
        print("   2. 符合条件的股票价格偏离均线过大（追高风险）")
        print("   3. 股票池范围较小，可尝试扩大筛选范围")
        if market_status:
            print(f"   4. 市场状态: {market_status}")
        print("\n📌 建议：可适当放宽参数或等待更好的入场时机")
        return
    
    print("\n" + "=" * 80)
    print(f"📋 明日操作清单（生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}）")
    if "风格基准权重" in plan_df.columns:
        weight_text = plan_df["风格基准权重"].iloc[0]
        if isinstance(weight_text, str) and weight_text:
            print(f"🧭 风格基准权重: {weight_text}")
    
    # 检查是否为分层策略输出
    is_layer_strategy = 'layer' in plan_df.columns
    
    if is_layer_strategy:
        _print_layer_trading_plan(plan_df, market_status)
    else:
        _print_single_layer_plan(plan_df, market_status)


def _print_layer_trading_plan(plan_df: pd.DataFrame, market_status: str = ""):
    """打印分层策略交易计划"""
    # 按层分组
    conservative_df = plan_df[plan_df['layer'] == LAYER_CONSERVATIVE]
    aggressive_df = plan_df[plan_df['layer'] == LAYER_AGGRESSIVE]
    
    print(f"📊 共筛选出 {len(plan_df)} 只股票（稳健层 {len(conservative_df)} + 激进层 {len(aggressive_df)}）")
    print("=" * 80)
    
    # 打印稳健层
    print("\n" + "=" * 80)
    print(f"💰 稳健层（价值趋势策略）")
    print(f"📊 推荐数量：{len(conservative_df)}/{CONSERVATIVE_MAX_POSITIONS}")
    print(f"⚙️ 止损: -{CONSERVATIVE_STOP_LOSS*100:.0f}% | 止盈: +{CONSERVATIVE_TAKE_PROFIT*100:.0f}%")
    print("=" * 80)
    
    if conservative_df.empty:
        print("   暂无符合条件的价值趋势股")
    else:
        for idx, (_, row) in enumerate(conservative_df.iterrows()):
            _print_stock_row(row, idx + 1, "稳")
    
    # 打印激进层
    print("\n" + "=" * 80)
    print(f"🚀 激进层（热门资金策略）")
    print(f"📊 推荐数量：{len(aggressive_df)}/{AGGRESSIVE_MAX_POSITIONS}")
    print(f"⚙️ 止损: -{AGGRESSIVE_STOP_LOSS*100:.0f}% | 止盈: +{AGGRESSIVE_TAKE_PROFIT*100:.0f}%")
    print("=" * 80)
    
    if aggressive_df.empty:
        print("   暂无符合条件的热门资金股")
    else:
        for idx, (_, row) in enumerate(aggressive_df.iterrows()):
            _print_stock_row(row, idx + 1, "激")
    
    # 风险提示
    print("\n" + "=" * 80)
    print("⚠️ 风险提示：以上仅供参考，不构成投资建议。请结合自身风险承受能力谨慎决策。")
    print("💡 稳健层适合中线持有，激进层注意及时止盈止损。")
    print("=" * 80)


def _print_stock_row(row, idx: int, prefix: str):
    """打印单只股票信息"""
    industry = row.get('板块', '未知')
    stock_type = row.get('stock_type', '')
    reasons = row.get('reasons', '')
    strength_label = row.get('板块强度', '')
    concepts = row.get('概念列表', '')
    
    print(f"\n【{prefix}{idx}】{row['名称']} ({row['代码']}) - 📌{industry}")
    if stock_type:
        type_label = "热门资金股" if stock_type == "HOT_MONEY" else "价值趋势股"
        print(f"    类型: {type_label}")
    if reasons:
        print(f"    特征: {reasons}")
    if strength_label:
        print(f"    板块强度: {strength_label}")
    if concepts:
        print(f"    概念: {concepts}")
    
    # 打印 AI 风险
    ai_risk_level = row.get('ai_risk_level', 'LOW')
    ai_risk_reason = row.get('ai_risk_reason', '')
    if ai_risk_level != 'LOW':
        risk_emoji = "🔴" if ai_risk_level == "HIGH" else "⚠️"
        print(f"    {risk_emoji} AI风险提示: {ai_risk_reason}")
        
    print(f"    收盘价: ¥{row['收盘价']:.2f} | MA20: ¥{row['MA20']:.2f}")
    print(f"    止损价: ¥{row['止损价']:.2f} → 止盈价: ¥{row['止盈价']:.2f}")
    print(f"    建议仓位: {row['建议股数']}股 (约¥{row['建议金额']:.0f}，占{row['仓位比例']})")


def _print_single_layer_plan(plan_df: pd.DataFrame, market_status: str = ""):
    """打印单层策略交易计划（原有格式）"""
    print(f"📊 共筛选出 {len(plan_df)} 只股票符合买入条件")
    
    # 显示当前持仓状态
    current_positions = position_tracker.get_position_count()
    params = adaptive_strategy.get_current_params()
    max_positions = params.max_positions or MAX_POSITIONS
    print(f"💼 当前持仓: {current_positions}/{max_positions}")
    print("=" * 80)
    
    # 格式化打印
    for idx, row in plan_df.iterrows():
        industry = row.get('板块', '未知')
        concepts = row.get('概念列表', '')
        strength_label = row.get('板块强度', '')
        print(f"\n【{idx + 1}】{row['名称']} ({row['代码']}) - 📌{industry}")
        print(f"    收盘价: ¥{row['收盘价']:.2f}")
        print(f"    建议买入价: ¥{row['建议买入价']:.2f}")
        print(f"    止损价: ¥{row['止损价']:.2f} (跌破即卖出)")
        print(f"    止盈价: ¥{row['止盈价']:.2f} (达到即卖出)")
        print(f"    MA20: ¥{row['MA20']:.2f}")
        if strength_label:
            print(f"    板块强度: {strength_label}")
        if concepts:
            print(f"    概念: {concepts}")
        
        # 打印 AI 风险
        ai_risk_level = row.get('ai_risk_level', 'LOW')
        ai_risk_reason = row.get('ai_risk_reason', '')
        if ai_risk_level != 'LOW':
            risk_emoji = "🔴" if ai_risk_level == "HIGH" else "⚠️"
            print(f"    {risk_emoji} AI风险提示: {ai_risk_reason}")

        print(f"    建议仓位: {row['建议股数']}股 (约¥{row['建议金额']:.0f}，占{row['仓位比例']})")
    
    print("\n" + "=" * 80)
    print("⚠️ 风险提示：以上仅供参考，不构成投资建议。请结合自身风险承受能力谨慎决策。")
    print("=" * 80)


def save_trading_plan(plan_df: pd.DataFrame, filepath: str = OUTPUT_CSV):
    """
    保存交易计划到CSV和Markdown文件
    """
    if plan_df.empty:
        print(f"\n[信息] 无交易计划需要保存")
        return
    
    try:
        output_dir = os.path.dirname(filepath)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        # 保存 Markdown 报告
        md_path = filepath.replace('.csv', '.md') if filepath.endswith('.csv') else filepath
        save_markdown_report(plan_df, md_path)
        print(f"\n[信息] 详细交易报告已保存至: {md_path}")
        
    except Exception as e:
        print(f"\n[错误] 保存计划失败: {e}")


def save_markdown_report(plan_df: pd.DataFrame, filepath: str):
    """生成美观的 Markdown 交易报告"""
    title = f"# 📋 量化交易计划报告 ({datetime.now().strftime('%Y-%m-%d')})"
    
    lines = [title, "\n"]
    
    if "风格基准权重" in plan_df.columns:
        weight_text = plan_df["风格基准权重"].iloc[0]
        if weight_text:
            lines.append(f"> 🧭 **风格基准权重**：{weight_text}\n")

    is_layer = 'layer' in plan_df.columns
    
    def _get_table(df):
        if df.empty:
            return "暂无符合条件的股票"
        
        # 挑选核心字段
        cols = ['名称', '代码', '收盘价', '建议股数', '建议金额', '仓位比例', 'reasons', 'ai_risk_reason']
        # 检查列是否存在
        existing_cols = [c for c in cols if c in df.columns]
        temp_df = df[existing_cols].copy()
        
        # 重命名列名以提高美观度
        rename_map = {
            'reasons': '推荐理由',
            'ai_risk_reason': 'AI风险提示',
            '建议金额': '建议金额(¥)',
            '收盘价': '现价',
            '建议买入价': '建议买入价',
            '买入备注': '操作备注'
        }
        temp_df = temp_df.rename(columns=rename_map)
        
        return temp_df.to_markdown(index=False)

    if is_layer:
        from .layer_strategy import LAYER_CONSERVATIVE, LAYER_AGGRESSIVE
        cons = plan_df[plan_df['layer'] == LAYER_CONSERVATIVE]
        aggr = plan_df[plan_df['layer'] == LAYER_AGGRESSIVE]
        
        lines.append("## 🛡️ 稳健层 (价值趋势策略)")
        lines.append(_get_table(cons))
        lines.append("\n")
        
        lines.append("## 🚀 激进层 (热门资金策略)")
        lines.append(_get_table(aggr))
        lines.append("\n")
    else:
        lines.append("## 📈 选股清单")
        lines.append(_get_table(plan_df))
        lines.append("\n")
    
    lines.append("---\n")
    lines.append("**⚠️ 风险提示**：以上内容仅供参考，不构成投资建议。市场有风险，入市需谨慎。")
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    # 简单测试
    from .stock_pool import get_final_pool
    
    print("测试交易计划生成器...")
    
    # 获取一小部分股票测试
    pool = get_final_pool(use_custom=False, skip_new_stock_filter=True)
    test_pool = pool.head(20)  # 只测试前20只
    
    plan = generate_trading_plan(test_pool, verbose=True)
    print_trading_plan(plan)
    save_trading_plan(plan)
