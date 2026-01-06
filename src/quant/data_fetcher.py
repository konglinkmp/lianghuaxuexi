"""
数据获取模块
使用 AKShare 获取 A 股行情数据
"""

import akshare as ak
import pandas as pd
import logging
import time
import warnings
import ssl
import urllib3
from datetime import datetime, timedelta
from functools import wraps
from config.config import HISTORY_DAYS, HS300_CODE

# 禁用 SSL 警告和验证（解决网络连接问题）
warnings.filterwarnings('ignore', category=urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings('ignore', message='Unverified HTTPS request')
ssl._create_default_https_context = ssl._create_unverified_context

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def retry(max_attempts: int = 3, delay: float = 1.0):
    """
    重试装饰器
    
    Args:
        max_attempts: 最大重试次数
        delay: 重试间隔（秒）
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts:
                        logger.warning(f"{func.__name__} 第{attempt}次调用失败: {e}，{delay}秒后重试...")
                        time.sleep(delay)
                    else:
                        logger.error(f"{func.__name__} 达到最大重试次数({max_attempts})，最终失败: {e}")
            return None if last_exception else None
        return wrapper
    return decorator


@retry(max_attempts=3, delay=1.0)
def get_all_a_stock_list() -> pd.DataFrame:
    """
    获取全 A 股股票列表
    
    Returns:
        DataFrame: 包含 代码、名称 等字段
    """
    global _stock_spot_cache
    
    logger.info("正在获取全A股列表...")
    start_time = time.time()
    
    # 使用东方财富接口获取A股实时行情（包含全部A股）
    df = ak.stock_zh_a_spot_em()
    
    # 缓存完整数据（供后续获取 PE/PB 使用）
    _stock_spot_cache = df.set_index('代码').to_dict('index')
    
    # 只保留需要的字段
    result = df[['代码', '名称']].copy()
    
    elapsed = time.time() - start_time
    logger.info(f"获取A股列表完成，共 {len(result)} 只股票，耗时 {elapsed:.2f}秒")
    return result


@retry(max_attempts=3, delay=1.0)
def get_stock_daily_history(symbol: str, days: int = HISTORY_DAYS) -> pd.DataFrame:
    """
    获取单只股票的历史日K线数据
    
    Args:
        symbol: 股票代码（如 '000001'）
        days: 获取最近N天的数据
        
    Returns:
        DataFrame: 包含 日期、开盘、收盘、最高、最低、成交量 等字段
    """
    # 计算起止日期（使用昨天作为结束日期，避免边界问题）
    end_date = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
    
    # 使用东方财富接口获取历史数据
    df = ak.stock_zh_a_hist(
        symbol=symbol,
        period="daily",
        start_date=start_date,
        end_date=end_date,
        adjust="qfq"  # 前复权
    )
    
    if df.empty:
        logger.warning(f"{symbol} 返回空数据")
        return pd.DataFrame()
    
    # 重命名列以便统一处理
    df = df.rename(columns={
        '日期': 'date',
        '开盘': 'open',
        '收盘': 'close',
        '最高': 'high',
        '最低': 'low',
        '成交量': 'volume',
        '成交额': 'amount'
    })
    
    # 确保日期为datetime类型
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    
    return df


@retry(max_attempts=3, delay=1.0)
def get_index_daily_history(index_code: str = HS300_CODE, days: int = HISTORY_DAYS) -> pd.DataFrame:
    """
    获取指数历史日K线数据
    
    Args:
        index_code: 指数代码（如 'sh000300' 表示沪深300）
        days: 获取最近N天的数据
        
    Returns:
        DataFrame: 包含 日期、收盘价 等字段
    """
    logger.info(f"正在获取指数 {index_code} 数据...")
    
    # 使用新浪接口获取指数数据
    df = ak.stock_zh_index_daily(symbol=index_code)
    
    if df.empty:
        logger.warning(f"指数 {index_code} 返回空数据")
        return pd.DataFrame()
    
    # 重命名列
    df = df.rename(columns={
        'date': 'date',
        'open': 'open',
        'close': 'close',
        'high': 'high',
        'low': 'low',
        'volume': 'volume'
    })
    
    # 确保日期为datetime类型
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    
    # 只取最近N天
    df = df.tail(days).reset_index(drop=True)
    
    logger.info(f"获取指数 {index_code} 数据完成，共 {len(df)} 条记录")
    return df


# 行业信息缓存
_industry_cache = {}

# 股票实时数据缓存（包含 PE/PB 等）
_stock_spot_cache = {}


@retry(max_attempts=2, delay=0.5)
def get_stock_industry(symbol: str) -> str:
    """
    获取股票所属行业/板块
    
    Args:
        symbol: 股票代码
        
    Returns:
        str: 所属行业名称，获取失败返回空字符串
    """
    global _industry_cache
    
    # 检查缓存
    if symbol in _industry_cache:
        return _industry_cache[symbol]
    
    try:
        df = ak.stock_individual_info_em(symbol=symbol)
        if df.empty:
            _industry_cache[symbol] = ""
            return ""
        
        # 查找行业信息
        for _, row in df.iterrows():
            if row['item'] == '行业':
                industry = str(row['value'])
                _industry_cache[symbol] = industry
                return industry
        
        _industry_cache[symbol] = ""
        return ""
    except Exception:
        _industry_cache[symbol] = ""
        return ""


@retry(max_attempts=2, delay=0.5)
def get_stock_info(symbol: str) -> dict:
    """
    获取股票基本信息（上市日期等）
    
    Args:
        symbol: 股票代码
        
    Returns:
        dict: 包含上市日期等信息
    """
    # 获取个股信息
    df = ak.stock_individual_info_em(symbol=symbol)
    
    if df.empty:
        return {}
    
    # 转换为字典
    info_dict = {}
    for _, row in df.iterrows():
        info_dict[row['item']] = row['value']
    
    return info_dict


@retry(max_attempts=2, delay=0.5)
def get_stock_fundamental(symbol: str) -> dict:
    """
    获取股票基本面数据（市盈率、市净率、上市日期）
    
    优先从缓存读取 PE/PB（由 get_all_a_stock_list 预加载），
    上市日期从 stock_individual_info_em 获取。
    
    Args:
        symbol: 股票代码
        
    Returns:
        dict: {'pe': float, 'pb': float, 'list_date': str}
              获取失败的字段值为 None
    """
    global _stock_spot_cache
    
    result = {'pe': None, 'pb': None, 'list_date': None}
    
    # 优先从缓存获取 PE/PB
    if symbol in _stock_spot_cache:
        spot_data = _stock_spot_cache[symbol]
        try:
            pe_val = spot_data.get('市盈率-动态')
            if pe_val is not None and pe_val != '-' and not pd.isna(pe_val):
                result['pe'] = float(pe_val)
        except (ValueError, TypeError):
            pass
        try:
            pb_val = spot_data.get('市净率')
            if pb_val is not None and pb_val != '-' and not pd.isna(pb_val):
                result['pb'] = float(pb_val)
        except (ValueError, TypeError):
            pass
    
    # 获取上市日期（需要调用 API）
    try:
        df = ak.stock_individual_info_em(symbol=symbol)
        if not df.empty:
            for _, row in df.iterrows():
                if row['item'] == '上市时间':
                    result['list_date'] = str(row['value']) if row['value'] else None
                    break
    except Exception as e:
        logger.warning(f"获取 {symbol} 上市日期失败: {e}")
    
    return result


if __name__ == "__main__":
    # 简单测试
    print("测试获取A股列表...")
    stocks = get_all_a_stock_list()
    print(f"共获取 {len(stocks)} 只股票")
    print(stocks.head())
    
    print("\n测试获取单只股票历史数据...")
    hist = get_stock_daily_history("000001")
    print(hist.tail())
    
    print("\n测试获取沪深300指数数据...")
    index_hist = get_index_daily_history()
    print(index_hist.tail())
