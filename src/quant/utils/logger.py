"""
统一日志系统模块
提供统一的日志配置和格式化
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Optional


# 日志格式
CONSOLE_FORMAT = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
FILE_FORMAT = '%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# 默认配置
DEFAULT_LOG_DIR = 'logs'
DEFAULT_LOG_FILE = 'quant.log'
DEFAULT_MAX_BYTES = 10 * 1024 * 1024  # 10MB
DEFAULT_BACKUP_COUNT = 5


class LoggerManager:
    """
    日志管理器
    
    提供统一的日志配置，支持：
    - 控制台输出
    - 文件输出（带轮转）
    - 统一格式
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if LoggerManager._initialized:
            return
        
        self.loggers = {}
        self.log_dir = DEFAULT_LOG_DIR
        self.log_file = DEFAULT_LOG_FILE
        self.level = logging.INFO
        self._file_handler = None
        self._console_handler = None
        
        LoggerManager._initialized = True
    
    def setup(
        self,
        log_dir: str = DEFAULT_LOG_DIR,
        log_file: str = DEFAULT_LOG_FILE,
        level: int = logging.INFO,
        max_bytes: int = DEFAULT_MAX_BYTES,
        backup_count: int = DEFAULT_BACKUP_COUNT,
        console: bool = True,
        file: bool = True
    ) -> None:
        """
        初始化日志系统
        
        Args:
            log_dir: 日志目录
            log_file: 日志文件名
            level: 日志级别
            max_bytes: 单个日志文件最大字节数
            backup_count: 保留的备份文件数量
            console: 是否输出到控制台
            file: 是否输出到文件
        """
        self.log_dir = log_dir
        self.log_file = log_file
        self.level = level
        
        # 确保日志目录存在
        if file:
            os.makedirs(log_dir, exist_ok=True)
        
        # 创建控制台处理器
        if console and self._console_handler is None:
            self._console_handler = logging.StreamHandler()
            self._console_handler.setLevel(level)
            self._console_handler.setFormatter(
                logging.Formatter(CONSOLE_FORMAT, DATE_FORMAT)
            )
        
        # 创建文件处理器
        if file and self._file_handler is None:
            log_path = os.path.join(log_dir, log_file)
            self._file_handler = RotatingFileHandler(
                log_path,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding='utf-8'
            )
            self._file_handler.setLevel(level)
            self._file_handler.setFormatter(
                logging.Formatter(FILE_FORMAT, DATE_FORMAT)
            )
    
    def get_logger(self, name: str) -> logging.Logger:
        """
        获取指定名称的日志器
        
        Args:
            name: 日志器名称（通常使用模块名 __name__）
            
        Returns:
            logging.Logger: 配置好的日志器
        """
        if name in self.loggers:
            return self.loggers[name]
        
        logger = logging.getLogger(name)
        logger.setLevel(self.level)
        
        # 避免重复添加处理器
        if not logger.handlers:
            if self._console_handler:
                logger.addHandler(self._console_handler)
            if self._file_handler:
                logger.addHandler(self._file_handler)
        
        # 防止日志向上传播到根日志器
        logger.propagate = False
        
        self.loggers[name] = logger
        return logger
    
    def set_level(self, level: int) -> None:
        """设置全局日志级别"""
        self.level = level
        for logger in self.loggers.values():
            logger.setLevel(level)
        if self._console_handler:
            self._console_handler.setLevel(level)
        if self._file_handler:
            self._file_handler.setLevel(level)


# 全局日志管理器实例
logger_manager = LoggerManager()


def setup_logging(
    log_dir: str = DEFAULT_LOG_DIR,
    log_file: str = DEFAULT_LOG_FILE,
    level: int = logging.INFO,
    console: bool = True,
    file: bool = True
) -> None:
    """
    初始化日志系统（便捷函数）
    
    Args:
        log_dir: 日志目录
        log_file: 日志文件名
        level: 日志级别
        console: 是否输出到控制台
        file: 是否输出到文件
    """
    logger_manager.setup(
        log_dir=log_dir,
        log_file=log_file,
        level=level,
        console=console,
        file=file
    )


def get_logger(name: str) -> logging.Logger:
    """
    获取指定名称的日志器（便捷函数）
    
    Args:
        name: 日志器名称（通常使用模块名 __name__）
        
    Returns:
        logging.Logger: 配置好的日志器
    """
    return logger_manager.get_logger(name)


if __name__ == '__main__':
    # 测试
    setup_logging(level=logging.DEBUG)
    
    logger = get_logger('test_module')
    logger.debug('这是一条调试日志')
    logger.info('这是一条信息日志')
    logger.warning('这是一条警告日志')
    logger.error('这是一条错误日志')
    
    print(f"\n日志文件已保存到: {DEFAULT_LOG_DIR}/{DEFAULT_LOG_FILE}")
