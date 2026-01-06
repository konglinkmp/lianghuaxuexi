"""
基本面过滤模块
根据市盈率、市净率、上市时间等条件筛选股票
"""

from datetime import datetime
from ..core.data_fetcher import get_stock_fundamental
from config.config import MAX_PE, MAX_PB, MIN_LIST_YEARS


def check_fundamental(symbol: str, 
                      max_pe: float = MAX_PE,
                      max_pb: float = MAX_PB,
                      min_list_years: int = MIN_LIST_YEARS) -> tuple:
    """
    检查股票是否通过基本面筛选
    
    Args:
        symbol: 股票代码
        max_pe: 最大市盈率阈值
        max_pb: 最大市净率阈值
        min_list_years: 最小上市年限
        
    Returns:
        tuple: (是否通过, 原因说明)
    """
    fundamental = get_stock_fundamental(symbol)
    
    pe = fundamental.get('pe')
    pb = fundamental.get('pb')
    list_date = fundamental.get('list_date')
    
    # 检查市盈率
    if pe is not None:
        if pe <= 0:
            return False, f"PE为负({pe:.1f})，公司亏损"
        if pe > max_pe:
            return False, f"PE过高({pe:.1f}>{max_pe})"
    
    # 检查市净率
    if pb is not None:
        if pb <= 0:
            return False, f"PB为负({pb:.2f})，净资产为负"
        if pb > max_pb:
            return False, f"PB过高({pb:.2f}>{max_pb})"
    
    # 检查上市时间
    if list_date:
        try:
            # 解析上市日期（格式：YYYYMMDD 或 YYYY-MM-DD）
            list_date_clean = list_date.replace('-', '')
            if len(list_date_clean) == 8:
                list_dt = datetime.strptime(list_date_clean, '%Y%m%d')
                years_listed = (datetime.now() - list_dt).days / 365
                if years_listed < min_list_years:
                    return False, f"上市不足{min_list_years}年({years_listed:.1f}年)"
        except (ValueError, AttributeError):
            pass  # 解析失败时不做限制
    
    return True, "基本面通过"
