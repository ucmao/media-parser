# 使用官方 Python 3.11-slim 镜像（Debian系列兼容 mini-racer 的预编译包）
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
# 防止 Python 生成 .pyc 文件
ENV PYTHONDONTWRITEBYTECODE 1
# 确保在输出日志时不会被缓冲，便于查看 Docker 日志
ENV PYTHONUNBUFFERED 1

# 复制依赖说明文件并配置国内镜像源后安装 Python 包
COPY requirements.txt /app/
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ && \
    pip install --no-cache-dir -r requirements.txt

# 复制项目所有代码
COPY . /app/

# 如果 static/videos 目录用于存放缓存拼接视频，确保有权限使用
RUN mkdir -p /app/static/videos && chmod -R 777 /app/static/videos

# 开放 8051 端口（在 app.py 中设定）
EXPOSE 8051

# 启动命令使用 gunicorn 运行（生产环境推荐）
# --workers 可以根据服务器 CPU 核心数进行调整
CMD ["gunicorn", "--workers", "3", "--bind", "0.0.0.0:8051", "app:app"]
