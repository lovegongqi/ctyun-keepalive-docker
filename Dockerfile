FROM python:3.9-slim

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    curl \
    unzip \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpangocairo-1.0-0 \
    libwayland-client0 \
    && rm -rf /var/lib/apt/lists/*

# 创建工作目录
WORKDIR /app

# 复制脚本文件
COPY root/ctyun_keepalive.py .

# 安装Python依赖
RUN pip install --no-cache-dir \
    playwright \
    ddddocr \
    requests

# 安装Playwright浏览器
RUN python -m playwright install chromium --with-deps

# 创建数据目录
RUN mkdir -p data

# 设置时区为中国上海
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 设置环境变量
ENV PYTHONUNBUFFERED=1

# 启动命令（默认以守护进程模式运行）
CMD ["python", "ctyun_keepalive.py", "-d"]
