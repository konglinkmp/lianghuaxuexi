"""
选股池管理模块
负责股票过滤和自定义股票池加载
"""

import os
import pandas as pd
from datetime import datetime, timedelta
from .data_fetcher import get_all_a_stock_list, get_stock_info, get_stock_daily_history
from config.config import NEW_STOCK_DAYS


def filter_st_stocks(df: pd.DataFrame) -> pd.DataFrame:
    """
    剔除 ST 股票
    
    Args:
        df: 包含 '名称' 列的DataFrame
        
    Returns:
        过滤后的DataFrame
    """
    # ST股票名称中包含"ST"
    mask = ~df['名称'].str.contains('ST', case=False, na=False)
    return df[mask].copy()


def filter_special_sectors(df: pd.DataFrame) -> pd.DataFrame:
    """
    剔除创业板（300开头）和科创板（688开头）股票
    
    Args:
        df: 包含 '代码' 列的DataFrame
        
    Returns:
        过滤后的DataFrame
    """
    # 创业板代码以300或301开头，科创板代码以688开头
    mask = ~df['代码'].str.startswith(('300', '301', '688'), na=False)
    return df[mask].copy()


def filter_new_stocks(df: pd.DataFrame, min_days: int = NEW_STOCK_DAYS) -> pd.DataFrame:
    """
    剔除上市不满指定天数的新股

    Args:
        df: 包含 '代码' 列的DataFrame
        min_days: 最低上市天数

    Returns:
        过滤后的DataFrame
    """
    valid_stocks = []
    cutoff_date = datetime.now() - timedelta(days=min_days)

    for _, row in df.iterrows():
        try:
            info = get_stock_info(row['代码'])
            if not info:
                continue

            # 获取上市日期
            list_date_str = info.get('上市时间', '')
            if not list_date_str:
                continue

            list_date = datetime.strptime(str(list_date_str), '%Y%m%d')

            if list_date <= cutoff_date:
                valid_stocks.append(row['代码'])

        except Exception as e:
            # 解析失败的股票跳过
            continue

    return df[df['代码'].isin(valid_stocks)].copy()


def filter_by_market_cap(df: pd.DataFrame, min_cap: float = 20_0000_0000) -> pd.DataFrame:
    """
    剔除小市值股票（默认20亿）
    注意：需要实时行情数据，这里简化处理，如果无法获取市值则保留
    """
    # 这里需要获取市值数据，akshare的 stock_zh_a_spot_em 包含总市值
    # df 应该已经包含了这些信息，如果 get_all_a_stock_list 返回了完整数据
    if '总市值' in df.columns:
        # akshare返回的单位通常是元
        mask = df['总市值'] >= min_cap
        return df[mask].copy()
    return df


def filter_by_turnover(df: pd.DataFrame, min_avg_amount: float = 5000_0000) -> pd.DataFrame:
    """
    剔除流动性差的股票（过去20日日均成交额 < 5000万）
    注意：这需要请求历史数据，速度较慢，建议仅对初步筛选后的股票池使用
    """
    print(f"[信息] 正在过滤低流动性股票 (阈值: {min_avg_amount/10000:.0f}万)...")
    valid_stocks = []
    total = len(df)
    
    for i, (_, row) in enumerate(df.iterrows(), 1):
        code = row['代码']
        try:
            # 获取最近20日数据
            hist = get_stock_daily_history(code, days=30)
            if hist.empty or len(hist) < 10:
                continue
                
            # 计算日均成交额
            avg_amount = hist['amount'].tail(20).mean()
            if avg_amount >= min_avg_amount:
                valid_stocks.append(code)
                
        except Exception:
            continue
            
        if i % 50 == 0:
            print(f"[进度] 流动性过滤 {i}/{total}", end='\r')
            
    print(f"\n[信息] 流动性过滤完成，剩余 {len(valid_stocks)}/{total}")
    return df[df['代码'].isin(valid_stocks)].copy()


