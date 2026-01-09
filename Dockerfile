# 基础镜像（指定 Python 3.10）
FROM python:3.10.19-slim

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai

# 设置工作目录
WORKDIR /app

# 安装系统依赖（可选但推荐）
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 先拷贝依赖文件（利用 Docker 缓存）
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# 拷贝项目代码
COPY . .

# 暴露端口（FastAPI 默认）
EXPOSE 8000

# 启动命令（生产推荐）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
