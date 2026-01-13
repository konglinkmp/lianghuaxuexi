#!/bin/bash

# =================================================================
# A股量化工具每日自动运行脚本
# =================================================================

# 1. 获取脚本所在目录的绝对路径
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 2. 配置日志文件
LOGS_DIR="$SCRIPT_DIR/logs"
LOG_FILE="$LOGS_DIR/daily_run.log"

# 确保日志目录存在
if [ ! -d "$LOGS_DIR" ]; then
    mkdir -p "$LOGS_DIR" || { echo "❌ 无法创建日志目录: $LOGS_DIR"; exit 1; }
fi

# 每次运行前清理旧日志并给用户反馈
echo "📝 日志文件位置: $LOG_FILE"
rm -f "$LOG_FILE"

echo "--------------------------------------------------" >> "$LOG_FILE"
echo "🚀 开始运行每日计划: $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"

# 3. 激活虚拟环境
if [ -f "$SCRIPT_DIR/venv/bin/activate" ]; then
    source "$SCRIPT_DIR/venv/bin/activate"
else
    echo "❌ 错误: 未找到虚拟环境，请先创建 venv" >> "$LOG_FILE"
    exit 1
fi

# 4. 设置环境变量
export PYTHONPATH="$SCRIPT_DIR/src"

# 5. 执行主程序
# --ignore-holdings: 忽略持仓，查看全量推荐
python3 -m quant.main --custom --ignore-holdings "$@" >> "$LOG_FILE" 2>&1

# 6. 检查执行结果
if [ $? -eq 0 ]; then
    echo "✅ 运行成功: $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"
else
    echo "❌ 运行失败，请检查日志" >> "$LOG_FILE"
fi

echo "--------------------------------------------------" >> "$LOG_FILE"
