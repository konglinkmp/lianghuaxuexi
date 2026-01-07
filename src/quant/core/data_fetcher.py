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
from .data_manager import data_manager

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
    # 注意：akshare返回的列名可能是 '总市值'
    result = df[['代码', '名称', '总市值']].copy()
    
    # 保存到本地数据库
    try:
        # 补充一些字段以便保存
        save_df = result.copy()
        save_df = save_df.rename(columns={'代码': 'code', '名称': 'name'})
        data_manager.save_stock_meta(save_df)
        logger.info(f"已缓存 {len(save_df)} 条股票基础信息到本地数据库")
    except Exception as e:
        logger.warning(f"保存股票列表到数据库失败: {e}")

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
    # 计算目标结束日期（昨天）
    target_end_date = (datetime.now() - timedelta(days=1)).date()
    target_end_str = target_end_date.strftime('%Y%m%d')
    
    # 1. 检查本地最新日期
    latest_date_str = data_manager.get_latest_date(symbol)
    
    need_fetch = False
    fetch_start_date = None
    
    if latest_date_str:
        latest_date = datetime.strptime(latest_date_str.split()[0], '%Y-%m-%d').date()
        if latest_date < target_end_date:
            # 需要增量更新
            need_fetch = True
            fetch_start_date = (latest_date + timedelta(days=1)).strftime('%Y%m%d')
    else:
        # 无本地数据，全量获取
        need_fetch = True
        fetch_start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')

    # 2. 如果需要，从接口获取并保存
    if need_fetch:
        try:
            logger.info(f"[{symbol}] 正在更新数据: {fetch_start_date} -> {target_end_str}")
            df_remote = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=fetch_start_date,
                end_date=target_end_str,
                adjust="qfq"
            )
            
            if not df_remote.empty:
                # 重命名列
                df_remote = df_remote.rename(columns={
                    '日期': 'date',
                    '开盘': 'open',
                    '收盘': 'close',
                    '最高': 'high',
                    '最低': 'low',
                    '成交量': 'volume',
                    '成交额': 'amount'
                })
                # 确保日期格式
                df_remote['date'] = pd.to_datetime(df_remote['date'])
                
                # 保存到数据库
                data_manager.save_stock_daily(symbol, df_remote)
                logger.debug(f"[{symbol}] 已保存 {len(df_remote)} 条新记录")
            else:
                logger.debug(f"[{symbol}] 接口未返回数据")
                
        except Exception as e:
            logger.warning(f"[{symbol}] 获取远程数据失败: {e}")

    # 3. 从本地数据库读取（只取最近 days 天）
    # 计算读取的起始日期
    read_start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    df = data_manager.get_stock_daily(symbol, start_date=read_start_date)
    
    if df.empty:
        logger.warning(f"[{symbol}] 本地无数据且远程获取失败")
        return pd.DataFrame()
        
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

# 个股详细信息缓存 (ak.stock_individual_info_em)
_individual_info_cache = {}

# 股票实时数据缓存（包含 PE/PB 等）
_stock_spot_cache = {}
_market_cap_cache = {}


@retry(max_attempts=2, delay=0.5)
def get_stock_individual_info(symbol: str) -> dict:
    """
    获取个股详细信息（行业、上市日期、板块等）
    使用内部缓存减少 API 调用
    """
    global _individual_info_cache
    
    if symbol in _individual_info_cache:
        return _individual_info_cache[symbol]
    
    try:
        df = ak.stock_individual_info_em(symbol=symbol)
        if df.empty:
            _individual_info_cache[symbol] = {}
            return {}
        
        info_dict = {}
        for _, row in df.iterrows():
            info_dict[row['item']] = row['value']
        
        _individual_info_cache[symbol] = info_dict
        return info_dict
    except Exception as e:
        logger.debug(f"获取 {symbol} 个股信息失败: {e}")
        _individual_info_cache[symbol] = {}
        return {}


def get_stock_industry(symbol: str) -> str:
    """
    获取股票所属行业/板块
    """
    info = get_stock_individual_info(symbol)
    return str(info.get('行业', ''))


def get_stock_info(symbol: str) -> dict:
    """
    获取股票基本信息（上市日期等）
    """
    return get_stock_individual_info(symbol)


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
    
    # 获取上市日期
    info = get_stock_individual_info(symbol)
    result['list_date'] = str(info.get('上市时间', '')) if info.get('上市时间') else None
    
    return result


# ============ 分层策略数据接口 ============

# 概念板块缓存
_concept_cache = {}

# 龙虎榜缓存
_longhu_cache = {}
_longhu_cache_date = None


