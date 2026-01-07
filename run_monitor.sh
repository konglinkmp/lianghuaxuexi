#!/bin/bash

# =================================================================
# A股量化工具盘中实时监控启动脚本
# =================================================================

# 1. 获取脚本所在目录的绝对路径
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# 2. 激活虚拟环境
if [ -f "$SCRIPT_DIR/venv/bin/activate" ]; then
    source "$SCRIPT_DIR/venv/bin/activate"
else
    echo "❌ 错误: 未找到虚拟环境，请先创建 venv"
    exit 1
fi

# 3. 设置环境变量
export PYTHONPATH="$SCRIPT_DIR/src"

# 4. 启动监控
# --interval 60: 每60秒检查一次
echo "🚀 正在启动盘中实时监控..."
echo "📈 监控日志请查看: logs/monitor.log"
echo "💡 按 Ctrl+C 可以停止监控"

python3 -m quant.trade.monitor --interval 60 "$@"
