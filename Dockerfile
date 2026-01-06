# 使用官方 Python 轻量级镜像
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
# 防止 Python 生成 .pyc 文件
ENV PYTHONDONTWRITEBYTECODE=1
# 确保控制台输出不被缓冲
ENV PYTHONUNBUFFERED=1
# 设置时区为上海
ENV TZ=Asia/Shanghai

# 安装必要的系统库
# 如果某些 Python 库需要编译（如 gcc），可以在这里安装
# RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
# 使用清华源加速下载
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制项目代码
COPY . .

# 设置 PYTHONPATH，确保 src 目录在路径中
ENV PYTHONPATH=/app/src

# 创建数据和输出目录（用于挂载卷）
RUN mkdir -p data outputs

# 默认启动命令
# 默认显示帮助信息
CMD ["python", "-m", "quant.main", "--help"]