# 注意：已移除 filter_manipulation_stocks 函数
# 主力资金控盘现在作为正向加分项，在 stock_classifier.py 中处理


def load_custom_pool(filepath: str = "data/myshare.txt") -> list:
    """
    加载自定义股票池文件
    
    文件格式：每行一个股票代码
    例如：
    000001
    600000
    300750
    
    Args:
        filepath: 股票池文件路径
        
    Returns:
        股票代码列表
    """
    if not os.path.exists(filepath):
        return []
    
    stocks = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                code = line.strip()
                if code and not code.startswith('#'):  # 忽略空行和注释
                    # 补齐6位代码
                    code = code.zfill(6)
                    stocks.append(code)
    except Exception as e:
        print(f"[错误] 读取股票池文件失败: {e}")
        return []
    
    return stocks


def get_final_pool(use_custom: bool = False, custom_file: str = "data/myshare.txt",
                   skip_new_stock_filter: bool = True) -> pd.DataFrame:
    """
    获取最终的待分析股票池
    
    Args:
        use_custom: 是否使用自定义股票池
        custom_file: 自定义股票池文件路径
        skip_new_stock_filter: 是否跳过新股过滤（该过滤较慢）
        
    Returns:
        DataFrame: 包含代码和名称的股票列表
    """
    if use_custom:
        # 使用自定义股票池
        custom_codes = load_custom_pool(custom_file)
        if not custom_codes:
            print("[警告] 自定义股票池为空，使用全A股")
            use_custom = False
        else:
            # 获取全A股列表以匹配名称
            all_stocks = get_all_a_stock_list()
            if all_stocks.empty:
                return pd.DataFrame()
            
            # 筛选自定义股票池中的股票
            df = all_stocks[all_stocks['代码'].isin(custom_codes)].copy()
            print(f"[信息] 从自定义股票池加载 {len(df)} 只股票")
            
            # 剔除ST
            df = filter_st_stocks(df)
            print(f"[信息] 剔除ST后剩余 {len(df)} 只股票")
            
            # 剔除创业板和科创板
            df = filter_special_sectors(df)
            print(f"[信息] 剔除创业板/科创板后剩余 {len(df)} 只股票")
            
            return df.reset_index(drop=True)
    
    if not use_custom:
        # 使用全A股
        print("[信息] 正在获取全A股列表...")
        all_stocks = get_all_a_stock_list()
        
        if all_stocks.empty:
            print("[错误] 获取A股列表失败")
            return pd.DataFrame()
        
        print(f"[信息] 共获取 {len(all_stocks)} 只股票")
        
        # 剔除ST
        df = filter_st_stocks(all_stocks)
        print(f"[信息] 剔除ST后剩余 {len(df)} 只股票")
        
        # 剔除创业板和科创板
        df = filter_special_sectors(df)
        print(f"[信息] 剔除创业板/科创板后剩余 {len(df)} 只股票")
        
        # 剔除新股（可选，因为需要逐个查询，较慢）
        if not skip_new_stock_filter:
            print("[信息] 正在过滤新股（此过程较慢）...")
            df = filter_new_stocks(df)
            print(f"[信息] 剔除新股后剩余 {len(df)} 只股票")
            
        # 剔除小市值
        df = filter_by_market_cap(df)
        print(f"[信息] 剔除小市值后剩余 {len(df)} 只股票")
        
        # 剔除低流动性（非常慢，建议只在生成最终计划时使用，或者在本地有全量数据时使用）
        # df = filter_by_turnover(df)
        
        return df.reset_index(drop=True)


if __name__ == "__main__":
    # 测试
    print("测试加载自定义股票池...")
    custom = load_custom_pool()
    print(f"自定义股票池: {custom}")
    
    print("\n测试获取股票池（跳过新股过滤）...")
    pool = get_final_pool(use_custom=False, skip_new_stock_filter=True)
    print(f"股票池大小: {len(pool)}")
    print(pool.head(10))