def get_stock_turnover_rate(symbol: str) -> float:
    """
    获取股票换手率（日频）
    
    Args:
        symbol: 股票代码
        
    Returns:
        float: 换手率百分比，获取失败返回 0.0
    """
    global _stock_spot_cache
    
    # 优先从缓存获取
    if symbol in _stock_spot_cache:
        spot_data = _stock_spot_cache[symbol]
        try:
            turnover = spot_data.get('换手率')
            if turnover is not None and turnover != '-' and not pd.isna(turnover):
                return float(turnover)
        except (ValueError, TypeError):
            pass
    
    # 缓存未命中，尝试单独获取
    try:
        df = ak.stock_zh_a_spot_em()
        if not df.empty:
            row = df[df['代码'] == symbol]
            if not row.empty:
                turnover = row['换手率'].values[0]
                if turnover is not None and not pd.isna(turnover):
                    return float(turnover)
    except Exception as e:
        logger.warning(f"获取 {symbol} 换手率失败: {e}")
    
    return 0.0


def get_stock_concepts(symbol: str) -> list:
    """
    获取股票所属概念板块列表
    
    Args:
        symbol: 股票代码
        
    Returns:
        list: 概念板块名称列表，获取失败返回空列表
    """
    global _concept_cache
    
    info = get_stock_individual_info(symbol)
    concepts = []
    
    # 尝试从 '板块' 或 '概念' 字段获取
    for key in ['板块', '概念']:
        value = info.get(key)
        if value:
            concepts.extend([c.strip() for c in str(value).split(',') if c.strip()])
    
    return list(set(concepts))


def get_stock_market_caps(symbols: list) -> dict:
    """
    批量获取股票总市值

    Args:
        symbols: 股票代码列表

    Returns:
        dict: {code: total_market_cap}
    """
    global _market_cap_cache
    if not symbols:
        return {}

    missing = [s for s in symbols if s not in _market_cap_cache]
    if missing:
        try:
            df = ak.stock_zh_a_spot_em()
            if not df.empty:
                for _, row in df.iterrows():
                    code = str(row.get("代码"))
                    cap = row.get("总市值")
                    if code and cap is not None and cap != "-":
                        try:
                            _market_cap_cache[code] = float(cap)
                        except (TypeError, ValueError):
                            continue
        except Exception as e:
            logger.warning(f"获取市值数据失败: {e}")

    return {code: _market_cap_cache.get(code, 0.0) for code in symbols}


def calculate_momentum(df: pd.DataFrame, days: int = 10) -> float:
    """
    计算N日动量（涨跌幅）
    
    Args:
        df: 包含 close 列的历史数据DataFrame
        days: 计算周期（默认10日）
        
    Returns:
        float: N日涨跌幅百分比，数据不足返回 0.0
    """
    if df is None or df.empty or len(df) < days:
        return 0.0
    
    try:
        current_price = df['close'].iloc[-1]
        past_price = df['close'].iloc[-days]
        if past_price > 0:
            return (current_price - past_price) / past_price * 100
    except (IndexError, KeyError):
        pass
    
    return 0.0


def calculate_volume_ratio(df: pd.DataFrame, period: int = 20) -> float:
    """
    计算成交量较N日均量的放大倍数
    
    Args:
        df: 包含 volume 列的历史数据DataFrame
        period: 均量周期（默认20日）
        
    Returns:
        float: 成交量放大倍数，数据不足返回 0.0
    """
    if df is None or df.empty or len(df) < period:
        return 0.0
    
    try:
        current_volume = df['volume'].iloc[-1]
        avg_volume = df['volume'].iloc[-period:].mean()
        if avg_volume > 0:
            return current_volume / avg_volume
    except (IndexError, KeyError):
        pass
    
    return 0.0


@retry(max_attempts=2, delay=0.5)
def get_stock_news(symbol: str, limit: int = 5) -> list:
    """
    获取个股最新新闻和公告摘要
    
    Args:
        symbol: 股票代码
        limit: 获取条数
        
    Returns:
        list: 包含新闻标题和摘要的列表
    """
    try:
        df = ak.stock_news_em(symbol=symbol)
        if df.empty:
            return []
        
        # 只取前 limit 条
        df = df.head(limit)
        
        news_list = []
        for _, row in df.iterrows():
            news_list.append({
                'title': row['新闻标题'],
                'content': row['新闻内容'],
                'date': row['发布时间']
            })
        return news_list
    except Exception as e:
        logger.warning(f"获取 {symbol} 新闻失败: {e}")
        return []


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
