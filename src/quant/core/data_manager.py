"""
数据管理器模块
负责本地 SQLite 数据库的创建、维护和查询
"""

import sqlite3
import pandas as pd
import os
from datetime import datetime
from typing import Optional, List, Dict
from config.config import DB_PATH

class DataManager:
    def __init__(self, db_path: str = DB_PATH, cache_ttl_hours: int = 4):
        self.db_path = db_path
        self._ensure_db_dir()
        self._init_tables()
        
        # 内存缓存
        self._memory_cache: Dict[str, pd.DataFrame] = {}
        self._cache_timestamps: Dict[str, datetime] = {}
        self._cache_ttl_hours = cache_ttl_hours
        self._cache_max_size = 500  # 最大缓存条目数

    def _ensure_db_dir(self):
        """确保数据库目录存在"""
        directory = os.path.dirname(self.db_path)
        if directory:
            os.makedirs(directory, exist_ok=True)

    def _get_conn(self):
        """获取数据库连接"""
        return sqlite3.connect(self.db_path)

    def _init_tables(self):
        """初始化数据库表结构"""
        conn = self._get_conn()
        cursor = conn.cursor()

        # 股票基础信息表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_meta (
            code TEXT PRIMARY KEY,
            name TEXT,
            industry TEXT,
            list_date TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # 日线行情表
        # 使用复合主键 (code, date) 防止重复
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_daily (
            code TEXT,
            date TEXT,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            amount REAL,
            adjust_factor REAL,
            PRIMARY KEY (code, date)
        )
        ''')
        
        # 创建索引以加速查询
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_daily_code_date ON stock_daily (code, date)')
        
        # 更新日志表（用于智能缓存）
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS update_log (
            data_type TEXT PRIMARY KEY,
            updated_date TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # 指数日线表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS index_daily (
            code TEXT,
            date TEXT,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            PRIMARY KEY (code, date)
        )
        ''')
        
        conn.commit()
        conn.close()

    def save_stock_meta(self, df: pd.DataFrame):
        """
        保存股票基础信息
        df columns: code, name, industry, list_date
        """
        if df.empty:
            return

        conn = self._get_conn()
        # 使用 replace 模式，如果有重复主键则替换
        # 注意：to_sql 的 if_exists='replace' 会删除表重建，这里我们希望是 upsert
        # SQLite 的 upsert 语法较新，这里用 executemany 配合 INSERT OR REPLACE
        
        data = []
        for _, row in df.iterrows():
            data.append((
                row.get('code'),
                row.get('name'),
                row.get('industry', ''),
                row.get('list_date', ''),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
            
        cursor = conn.cursor()
        cursor.executemany('''
        INSERT OR REPLACE INTO stock_meta (code, name, industry, list_date, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ''', data)
        
        conn.commit()
        conn.close()

    def get_stock_meta(self, code: Optional[str] = None) -> pd.DataFrame:
        """获取股票基础信息"""
        conn = self._get_conn()
        if code:
            query = "SELECT * FROM stock_meta WHERE code = ?"
            df = pd.read_sql(query, conn, params=(code,))
        else:
            query = "SELECT * FROM stock_meta"
            df = pd.read_sql(query, conn)
        conn.close()
        return df

    def save_stock_daily(self, code: str, df: pd.DataFrame):
        """
        保存单只股票的日线数据
        df columns: date, open, high, low, close, volume, amount
        """
        if df.empty:
            return

        # 确保包含 code 列
        df = df.copy()
        df['code'] = code
        
        # 确保日期格式统一
        if not pd.api.types.is_string_dtype(df['date']):
             df['date'] = df['date'].dt.strftime('%Y-%m-%d')

        # 准备数据
        data = []
        for _, row in df.iterrows():
            data.append((
                row['code'],
                row['date'],
                row.get('open'),
                row.get('high'),
                row.get('low'),
                row.get('close'),
                row.get('volume'),
                row.get('amount'),
                row.get('adjust_factor', 1.0) # 默认为1.0
            ))

        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.executemany('''
        INSERT OR REPLACE INTO stock_daily (code, date, open, high, low, close, volume, amount, adjust_factor)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', data)
        
        conn.commit()
        conn.close()

    def get_stock_daily(self, code: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """
        获取单只股票的日线数据
        """
        conn = self._get_conn()
        query = "SELECT * FROM stock_daily WHERE code = ?"
        params = [code]
        
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
            
        query += " ORDER BY date ASC"
        
        df = pd.read_sql(query, conn, params=params)
        conn.close()
        
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
            
        return df

    def get_latest_date(self, code: str) -> Optional[str]:
        """获取某只股票本地存储的最新日期"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(date) FROM stock_daily WHERE code = ?", (code,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    
    def get_stock_daily_cached(
        self,
        code: str,
        start_date: str = None,
        end_date: str = None
    ) -> pd.DataFrame:
        """
        带内存缓存的数据获取
        
        Args:
            code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            pd.DataFrame: 日线数据
        """
        from datetime import timedelta
        
        cache_key = f"{code}_{start_date}_{end_date}"
        
        # 检查内存缓存
        if cache_key in self._memory_cache:
            cache_time = self._cache_timestamps.get(cache_key)
            if cache_time and (datetime.now() - cache_time).total_seconds() < self._cache_ttl_hours * 3600:
                return self._memory_cache[cache_key].copy()
        
        # 从数据库读取
        df = self.get_stock_daily(code, start_date, end_date)
        
        # 更新缓存（如果缓存未满）
        if len(self._memory_cache) < self._cache_max_size:
            self._memory_cache[cache_key] = df.copy()
            self._cache_timestamps[cache_key] = datetime.now()
        else:
            # 缓存已满，清理最旧的条目
            self._cleanup_cache()
            self._memory_cache[cache_key] = df.copy()
            self._cache_timestamps[cache_key] = datetime.now()
        
        return df
    
    def _cleanup_cache(self, keep_ratio: float = 0.5):
        """
        清理过期或最旧的缓存条目
        
        Args:
            keep_ratio: 保留的缓存比例
        """
        if not self._cache_timestamps:
            return
        
        # 按时间戳排序，删除最旧的一半
        sorted_keys = sorted(
            self._cache_timestamps.keys(),
            key=lambda k: self._cache_timestamps[k]
        )
        
        remove_count = int(len(sorted_keys) * (1 - keep_ratio))
        for key in sorted_keys[:remove_count]:
            self._memory_cache.pop(key, None)
            self._cache_timestamps.pop(key, None)
    
    def clear_cache(self):
        """清空所有内存缓存"""
        self._memory_cache.clear()
        self._cache_timestamps.clear()
    
    def get_cache_stats(self) -> Dict:
        """获取缓存统计信息"""
        return {
            'cache_size': len(self._memory_cache),
            'max_size': self._cache_max_size,
            'ttl_hours': self._cache_ttl_hours,
            'usage_pct': f"{len(self._memory_cache) / self._cache_max_size * 100:.1f}%"
        }

    def is_today_updated(self, data_type: str) -> bool:
        """
        检查某类型数据今天是否已更新
        
        Args:
            data_type: 数据类型，如 'stock_list', 'index_sh000300'
        """
        today = datetime.now().strftime('%Y-%m-%d')
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT updated_date FROM update_log WHERE data_type = ?",
            (data_type,)
        )
        result = cursor.fetchone()
        conn.close()
        return result is not None and result[0] == today
    
    def mark_today_updated(self, data_type: str):
        """
        标记某类型数据今天已更新
        """
        today = datetime.now().strftime('%Y-%m-%d')
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO update_log (data_type, updated_date, updated_at) VALUES (?, ?, ?)",
            (data_type, today, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        )
        conn.commit()
        conn.close()
    
    def save_index_daily(self, code: str, df: pd.DataFrame):
        """保存指数日线数据"""
        if df.empty:
            return
        
        df = df.copy()
        df['code'] = code
        
        if not pd.api.types.is_string_dtype(df['date']):
            df['date'] = df['date'].dt.strftime('%Y-%m-%d')
        
        data = []
        for _, row in df.iterrows():
            data.append((
                row['code'],
                row['date'],
                row.get('open'),
                row.get('high'),
                row.get('low'),
                row.get('close'),
                row.get('volume')
            ))
        
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.executemany('''
        INSERT OR REPLACE INTO index_daily (code, date, open, high, low, close, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', data)
        conn.commit()
        conn.close()
    
    def get_index_daily(self, code: str, days: int = 120) -> pd.DataFrame:
        """获取指数日线数据"""
        conn = self._get_conn()
        query = f"SELECT * FROM index_daily WHERE code = ? ORDER BY date DESC LIMIT {days}"
        df = pd.read_sql(query, conn, params=(code,))
        conn.close()
        
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date').reset_index(drop=True)
        
        return df

data_manager = DataManager()

