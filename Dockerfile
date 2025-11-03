FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Etc/UTC

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    locales \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 仅安装依赖
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip && \
    pip install -r /app/requirements.txt

# 复制源代码（保持 .gitignore 的输出目录不被复制）
COPY src /app/src
COPY scripts /app/scripts
COPY config /app/config
COPY assets /app/assets

# 创建输出目录（将通过卷挂载覆盖）
RUN mkdir -p /app/output

# 缺省命令：仅预检
CMD ["python", "scripts/local_picker/create_mixtape.py", "--preflight-only"]


